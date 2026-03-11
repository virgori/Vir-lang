# ═══════════════════════════════════════════════════════════════════
# Vir Language — Multi-Architecture Docker Build
# ═══════════════════════════════════════════════════════════════════
# Supports: linux/amd64 (x86_64), linux/arm64 (aarch64)
#
# Build:
#   docker build -t vir:latest .
#   docker buildx build --platform linux/amd64,linux/arm64 -t vir:latest .
#
# Run:
#   docker run --rm vir:latest vir --version
#   docker run --rm -v $(pwd)/myapp:/app vir:latest vir /app/main.vir
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Build native library ─────────────────────────────────
FROM debian:bookworm-slim AS native-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/core
COPY core/ .

RUN make clean && make all && make test \
    && echo "── Native build artifacts ──" && ls -la lib/

# ── Stage 2: Build Python package + stdlib ────────────────────────
FROM python:3.11-slim-bookworm AS wheel-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY . .

# Inject native lib from Stage 1
COPY --from=native-builder /build/core/lib/libvir_core.so src/native/lib/
COPY --from=native-builder /build/core/lib/libvir_core.a  src/native/lib/

# Install build tools + build wheel
RUN pip install --no-cache-dir build setuptools wheel \
    && python -m build --wheel --outdir /wheels \
    && ls -la /wheels/

# Compile stdlib
RUN pip install --no-cache-dir -e . \
    && python -m scripts.build_stdlib --arch "$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x86_64/')" \
    || echo "stdlib build skipped"

# ── Stage 3: Runtime image ────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="Vir Team"
LABEL description="Vir Language Runtime v0.3.0"
LABEL org.opencontainers.image.source="https://github.com/vir-lang/vir"

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r vir && useradd -r -g vir -d /home/vir -m vir

# Install wheel from builder
COPY --from=wheel-builder /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# Copy native lib to system path
COPY --from=native-builder /build/core/lib/libvir_core.so /usr/local/lib/
RUN ldconfig

# Copy compiled stdlib
COPY --from=wheel-builder /build/build/stdlib/ /usr/local/share/vir/stdlib/ 2>/dev/null || true
COPY stdlib/ /usr/local/share/vir/stdlib/src/

# Copy CLI binary
COPY --from=native-builder /build/core/build/vir /usr/local/bin/vir-native
RUN chmod +x /usr/local/bin/vir-native 2>/dev/null || true

# Default config
COPY packaging/linux/vir.conf /etc/vir/vir.conf 2>/dev/null || true

ENV VIR_HOME=/usr/local/share/vir
ENV VIR_STDLIB_PATH=/usr/local/share/vir/stdlib

USER vir
WORKDIR /home/vir

ENTRYPOINT ["vir"]
CMD ["--help"]
