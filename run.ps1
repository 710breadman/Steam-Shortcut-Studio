$ErrorActionPreference = "Stop"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $BundledPython) {
    & $BundledPython -m steam_shortcut_studio.app
} else {
    python -m steam_shortcut_studio.app
}
