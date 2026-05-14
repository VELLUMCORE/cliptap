#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dist"
VERSION="${CLIPTAP_VERSION:-v1.3}"
SPECIFIC_ID="${CLIPTAP_SPECIFIC_ID:-62}"
if [ -n "${SPECIFIC_ID}" ]; then
  BASENAME="cliptap-${VERSION}-${SPECIFIC_ID}"
else
  BASENAME="cliptap-${VERSION}"
fi
rm -rf "${OUT}"
mkdir -p "${OUT}"
(cd "${ROOT}/extension" && zip -qr "${OUT}/${BASENAME}.xpi" .)
mkdir -p "${OUT}/chrome/cliptap"
cp -R "${ROOT}/extension/." "${OUT}/chrome/cliptap/"
(cd "${OUT}/chrome" && zip -qr "${OUT}/${BASENAME}-chrome.zip" cliptap)
(cd "${ROOT}/.." && zip -qr "${OUT}/${BASENAME}.zip" cliptap   -x "cliptap/.git/*"   -x "cliptap/.source-head"   -x "cliptap/dist/*"   -x "cliptap/build/*"   -x "cliptap/**/__pycache__/*"   -x "cliptap/**/*.pyc")
