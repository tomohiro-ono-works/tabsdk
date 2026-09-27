param(
    [string]$Filter = "All files (*.*)|*.*",
    [string]$Title = "Select a file"
)

# このファイルは UTF-8 の BOM 付きで保存する（2026-09-21）。
# PowerShell 5.1 は BOM の無い .ps1 を ANSI として読むため、BOM を外すと
# ここの日本語が壊れ、スクリプト全体が構文エラーになる。

# 選んだパスは bat の for /f が受け取る。cmd はコンソールの既定コードページ
# （日本語 Windows は 932）で読むので、出力もそれに合わせる。
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(
        [System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
} catch {
    $null = $_   # 変更できない環境では既定のまま使う
}

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = $Filter
$dialog.Title = $Title
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.FileName
}
