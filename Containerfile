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
        # general utilities
        findutils which \
    && dnf clean all

# ── Python packages ──────────────────────────────────────────────────
RUN pip3 install --no-cache-dir weasyprint pyyaml openpyxl

# ── stitchmd (Go binary) ────────────────────────────────────────────
ENV GOPATH=/usr/local/go
RUN go install go.abhg.dev/stitchmd@latest \
    && ln -s /usr/local/go/bin/stitchmd /usr/local/bin/stitchmd \
    && rm -rf /root/go /usr/local/go/pkg /usr/local/go/src

# ── mermaid-cli ──────────────────────────────────────────────────────
RUN npm install -g @mermaid-js/mermaid-cli --unsafe-perm \
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
ENV ELECTRON_DISABLE_SANDBOX=1
RUN printf '#!/bin/bash\nexec xvfb-run -a /usr/bin/drawio "$@" 2>&1 | grep -v -E "^\\[|Checking for beta|Found package-type|^/workspace/"\n' \
        > /usr/local/bin/drawio \
    && chmod +x /usr/local/bin/drawio

# ── Toolkit entrypoint + setup script ────────────────────────────────
COPY scripts/entrypoint.sh /toolkit/entrypoint.sh
COPY scripts/setup_project.py /toolkit/setup_project.py
RUN chmod +x /toolkit/entrypoint.sh

# Puppeteer config: --no-sandbox required when running as root in container
RUN printf '{"args":["--no-sandbox","--disable-setuid-sandbox"]}\n' \
        > /toolkit/puppeteer.json

WORKDIR /workspace
ENTRYPOINT ["/toolkit/entrypoint.sh"]
CMD ["help"]
