## 課程初始化說明

採用 uv 來管理 Python 依賴與執行環境，請先安裝 uv（<https://uv.pypa.io/en/stable/installation/）。>
上課老師亦可以自行選擇熟悉的環境進行教學。
本教材內容，老師可以根據上課實際情況進行調整。

## copy 以下檔案

scripts/*.py (產生課程資料集的腳本)
textbook/*.md (每堂課的教材)
lessons/*.py (每堂課的範例程式碼與章末練習)
pyproject.toml
requirements.txt
uv.lock

## 1. 執行 `uv sync` 安裝依賴項目

## 2. 執行 `uv run python scripts/generate_course_data.py` 產生課程資料集

## 3. 執行每堂課範例 `uv run python lessons/lessonXX.py` XX 是章節號碼

## 4. 每堂課結束後，執行 `uv run python lessons/practice_chXX.py` 完成章末練習（XX 是章節號碼）
