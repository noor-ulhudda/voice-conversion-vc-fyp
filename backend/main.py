"""Voice-conversion API (FastAPI + Applio/RVC). One GPU worker, async jobs."""
import os, uuid, time, shutil, subprocess, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

APPLIO = os.getenv("APPLIO_DIR", "/kaggle/working/Applio")
PYTHON = os.getenv("APPLIO_PYTHON", "python")
SEEDVC = os.getenv("SEEDVC_DIR", "/kaggle/working/seed-vc")
SEEDVC_PYTHON = os.getenv("SEEDVC_PYTHON", PYTHON)
ENABLED = {int(x) for x in os.getenv("ENABLED_SPEAKERS", "1,2,3,4").split(",")}
MODELS = Path(os.getenv("MODELS_DIR", "/kaggle/working/models/rvc"))
WORK = Path(os.getenv("WORK_DIR", "/tmp/vc_jobs")); WORK.mkdir(parents=True, exist_ok=True)
ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://voice-conversion-vc-fyp-frontend.vercel.app,http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000",
).split(",")

# (gender, age) -> speaker number.  1=old man, 2=old woman, 3=mid-age man, 4=mid-age woman
SPEAKERS = {("male", "old"): 1, ("female", "old"): 2, ("male", "adult"): 3, ("female", "adult"): 4}
# default pitch shift (semitones) per speaker; tune these by ear
PITCH = {1: 0, 2: 0, 3: 0, 4: 0}

MAX_UPLOAD = 20 * 1024 * 1024
JOBS: dict = {}
pool = ThreadPoolExecutor(max_workers=1)   # one conversion at a time on the GPU

app = FastAPI(title="Voice Conversion API")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_origin_regex=r"https://.*\.vercel\.app",
                   allow_methods=["*"], allow_headers=["*"])


def model_files(n: int):
    d = MODELS / f"speaker_{n}"
    idx = next(iter(glob.glob(str(d / "*.index"))), None)
    return d / "model.pth", idx


def seedvc_files(n: int):
    """(checkpoint, config, reference wav) for the fine-tuned Seed-VC stage, or None if not installed."""
    d = MODELS / f"speaker_{n}" / "seedvc"
    t = (d / "ckpt.pth", d / "config.yml", d / "ref.wav")
    return t if all(p.exists() for p in t) else None


def run_job(job_id: str, speaker: int, pitch: int):
    job = JOBS[job_id]; d = WORK / job_id
    try:
        job["status"] = "processing"
        src, wav, out = d / "input", d / "in.wav", d / "out.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", "90",
                            "-vn", "-ac", "1", "-ar", "40000", str(wav)], capture_output=True, text=True)
        if r.returncode: raise RuntimeError("Could not read the audio: " + r.stderr[-300:])

        pth, idx = model_files(speaker)
        cmd = [PYTHON, "core.py", "infer", "--input-path", str(wav), "--output-path", str(out),
               "--pth-path", str(pth), "--index-rate", "0.5" if idx else "0", "--pitch", str(pitch),
               "--f0-method", "rmvpe", "--embedder-model", "contentvec", "--protect", "0.33",
               "--export-format", "WAV"]
        if idx: cmd += ["--index-path", idx]
        job["stage"] = "voice"                       # stage 1: RVC
        r = subprocess.run(cmd, cwd=APPLIO, capture_output=True, text=True, timeout=600)
        if not out.exists(): raise RuntimeError("Conversion failed: " + (r.stdout + r.stderr)[-500:])
        job["file"] = str(out)

        sv = seedvc_files(speaker)
        if sv:                                       # stage 2: fine-tuned Seed-VC style transfer
            job["stage"] = "style"
            sdir = d / "sv"; sdir.mkdir(exist_ok=True)
            ck, cfg, ref = sv
            r = subprocess.run([SEEDVC_PYTHON, "inference.py", "--source", str(out), "--target", str(ref),
                                "--output", str(sdir), "--checkpoint", str(ck), "--config", str(cfg),
                                "--diffusion-steps", "50", "--length-adjust", "1.0",
                                "--inference-cfg-rate", "0.7", "--f0-condition", "False"],
                               cwd=SEEDVC, capture_output=True, text=True, timeout=900)
            wavs = sorted(glob.glob(str(sdir / "*.wav")))
            if not wavs: raise RuntimeError("Style transfer failed: " + (r.stdout + r.stderr)[-500:])
            job["file"] = wavs[0]
        job["status"] = "done"
    except Exception as e:
        job["status"], job["error"] = "error", str(e)


def cleanup():
    now = time.time()
    for jid in [j for j, v in JOBS.items() if now - v["t"] > 3600]:
        JOBS.pop(jid, None); shutil.rmtree(WORK / jid, ignore_errors=True)


@app.get("/health")
def health():
    return {"ok": True, "enabled": sorted(ENABLED),
            "rvc": {n: model_files(n)[0].exists() for n in (1, 2, 3, 4)},
            "seedvc": {n: seedvc_files(n) is not None for n in (1, 2, 3, 4)}}


@app.post("/convert")
async def convert(audio: UploadFile = File(...), gender: str = Form(...), age: str = Form(...),
                  pitch: int | None = Form(None)):
    cleanup()
    speaker = SPEAKERS.get((gender.lower(), age.lower()))
    if not speaker: raise HTTPException(400, "Unsupported voice. Choose male/female and adult/old.")
    if speaker not in ENABLED: raise HTTPException(400, "This voice is not available yet.")
    if not model_files(speaker)[0].exists(): raise HTTPException(500, f"Model for speaker {speaker} is not installed.")
    data = await audio.read()
    if not data: raise HTTPException(400, "Empty audio.")
    if len(data) > MAX_UPLOAD: raise HTTPException(413, "Audio too large (max 20 MB).")

    job_id = uuid.uuid4().hex
    (WORK / job_id).mkdir(parents=True)
    (WORK / job_id / "input").write_bytes(data)
    p = PITCH[speaker] if pitch is None else max(-24, min(24, pitch))
    JOBS[job_id] = {"status": "queued", "t": time.time()}
    pool.submit(run_job, job_id, speaker, p)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    j = JOBS.get(job_id)
    if not j: raise HTTPException(404, "Unknown job.")
    return {"status": j["status"], "stage": j.get("stage"), "error": j.get("error")}


@app.get("/jobs/{job_id}/audio")
def job_audio(job_id: str):
    j = JOBS.get(job_id)
    if not j or j["status"] != "done": raise HTTPException(404, "Not ready.")
    return FileResponse(j["file"], media_type="audio/wav", filename="converted.wav")
