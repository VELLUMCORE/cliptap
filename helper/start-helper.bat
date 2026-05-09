@echo off
<<<<<<< HEAD
setlocal
cd /d "%~dp0"
start "ClipTap Helper" pyw ClipTapHelper.pyw
=======
cd /d "%~dp0"
py ClipTapHelper.py --open
>>>>>>> 8059d7f (feat: add standalone web manager build)
