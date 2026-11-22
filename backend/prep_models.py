"""Download the 4 RVC speaker zips from Hugging Face -> MODELS_DIR/speaker_N/model.pth (+ .index)."""
import os, re, glob, shutil, zipfile
from huggingface_hub import hf_hub_download

REPO = "Speech-itu/Urdu_Speakers_Models_BSAI"
OUT = os.getenv("MODELS_DIR", "/kaggle/working/models/rvc")
TOKEN = os.environ["HF_TOKEN"]

SPEAKERS = [int(x) for x in os.getenv("SPEAKERS", "1,2,3,4").split(",")]
for n in SPEAKERS:
    z = hf_hub_download(REPO, f"rvc_speaker_{n}.zip", token=TOKEN)
    d = f"{OUT}/speaker_{n}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    names = zipfile.ZipFile(z).namelist()

    if any(x.endswith("data.pkl") for x in names) and not any(x.endswith(".pth") for x in names):
        shutil.copy(z, f"{d}/model.pth")            # the "zip" is itself a torch .pth file
    else:
        tmp = f"{d}/_x"; zipfile.ZipFile(z).extractall(tmp)
        def ok(p): return "__MACOSX" not in p and not os.path.basename(p).startswith(("D_", "G_", "._"))
        def epoch(p):                                   # e.g. midage_150e_6450s.pth -> 150
            m = re.search(r"(\d+)e_", os.path.basename(p)); return int(m.group(1)) if m else 0
        pths = [p for p in glob.glob(tmp + "/**/*.pth", recursive=True) if ok(p)]
        print(f"speaker_{n} candidates:", sorted(os.path.basename(p) for p in pths))
        if pths:
            best = max(pths, key=epoch)                 # highest epoch = latest checkpoint
            print(f"speaker_{n} using:", os.path.basename(best))
            shutil.copy(best, f"{d}/model.pth")
        else:                                        # extracted torch folder -> repack as .pth
            pk = glob.glob(tmp + "/**/data.pkl", recursive=True)[0]
            top = os.path.dirname(pk)
            with zipfile.ZipFile(f"{d}/model.pth", "w", zipfile.ZIP_STORED) as zz:
                for root, _, files in os.walk(top):
                    for fn in files:
                        full = os.path.join(root, fn); zz.write(full, os.path.relpath(full, os.path.dirname(top)))
        for ix in glob.glob(tmp + "/**/*.index", recursive=True):
            if "__MACOSX" not in ix and not os.path.basename(ix).startswith("._"):
                shutil.copy(ix, d)
        shutil.rmtree(tmp)
    print(f"speaker_{n}:", os.listdir(d))
