"""Find each speaker's fine-tuned Seed-VC files in the HF repo and lay them out as
MODELS_DIR/speaker_N/seedvc/{ckpt.pth,config.yml,ref.wav}. Works with zips or loose files, any folder name
as long as the path mentions 'seed' and 'speaker_N'."""
import os, re, glob, shutil, zipfile
from huggingface_hub import hf_hub_download, list_repo_files

REPO = os.getenv("SEEDVC_REPO", "Speech-itu/Urdu_Speakers_Models_BSAI")
OUT = os.getenv("MODELS_DIR", "/kaggle/working/models/rvc")
TOKEN = os.environ["HF_TOKEN"]
SPEAKERS = [int(x) for x in os.getenv("SPEAKERS", "1,2,3,4").split(",")]
EXT = (".zip", ".pth", ".yml", ".yaml", ".wav")

def clean(ps): return [p for p in ps if "__MACOSX" not in p and not os.path.basename(p).startswith("._")]
def step(p):
    m = re.search(r"step_(\d+)", os.path.basename(p)); return int(m.group(1)) if m else 0
def of_speaker(f, n): return re.search(rf"speaker[_\- ]?{n}(?!\d)", f.lower()) is not None

files = list_repo_files(REPO, token=TOKEN)
for n in SPEAKERS:
    d = f"{OUT}/speaker_{n}/seedvc"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    tmp = f"{d}/_x"; os.makedirs(tmp)
    cand = [f for f in files if "seed" in f.lower() and of_speaker(f, n) and f.lower().endswith(EXT)
            and "rvc" not in f.lower()]
    loose = [f for f in cand if not f.lower().endswith(".zip")]
    use = loose if any(f.lower().endswith(".pth") for f in loose) else cand   # prefer the folder, ignore old zips
    print(f"speaker_{n}: using repo files:", use)
    for f in use:
        local = hf_hub_download(REPO, f, token=TOKEN)
        if f.lower().endswith(".zip"): zipfile.ZipFile(local).extractall(f"{tmp}/{os.path.basename(f)}_")
        else:
            os.makedirs(f"{tmp}/{os.path.dirname(f)}", exist_ok=True); shutil.copy(local, f"{tmp}/{f}")

    pths = clean(glob.glob(tmp + "/**/*.pth", recursive=True))
    ft = [p for p in pths if os.path.basename(p).startswith("ft_model")]
    ckpt = ft[0] if ft else (max(pths, key=step) if pths else None)
    ymls = clean(glob.glob(tmp + "/**/*.yml", recursive=True) + glob.glob(tmp + "/**/*.yaml", recursive=True))
    own = [y for y in ymls if "/configs/" not in y]                              # saved next to the weights
    stock = [y for y in ymls if "whisper_small_wavenet" in os.path.basename(y)]  # preset used for training
    cfg = (own or stock or [None])[0]
    wavs = clean(glob.glob(tmp + "/**/*.wav", recursive=True))
    if not wavs:   # no reference clip in the folder -> take one from the old code zip's reference/ folder
        for f in [c for c in cand if c.lower().endswith(".zip")]:
            zf = zipfile.ZipFile(hf_hub_download(REPO, f, token=TOKEN))
            for name in zf.namelist():
                if name.lower().endswith(".wav") and "reference" in name.lower() and "__MACOSX" not in name:
                    zf.extract(name, f"{tmp}/_ref")
        wavs = clean(glob.glob(tmp + "/_ref/**/*.wav", recursive=True))
    wavs = sorted(wavs, key=lambda w: ("ref" not in w.lower(), w))
    print(f"speaker_{n}: ckpt={ckpt and os.path.relpath(ckpt, tmp)} | cfg={cfg and os.path.relpath(cfg, tmp)} | ref={wavs and os.path.relpath(wavs[0], tmp)}")
    if not (ckpt and cfg and wavs):
        print(f"speaker_{n}: INCOMPLETE -> RVC only. Repo files mentioning 'seed':", [f for f in files if "seed" in f.lower()])
        shutil.rmtree(d); continue
    shutil.copy(ckpt, f"{d}/ckpt.pth"); shutil.copy(cfg, f"{d}/config.yml"); shutil.copy(wavs[0], f"{d}/ref.wav")
    shutil.rmtree(tmp, ignore_errors=True)
