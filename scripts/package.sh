#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dist"
VERSION="${CLIPTAP_VERSION:-v1.2}"
SPECIFIC_ID="${CLIPTAP_SPECIFIC_ID:-6}"
BASENAME="cliptap-${VERSION}-${SPECIFIC_ID}"
rm -rf "${OUT}"
mkdir -p "${OUT}"
(cd "${ROOT}/extension" && zip -qr "${OUT}/${BASENAME}.xpi" .)
mkdir -p "${OUT}/chrome/cliptap"
cp -R "${ROOT}/extension/." "${OUT}/chrome/cliptap/"
(cd "${OUT}/chrome" && zip -qr "${OUT}/${BASENAME}-chrome.zip" cliptap)
(cd "${ROOT}/.." && zip -qr "${OUT}/${BASENAME}.zip" cliptap   -x "cliptap/dist/*"   -x "cliptap/build/*"   -x "cliptap/**/__pycache__/*"   -x "cliptap/**/*.pyc")
