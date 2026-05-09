#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dist"
VERSION="1.1.1"
rm -rf "${OUT}"
mkdir -p "${OUT}"
(cd "${ROOT}/extension" && zip -qr "${OUT}/cliptap-v${VERSION}.xpi" .)
mkdir -p "${OUT}/chrome/cliptap"
cp -R "${ROOT}/extension/." "${OUT}/chrome/cliptap/"
(cd "${OUT}/chrome" && zip -qr "${OUT}/cliptap-v${VERSION}-chrome.zip" cliptap)
(cd "${ROOT}/.." && zip -qr "${OUT}/cliptap-v${VERSION}.zip" cliptap -x "cliptap/dist/*" "cliptap/**/__pycache__/*" "cliptap/**/*.pyc")
