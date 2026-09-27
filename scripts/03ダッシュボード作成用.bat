@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

set "CONFIG=%~1"
set "TARGET=%~2"

if "%CONFIG%"=="" if "%TARGET%"=="" (
  for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\pick_file.ps1" -Filter "Data source config (*.yaml;*.yml)^|*.yaml;*.yml" -Title "Select data source config (yaml)"`) do set "CONFIG=%%F"
  if "!CONFIG!"=="" goto :cancelled
  for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select target workbook (.twb/.twbx)"`) do set "TARGET=%%F"
  if "!TARGET!"=="" goto :cancelled
)

if "!CONFIG!"=="" goto :missing
if "!TARGET!"=="" goto :missing

uv run --no-sync python scripts\03_apply_dashboard.py "!CONFIG!" "!TARGET!"
goto :end

:cancelled
echo No file selected.
goto :end

:missing
echo Both a config yaml and a workbook are required.

:end
endlocal
