$ErrorActionPreference = "Stop"
# Runs the same entry point a packaged build runs: the modern shell, which is
# the only interface.
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $BundledPython) {
    & $BundledPython main.py @args
} else {
    python main.py @args
}
