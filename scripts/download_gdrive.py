#!/usr/bin/env python3
"""
Google Drive ETF Excel 下載器
==============================
使用 Service Account 從 Google Drive 下載 ETF 持股 Excel 檔案。

環境變數:
  GDRIVE_SERVICE_ACCOUNT_JSON  — Service Account 金鑰 JSON 內容
  GDRIVE_FOLDER_ID             — Google Drive 根資料夾 ID（FinanceData/history/ETF）

用法:
  python download_gdrive.py                   # 下載全部 ETF 最新 7 天
  python download_gdrive.py --days 30         # 下載最新 30 天
  python download_gdrive.py --etf 00981A      # 只下載指定 ETF
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ETF_IDS = ["00981A", "00980A", "00982A", "00991A", "00993A"]


def get_drive_service():
    """建立 Google Drive API 連線"""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    cred_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "")
    if not cred_json:
        print("ERROR: GDRIVE_SERVICE_ACCOUNT_JSON 未設定")
        sys.exit(1)

    cred_info = json.loads(cred_json)
    credentials = service_account.Credentials.from_service_account_info(
        cred_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=credentials)


def find_etf_folder(service, parent_id, etf_id):
    """在 parent 資料夾下找到 ETF 子資料夾"""
    query = (
        f"'{parent_id}' in parents "
        f"and name = '{etf_id}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def find_daily_xlsx_folder(service, etf_folder_id):
    """找到 daily_xlsx 子資料夾"""
    query = (
        f"'{etf_folder_id}' in parents "
        f"and name = 'daily_xlsx' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def list_xlsx_files(service, folder_id, days=7):
    """列出資料夾內的 xlsx 檔案"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat() + "Z"
    query = (
        f"'{folder_id}' in parents "
        f"and mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' "
        f"and trashed = false "
        f"and modifiedTime > '{cutoff}'"
    )
    results = service.files().list(
        q=query, fields="files(id, name, modifiedTime)", orderBy="modifiedTime desc"
    ).execute()
    return results.get("files", [])


def list_csv_files(service, folder_id):
    """列出資料夾內的 CSV Master 檔案"""
    query = (
        f"'{folder_id}' in parents "
        f"and name contains 'Master' "
        f"and trashed = false"
    )
    results = service.files().list(
        q=query, fields="files(id, name, modifiedTime)"
    ).execute()
    return results.get("files", [])


def download_file(service, file_id, dest_path):
    """下載單一檔案"""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    with open(dest_path, "wb") as f:
        f.write(fh.getvalue())


def download_etf(service, root_folder_id, etf_id, output_base, days=7):
    """下載單一 ETF 的資料"""
    print(f"\n📂 {etf_id}")

    etf_folder_id = find_etf_folder(service, root_folder_id, etf_id)
    if not etf_folder_id:
        print(f"  ⚠️ 找不到 {etf_id} 資料夾")
        return 0

    count = 0

    # 下載 daily_xlsx
    daily_folder_id = find_daily_xlsx_folder(service, etf_folder_id)
    if daily_folder_id:
        xlsx_files = list_xlsx_files(service, daily_folder_id, days=days)
        print(f"  找到 {len(xlsx_files)} 個 xlsx 檔案（最近 {days} 天）")

        for f in xlsx_files:
            dest = output_base / etf_id / "daily_xlsx" / f["name"]
            if dest.exists():
                continue
            download_file(service, f["id"], dest)
            print(f"  ✅ {f['name']}")
            count += 1
    else:
        print(f"  ⚠️ 找不到 daily_xlsx 資料夾")

    # 下載 Master CSV（非 00981A）
    if etf_id != "00981A":
        csv_files = list_csv_files(service, etf_folder_id)
        for f in csv_files:
            dest = output_base / etf_id / f["name"]
            download_file(service, f["id"], dest)
            print(f"  ✅ {f['name']}")
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Download ETF Excel from Google Drive")
    parser.add_argument("--days", type=int, default=7, help="下載最近 N 天的檔案")
    parser.add_argument("--etf", type=str, help="只下載指定 ETF")
    parser.add_argument("--output", type=str, default=None, help="輸出目錄")
    args = parser.parse_args()

    # 決定輸出路徑
    if args.output:
        output_base = Path(args.output)
    elif os.environ.get("GITHUB_ACTIONS") == "true":
        output_base = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "history" / "ETF"
    else:
        output_base = Path(__file__).resolve().parent.parent / "history" / "ETF"

    root_folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")
    if not root_folder_id:
        print("ERROR: GDRIVE_FOLDER_ID 未設定")
        sys.exit(1)

    print("🐺 Wolf Pack — Google Drive ETF 下載器")
    print(f"   輸出: {output_base}")
    print(f"   天數: {args.days}")

    service = get_drive_service()
    etf_list = [args.etf] if args.etf else ETF_IDS
    total = 0

    for etf_id in etf_list:
        total += download_etf(service, root_folder_id, etf_id, output_base, args.days)

    print(f"\n✅ 完成，共下載 {total} 個新檔案")


if __name__ == "__main__":
    main()
