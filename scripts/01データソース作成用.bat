@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

set "TARGET=%~1"
if "%TARGET%"=="" (
  for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select workbook (.twb/.twbx)"`) do set "TARGET=%%F"
)
if "!TARGET!"=="" (
  echo No file selected.
  goto :end
)

set "OUTPUT=%~2"
if "!OUTPUT!"=="" (
  for %%F in ("!TARGET!") do set "OUTPUT=%%~dpnF_config.html"
)

if "%~2"=="" (
  uv run --no-sync python scripts\01_export_html.py "!TARGET!"
) else (
  uv run --no-sync python scripts\01_export_html.py "!TARGET!" "%~2"
)
if errorlevel 1 (
  echo Export failed. See error above.
  pause
  goto :end
)

if exist "!OUTPUT!" (
  start "" "!OUTPUT!"
) else (
  echo Output file not found: !OUTPUT!
  pause
)

:end
endlocal
