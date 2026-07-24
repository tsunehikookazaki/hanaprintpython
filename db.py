# -*- coding: utf-8 -*-
"""
寄付データを保持する CSV データ管理モジュール（SQLite不要版）。
元の Excel「データ」シートの列構成 (A:ブロック, B:班, C:氏名, D:最新金額,
E:最新日付, F:過去金額, G:過去日付, H:印刷日, I:印刷状態) を
そのままCSVの列に対応させている。

- データ件数は最大でも数百件程度を想定（CSVを毎回全件読み書きする単純な実装）
- 文字コードは Excel でもそのまま開けるように utf-8-sig（BOM付き）にしている
- 中身はテキストなので、いざという時はメモ帳やExcelで直接確認・修正できる
"""
import csv
from datetime import date
from pathlib import Path

CSV_PATH = Path(__file__).with_name("hanacho.csv")

FIELDNAMES = [
    "block", "han", "name", "amount", "donate_date",
    "prev_amount", "prev_date", "print_date", "print_status",
]


def init_db():
    """CSVファイルが無ければヘッダー付きで新規作成する。"""
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def _read_all():
    init_db()
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_all(rows):
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def search_names(query: str, limit: int = 20):
    """氏名の部分一致検索。ComboBox1_Change の絞り込み処理に相当。"""
    if not query:
        return []
    rows = _read_all()
    seen = set()
    results = []
    for r in rows:
        if query in r["name"]:
            key = (r["name"], r["block"], r["han"])
            if key not in seen:
                seen.add(key)
                results.append(key)
            if len(results) >= limit:
                break
    return results


def find_person(name: str, block: str, han: str):
    rows = _read_all()
    for r in rows:
        if r["name"] == name and r["block"] == block and r["han"] == han:
            return r
    return None


def record_and_print(name: str, block: str, han: str, amount: int):
    """記録して印刷。既存データがあれば旧データを過去欄へスライドする。"""
    today = date.today().strftime("%Y/%m/%d")
    rows = _read_all()

    target = None
    for r in rows:
        if r["name"] == name and r["block"] == block and r["han"] == han:
            target = r
            break

    if target:
        target["prev_amount"] = target.get("amount", "")
        target["prev_date"] = target.get("donate_date", "")
        target["amount"] = amount
        target["donate_date"] = today
        target["print_date"] = today
        target["print_status"] = "印刷済み"
    else:
        rows.append({
            "block": block, "han": han, "name": name,
            "amount": amount, "donate_date": today,
            "prev_amount": "", "prev_date": "",
            "print_date": today, "print_status": "印刷済み",
        })

    _write_all(rows)
    return today


def get_by_print_date(target_date: str):
    """当日集計。print_date が target_date のものを返す。"""
    rows = _read_all()
    matched = [r for r in rows if r.get("print_date") == target_date]
    matched.sort(key=lambda r: (r["block"], r["han"], r["name"]))
    total = sum(_to_int(r.get("amount")) for r in matched)

    # main.py 側で r["amount"] を数値として扱えるように変換しておく
    for r in matched:
        r["amount"] = _to_int(r.get("amount"))

    return matched, total, len(matched)


if __name__ == "__main__":
    init_db()
    print("CSV initialized at", CSV_PATH)
