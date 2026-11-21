$GPT_SOVITS_DIR = "D:\v\GPT-SoVITS"
$HOST_ADDR      = "127.0.0.1"
$PORT           = 9880

$PYTHON_EXE = if (Test-Path "$GPT_SOVITS_DIR\runtime\python.exe") {
    "$GPT_SOVITS_DIR\runtime\python.exe"
} elseif (Test-Path "$GPT_SOVITS_DIR\.venv\Scripts\python.exe") {
    "$GPT_SOVITS_DIR\.venv\Scripts\python.exe"
} else {
    "python"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$GPT_SOVITS_DIR;$GPT_SOVITS_DIR\GPT_SoVITS"
chcp 65001 | Out-Null
Write-Host "Starting GPT-SoVITS API server on http://${HOST_ADDR}:${PORT} ..."
Push-Location $GPT_SOVITS_DIR
& $PYTHON_EXE "api_v2.py" -a $HOST_ADDR -p $PORT -c "GPT_SoVITS\configs\tts_infer_dimsum.yaml"
Pop-Location
