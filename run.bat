@echo off
rem Runs the same entry point a packaged build runs: the modern shell by
rem default, with `run.bat --classic` for the original window.
cd /d "%~dp0"
set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PY%" (
  "%BUNDLED_PY%" main.py %*
) else (
  python main.py %*
)
