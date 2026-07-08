$ErrorActionPreference = "Stop"

Write-Host "TTB LabelScan CLI - local ONNX installation" -ForegroundColor Cyan

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating Python 3.8 virtual environment..."
    py -3.8 -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install --no-cache-dir -r requirements.txt

Write-Host ""
Write-Host "Verifying imports..."
& $python -c "from rapidocr import RapidOCR; import onnxruntime, cv2, PIL, rapidfuzz; print('All runtime imports succeeded.')"

Write-Host ""
Write-Host "Running generated OCR self-test..."
& $python labelscan_cli.py self-test

Write-Host ""
Write-Host "Installation and self-test completed." -ForegroundColor Green
