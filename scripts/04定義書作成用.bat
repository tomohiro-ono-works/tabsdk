@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0.."

set "TARGET=%~1"
if "%TARGET%"=="" (
  for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select workbook (.twb/.twbx)"`) do set "TARGET=%%F"
)
if "%TARGET%"=="" (
  echo No file selected.
  goto :end
)

set "OUTPUT=%~2"
if "%OUTPUT%"=="" (
  for %%F in ("%TARGET%") do set "OUTPUT=%%~dpnF_definition.xlsx"
)

uv run --no-sync python scripts\04_export_definitions.py "%TARGET%" "%OUTPUT%"
if errorlevel 1 (
  echo Export failed. See error above.
  pause
  goto :end
)

if exist "%OUTPUT%" (
  start "" "%OUTPUT%"
) else (
  echo Output file not found: %OUTPUT%
  pause
)

:end
endlocal
