ARG BASE_IMAGE=nvcr.io/nvidia/cuda
ARG BASE_TAG=12.2.2-devel-ubuntu22.04

FROM ${BASE_IMAGE}:${BASE_TAG} AS base
ARG CUDA_ARCH
ENV CUDA_ARCH=${CUDA_ARCH}

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    xz-utils \
    curl \
    git && \
    rm -rf /var/lib/apt/lists/*

FROM base AS devel
WORKDIR /root
COPY scripts/install-deps.sh /root
RUN bash install-deps.sh && rm install-deps.sh
COPY scripts/build-trt-llm.sh /root
RUN bash build-trt-llm.sh && rm build-trt-llm.sh

FROM devel AS release
WORKDIR /root/
COPY scripts/install-trt-llm.sh /root
RUN bash install-trt-llm.sh && rm install-trt-llm.sh
COPY scripts/build-melo.sh /root
RUN bash build-melo.sh && rm build-melo.sh
COPY scripts/setup-whisperfusion.sh /root/
ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
RUN ./setup-whisperfusion.sh --no-cache
