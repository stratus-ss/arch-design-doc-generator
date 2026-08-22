# Arch Design Doc Generator — all-in-one build image
#
# Contains: pandoc, weasyprint, stitchmd, drawio-desktop (xvfb),
#           mermaid-cli, Python 3 + pyyaml/openpyxl
#
# Build:   podman build -t arch-doc-gen .
# Run:     podman run --rm -v .:/workspace:Z arch-doc-gen <command>

FROM registry.fedoraproject.org/fedora:43 AS base

# ── System packages ──────────────────────────────────────────────────
RUN dnf install -y --setopt=install_weak_deps=False \
        python3 python3-pip \
        pandoc \
        xorg-x11-server-Xvfb \
        nodejs npm \
        golang \
        curl \
        # weasyprint system deps
        cairo pango gdk-pixbuf2 \
        libffi-devel \
        # drawio runtime deps (Electron)
        alsa-lib atk at-spi2-atk cups-libs libdrm mesa-libgbm \
        gtk3 nss libXcomposite libXdamage libXrandr libxkbcommon \
        # general utilities (unzip required by puppeteer chrome extract)
        findutils which unzip \
    && dnf clean all

# ── Python packages ──────────────────────────────────────────────────
RUN pip3 install --no-cache-dir weasyprint==66.0 pyyaml==6.0.3 openpyxl==3.1.5 tomli>=2.0 curl_cffi

# ── stitchmd (Go binary) ────────────────────────────────────────────
ENV GOPATH=/usr/local/go
RUN go install go.abhg.dev/stitchmd@v0.9.0 \
    && ln -s /usr/local/go/bin/stitchmd /usr/local/bin/stitchmd \
    && rm -rf /root/go /usr/local/go/pkg /usr/local/go/src

# ── mermaid-cli ──────────────────────────────────────────────────────
RUN npm install -g @mermaid-js/mermaid-cli@11.16.0 --unsafe-perm \
    && npm cache clean --force

# ── drawio-desktop ───────────────────────────────────────────────────
ARG DRAWIO_VERSION=26.2.2
RUN curl -fsSL \
        "https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-x86_64-${DRAWIO_VERSION}.rpm" \
        -o /tmp/drawio.rpm \
    && dnf install -y /tmp/drawio.rpm \
    && rm -f /tmp/drawio.rpm \
    && dnf clean all

# Wrapper so scripts can call `drawio` and get headless xvfb.
# ELECTRON_DISABLE_SANDBOX avoids --no-sandbox being parsed as a file argument.
# HOME/XDG under /tmp: Electron otherwise tries mkdir on /workspace (the bind
# mount) and fails with "Permission denied", aborting export mid-batch.
# Grep filters noise; do not let grep's "no matches" exit 1 fail callers —
# export_drawio.sh treats a missing PNG as the real failure.
ENV ELECTRON_DISABLE_SANDBOX=1
RUN printf '%s\n' \
        '#!/bin/bash' \
        'export HOME=/tmp' \
        'export XDG_CONFIG_HOME=/tmp/.config' \
        'export XDG_CACHE_HOME=/tmp/.cache' \
        'mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"' \
        'xvfb-run -a /usr/bin/drawio "$@" 2>&1 | grep -v -E "^\[|Checking for beta|Found package-type|^/workspace/" || true' \
        'exit 0' \
        > /usr/local/bin/drawio \
        && chmod +x /usr/local/bin/drawio

# ── Immutable templates (also available on /workspace via bind mount) ─
COPY templates/ /toolkit/templates/

# ── HLD/LLD build pipeline scripts (host-only AI scripts excluded) ───
COPY scripts/hld_lld/build/ /toolkit/hld_lld/build/
COPY scripts/hld_lld/lld_to_workitems.py /toolkit/hld_lld/lld_to_workitems.py

# ── RVTools migration schedule scripts ───────────────────────────────
COPY scripts/rvtools/ /toolkit/rvtools/

# ── Shared Python libraries ──────────────────────────────────────────
COPY scripts/shared/ /toolkit/shared/

# ── Health Check report engine ─────────────────────────────────────
COPY scripts/health_check/ /toolkit/health_check/

# ── Toolkit entrypoint + setup script ────────────────────────────────
COPY scripts/entrypoint.sh /toolkit/entrypoint.sh
COPY scripts/setup_project.py /toolkit/setup_project.py
COPY scripts/setup_status.py /toolkit/setup_status.py
RUN chmod +x /toolkit/entrypoint.sh

# Puppeteer config: --no-sandbox required when running as root in container
RUN printf '{"args":["--no-sandbox","--disable-setuid-sandbox"]}\n' \
        > /toolkit/puppeteer.json

ARG SCRIPTS_HASH=unknown
LABEL org.opencontainers.image.scripts-hash=$SCRIPTS_HASH
LABEL org.opencontainers.image.title="arch-doc-gen" \
      org.opencontainers.image.description="Config-driven document automation toolkit for architecture engagements — HLD/LLD, diagrams, PDFs, work items" \
      org.opencontainers.image.licenses="GPL-3.0-only"

WORKDIR /workspace
ENTRYPOINT ["/toolkit/entrypoint.sh"]
CMD ["help"]
