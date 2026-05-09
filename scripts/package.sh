#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dist"
<<<<<<< HEAD
VERSION="1.1.7"
rm -rf "${OUT}"
mkdir -p "${OUT}"
(cd "${ROOT}/extension" && zip -qr "${OUT}/cliptap-v${VERSION}.xpi" .)
mkdir -p "${OUT}/chrome/cliptap"
cp -R "${ROOT}/extension/." "${OUT}/chrome/cliptap/"
(cd "${OUT}/chrome" && zip -qr "${OUT}/cliptap-v${VERSION}-chrome.zip" cliptap)
(cd "${ROOT}/.." && zip -qr "${OUT}/cliptap-v${VERSION}.zip" cliptap -x "cliptap/dist/*" "cliptap/**/__pycache__/*" "cliptap/**/*.pyc")
=======
rm -rf "${OUT}"
mkdir -p "${OUT}"
(cd "${ROOT}/extension" && zip -qr "${OUT}/cliptap.xpi" .)
mkdir -p "${OUT}/chrome/cliptap"
cp -R "${ROOT}/extension/." "${OUT}/chrome/cliptap/"
(cd "${OUT}/chrome" && zip -qr "${OUT}/cliptap-chrome.zip" cliptap)
(cd "${ROOT}/.." && zip -qr "${OUT}/cliptap.zip" cliptap \
  -x "cliptap/dist/*" \
  -x "cliptap/build/*" \
  -x "cliptap/**/__pycache__/*" \
  -x "cliptap/**/*.pyc")
>>>>>>> 8059d7f (feat: add standalone web manager build)
