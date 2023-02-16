# Do not invoke `docker build` directly; use `make images` (in the root dir of this repo).

ARG BCC_TAG=latest
ARG SRC_DIR=.
ARG DIST_DIR=dist/network-tracing

# TODO: Build artifacts in a separate stage; currently artifacts must be
#       pre-built and available under dist/ directory.

FROM ubuntu:22.04 AS runner
WORKDIR /
RUN apt-get update && \
    apt-get install -y \
    bison \
    build-essential \
    cmake \
    flex \
    git \
    libedit-dev \
    libllvm14 \
    llvm-14-dev \
    libclang-14-dev \
    python3 \
    zlib1g-dev \
    libelf-dev \
    libfl-dev \
    python3-distutils \
    curl \
    python3-pip \
    jq \
    moreutils \
    && \
    rm -rf /var/lib/apt/lists/*
ARG BCC_TAG
RUN (curl -fL "https://github.com/iovisor/bcc/releases/download/$BCC_TAG/bcc-src-with-submodule.tar.gz" | tar xvzf -) && \
    mkdir -p /bcc/build && \
    cd /bcc/build && \
    cmake -DPYTHON_CMD=python3 .. && \
    make -j$(nproc) && \
    make install && \
    cd /bcc/build/src/python && \
    make -j$(nproc) && \
    make install && \
    rm -rf /bcc
ARG SRC_DIR
COPY $SRC_DIR/setup.py /src/setup.py
RUN cd /src && \
    python3 -c "from setup import INSTALL_REQUIRES; import os; os.system('python3 -m pip install ' + ' '.join(INSTALL_REQUIRES))" && \
    rm -rf /src
ARG DIST_DIR
COPY $DIST_DIR /dist
RUN cd /dist && \
    python3 -m pip install *.whl && \
    rm -rf /dist
COPY $SRC_DIR/ops/build/entrypoint.sh /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "ntd" ]
