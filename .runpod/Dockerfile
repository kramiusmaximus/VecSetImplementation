FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    RUNPOD_HANDLER=/workspace/.runpod/handler.py

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    build-essential \
    ninja-build \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libsm6 \
    && rm -rf /var/lib/apt/lists/*

COPY . /workspace

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /workspace/.runpod/requirements_serverless.txt \
    && pip install --no-cache-dir setuptools wheel ninja \
    && pip install --no-cache-dir git+https://github.com/NVlabs/nvdiffrast.git --no-build-isolation \
    && pip install --no-cache-dir torch-cluster -f https://pytorch-geometric.com/whl/torch-2.6.0+cu124.html \
    && pip install --no-cache-dir git+https://github.com/SarahWeiii/diso.git --no-build-isolation

CMD ["python", "-u", "/workspace/.runpod/handler.py"]
