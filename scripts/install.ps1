param(
    [switch]$RegisterOpenClaw
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv $Venv
}

& $Python -m pip install -e $Root

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $Root "src"
    & $Python -m unittest discover -s (Join-Path $Root "tests") -v
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($RegisterOpenClaw) {
    $DataDir = Join-Path $Root ".cnws-data"
    openclaw mcp set cn-web-search (@{
        command = $Python
        args = @("-m", "cn_web_search_mcp")
        cwd = $Root
        env = @{ CNWS_DATA_DIR = $DataDir }
    } | ConvertTo-Json -Compress)
    openclaw mcp doctor cn-web-search --probe
}
