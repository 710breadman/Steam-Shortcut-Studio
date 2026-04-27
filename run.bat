@echo off
set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PY%" (
  "%BUNDLED_PY%" -m steam_shortcut_studio.app
) else (
  python -m steam_shortcut_studio.app
)
