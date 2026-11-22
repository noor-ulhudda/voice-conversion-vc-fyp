#!/usr/bin/env bash
# Fresh Ubuntu 22.04 GPU instance (g4dn.xlarge, Deep Learning AMI). From the project root run:
#   sudo HF_TOKEN=hf_xxx SPEAKERS=1 bash backend/aws/setup_server.sh
set -euo pipefail
: "${HF_TOKEN:?Set HF_TOKEN=hf_...}"
SPEAKERS="${SPEAKERS:-1}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
nvidia-smi >/dev/null || { echo "No NVIDIA driver found - use a Deep Learning AMI on a GPU instance"; exit 1; }

apt-get update -y
apt-get install -y ffmpeg git python3-venv python3-dev build-essential portaudio19-dev unzip

# ---- Applio (RVC) in its own venv ----
python3 -m venv /opt/venv-applio
/opt/venv-applio/bin/pip install -q -U pip uv
[ -d /opt/Applio ] || git clone --depth 1 https://github.com/IAHispano/Applio.git /opt/Applio
cd /opt/Applio
/opt/venv-applio/bin/uv pip install -q --python /opt/venv-applio/bin/python -r requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
/opt/venv-applio/bin/python core.py prerequisites --models --exe --pretraineds-hifigan

# ---- Seed-VC in its own venv ----
python3 -m venv /opt/venv-seedvc
/opt/venv-seedvc/bin/pip install -q -U pip uv
[ -d /opt/seed-vc ] || git clone --depth 1 https://github.com/Plachtaa/seed-vc.git /opt/seed-vc
cd /opt/seed-vc
/opt/venv-seedvc/bin/uv pip install -q --python /opt/venv-seedvc/bin/python torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
grep -viE "^(torch|torchvision|torchaudio)([=<>~ ]|$)" requirements.txt > req_notorch.txt
/opt/venv-seedvc/bin/uv pip install -q --python /opt/venv-seedvc/bin/python -r req_notorch.txt
/opt/venv-seedvc/bin/uv pip install -q --python /opt/venv-seedvc/bin/python librosa munch einops descript-audio-codec \
  pydub transformers soundfile hydra-core pyyaml "huggingface-hub>=0.28.1" scipy accelerate resemblyzer jiwer
/opt/venv-seedvc/bin/python "$ROOT/backend/aws/patch_bigvgan.py"

# ---- API (light venv) + models ----
python3 -m venv /opt/venv-api
/opt/venv-api/bin/pip install -q -U pip
/opt/venv-api/bin/pip install -q fastapi "uvicorn[standard]" python-multipart huggingface_hub
export MODELS_DIR=/opt/models/rvc SPEAKERS HF_TOKEN
/opt/venv-api/bin/python "$ROOT/backend/prep_models.py"
/opt/venv-api/bin/python "$ROOT/backend/prep_seedvc.py"

mkdir -p /opt/backend && cp "$ROOT/backend/main.py" /opt/backend/
cat > /etc/systemd/system/vc.service <<UNIT
[Unit]
Description=Voice conversion API
After=network.target
[Service]
WorkingDirectory=/opt/backend
Environment=APPLIO_DIR=/opt/Applio
Environment=APPLIO_PYTHON=/opt/venv-applio/bin/python
Environment=SEEDVC_DIR=/opt/seed-vc
Environment=SEEDVC_PYTHON=/opt/venv-seedvc/bin/python
Environment=MODELS_DIR=/opt/models/rvc
Environment=ENABLED_SPEAKERS=${SPEAKERS}
ExecStart=/opt/venv-api/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now vc
sleep 6; curl -s localhost:8000/health; echo
