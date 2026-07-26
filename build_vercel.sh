#!/usr/bin/env bash
#
# build_vercel.sh
# ===============
# Builds the WebAssembly version of Zombie War inside Vercel's build container.
# Referenced by vercel.json as the project's buildCommand.
#
# You do not need this file to work on the game locally - use build_web.py.
#
set -euo pipefail

echo "==> python: $(python3 --version 2>&1)"

# Vercel's Python is managed by uv, so a plain "pip install" is refused with
# PEP 668 "externally-managed-environment".  Build inside a throwaway virtual
# environment instead, and fall back to --break-system-packages if the venv
# module is not available in the image.
if python3 -m venv /tmp/zwbuild >/dev/null 2>&1; then
    PY=/tmp/zwbuild/bin/python
    echo "==> installing pygbag into a build venv"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet pygbag
else
    echo "==> venv unavailable; installing pygbag with --break-system-packages"
    PY=python3
    "$PY" -m pip install --quiet --break-system-packages pygbag
fi

echo "==> building the web bundle"
"$PY" build_web.py

# Fail loudly rather than publishing an empty site.
if [ ! -f zombie-war-web/index.html ]; then
    echo "ERROR: build produced no zombie-war-web/index.html" >&2
    exit 1
fi

echo "==> build ok:"
ls -la zombie-war-web
