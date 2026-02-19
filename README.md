# VecSetEdit GUI (Local)

This repo provides a Gradio web UI (`app.py`) to run VecSetEdit locally on a Linux GPU machine.

## Requirements

- Linux
- NVIDIA GPU with CUDA 12.4
- Python 3.11

## Install (GUI Mode Only)

Use a fresh environment and **install in this order**:

```bash
# 1) Create and activate env (conda or venv)
conda create -n vecset_edit python=3.11 -y
conda activate vecset_edit

# 2) Install PyTorch CUDA 12.4 (must be first)
pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 torchaudio==2.6.0+cu124 \
  --index-url https://download.pytorch.org/whl/cu124

# 3) CUDA-dependent build tools
pip install setuptools wheel ninja

# 4) nvdiffrast (from source)
pip install git+https://github.com/NVlabs/nvdiffrast.git --no-build-isolation

# 5) torch-cluster (matching PyTorch/CUDA)
pip install torch-cluster -f https://pytorch-geometric.com/whl/torch-2.6.0+cu124.html

# 6) diso (from source)
pip install git+https://github.com/SarahWeiii/diso.git --no-build-isolation

# 7) App + core deps
pip install -r requirements.txt
```

## Run the GUI

```bash
python app.py
```

Open:
```
http://localhost:7860
```

## Notes

- If you see CUDA build errors, confirm your system has CUDA 12.4 and a compatible GPU driver.
- Large model weights are downloaded automatically when the pipeline runs.
