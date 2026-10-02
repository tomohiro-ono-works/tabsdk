@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo tabsdk
echo 1: twbファイルから設計ページを生成する
echo 2: twbファイルと設計ページから設計ページを改修する
echo 3: twbファイルと設計ページからtwbファイルを生成する
echo.
set /p CHOICE="選択 (1/2/3): "

if "%CHOICE%"=="1" goto :datasource
if "%CHOICE%"=="2" goto :config
if "%CHOICE%"=="3" goto :dashboard
echo 1 / 2 / 3 のいずれかを入力してください。
goto :end

:datasource
for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select workbook (.twb/.twbx)"`) do set "TARGET=%%F"
if "!TARGET!"=="" (
  echo ファイルが選ばれませんでした。
  goto :end
)
for %%F in ("!TARGET!") do set "OUTPUT=%%~dpnF_config.html"
uv run --no-sync python scripts/01_export_html.py "!TARGET!"
if errorlevel 1 (
  echo 失敗しました。上のエラーを確認してください。
  pause
  goto :end
)
if exist "!OUTPUT!" (
  start "" "!OUTPUT!"
) else (
  echo 出力が見つかりません: !OUTPUT!
  pause
)
goto :end

:config
for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/pick_file.ps1" -Filter "Data source config (*.yaml;*.yml)^|*.yaml;*.yml" -Title "Select data source config (yaml)"`) do set "CONFIG=%%F"
if "!CONFIG!"=="" (
  echo ファイルが選ばれませんでした。
  goto :end
)
for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select target workbook (.twb/.twbx)"`) do set "TARGET=%%F"
if "!TARGET!"=="" (
  echo ファイルが選ばれませんでした。
  goto :end
)
for %%F in ("!TARGET!") do set "OUTPUT=%%~dpnF_config.html"
uv run --no-sync python scripts/02_apply_config_html.py "!CONFIG!" "!TARGET!"
if errorlevel 1 (
  echo 失敗しました。上のエラーを確認してください。
  pause
  goto :end
)
if exist "!OUTPUT!" (
  start "" "!OUTPUT!"
) else (
  echo 出力が見つかりません: !OUTPUT!
  pause
)
goto :end

:dashboard
for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/pick_file.ps1" -Filter "Data source config (*.yaml;*.yml)^|*.yaml;*.yml" -Title "Select data source config (yaml)"`) do set "CONFIG=%%F"
if "!CONFIG!"=="" (
  echo ファイルが選ばれませんでした。
  goto :end
)
for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/pick_file.ps1" -Filter "Tableau Workbook (*.twb;*.twbx)^|*.twb;*.twbx" -Title "Select target workbook (.twb/.twbx)"`) do set "TARGET=%%F"
if "!TARGET!"=="" (
  echo ファイルが選ばれませんでした。
  goto :end
)
for %%F in ("!TARGET!") do set "OUTPUT=%%~dpnF_dashboard.twb"
uv run --no-sync python scripts/03_apply_dashboard.py "!CONFIG!" "!TARGET!"
if errorlevel 1 (
  echo 失敗しました。上のエラーを確認してください。
  pause
  goto :end
)
if not exist "!OUTPUT!" (
  echo 出力が見つかりません: !OUTPUT!
  pause
  goto :end
)
echo.
set /p OPEN="Tableau で開きますか？ (1:はい / それ以外:いいえ): "
if "!OPEN!"=="1" start "" "!OUTPUT!"

:end
endlocal
