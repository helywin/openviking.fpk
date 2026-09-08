FROM ghcr.io/volcengine/openviking:v0.4.16@sha256:46f9e34cd37238c28cbd9535033773d179006bdf7f3e528dd1c46567abce7701
# Build a compatible wheel inside the image; never compile during NAS installation.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1 \
    && /app/.venv/bin/python -m ensurepip \
    && CMAKE_BUILD_PARALLEL_LEVEL=4 CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_CUDA=OFF" /app/.venv/bin/python -m pip install --no-cache-dir llama-cpp-python==0.3.35 diskcache==5.6.3 \
    && apt-get purge -y --auto-remove build-essential cmake \
    && rm -rf /var/lib/apt/lists/* \
    && /app/.venv/bin/python -c "import llama_cpp; assert llama_cpp.Llama"
ENV OPENVIKING_WITH_BOT=0
