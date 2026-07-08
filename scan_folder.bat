@echo off
if "%~1"=="" (
  echo Drag a folder of label images onto this file.
  pause
  exit /b 2
)
.\.venv\Scripts\python.exe labelscan_cli.py scan "%~1" --workers 2 --limit 50
pause
