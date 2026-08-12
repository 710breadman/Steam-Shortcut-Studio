$ErrorActionPreference = "Stop"
# Runs the same entry point a packaged build runs: the modern shell by
# default, with `run.ps1 --classic` for the original window.
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $BundledPython) {
    & $BundledPython main.py @args
} else {
    python main.py @args
}
