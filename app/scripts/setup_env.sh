#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${1:-python3}

echo "[1/3] 建立虛擬環境..."
$PYTHON_BIN -m venv .venv

source .venv/bin/activate

echo "[2/3] 安裝依賴..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/3] 完成環境初始化"


