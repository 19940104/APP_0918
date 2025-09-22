param(
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/3] 建立虛擬環境..."
& $PythonPath -m venv .venv

Write-Host "[2/3] 啟用虛擬環境並安裝套件..."
$venvActivate = ".venv/Scripts/Activate.ps1"
if (!(Test-Path $venvActivate)) {
    throw "未找到虛擬環境啟用腳本：$venvActivate"
}
. $venvActivate
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "[3/3] 完成環境初始化"


