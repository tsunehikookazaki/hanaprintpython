# -*- coding: utf-8 -*-
"""
町会 花代記録アプリ（Windows用スタンドアロン版）

元のExcel VBAの3ボタン
  ①記録して印刷 ②再印刷 ③当日集計
と、氏名の絞り込み検索コンボボックスを再現している。
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date

import db
import printing


class HanachoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("町会 花代記録")
        self.geometry("420x420")
        self.resizable(False, False)

        db.init_db()
        self._build_widgets()

    # ---------------------------------------------------------- UI構築
    def _build_widgets(self):
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="ブロック").grid(row=0, column=0, sticky="e", **pad)
        self.var_block = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_block, width=10).grid(
            row=0, column=1, sticky="w", **pad)

        ttk.Label(frm, text="班").grid(row=1, column=0, sticky="e", **pad)
        self.var_han = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_han, width=10).grid(
            row=1, column=1, sticky="w", **pad)

        ttk.Label(frm, text="氏名（検索可）").grid(row=2, column=0, sticky="e", **pad)
        self.var_name = tk.StringVar()
        self.combo_name = ttk.Combobox(frm, textvariable=self.var_name, width=22)
        self.combo_name.grid(row=2, column=1, sticky="w", **pad)
        self.combo_name.bind("<KeyRelease>", self._on_name_typed)
        self.combo_name.bind("<<ComboboxSelected>>", self._on_name_selected)

        ttk.Label(frm, text="金額").grid(row=3, column=0, sticky="e", **pad)
        self.var_amount = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_amount, width=12).grid(
            row=3, column=1, sticky="w", **pad)

        ttk.Label(frm, text="敬称").grid(row=4, column=0, sticky="e", **pad)
        self.var_honorific = tk.StringVar(value="様")
        ttk.Entry(frm, textvariable=self.var_honorific, width=6).grid(
            row=4, column=1, sticky="w", **pad)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=16)

        ttk.Button(btn_frame, text="①記録して印刷", width=16,
                   command=self.record_and_print).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(btn_frame, text="②再印刷", width=16,
                   command=self.reprint_only).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(btn_frame, text="③当日集計", width=16,
                   command=self.daily_summary).grid(row=1, column=0, columnspan=2, pady=4)

        self.status = tk.StringVar(value="準備完了")
        ttk.Label(self, textvariable=self.status, anchor="w",
                  relief="sunken").pack(fill="x", side="bottom")

    # ------------------------------------------------------ 検索コンボ
    def _on_name_typed(self, event):
        query = self.var_name.get()
        results = db.search_names(query)
        self.combo_name["values"] = [
            f"{n}｜ブロック{b}｜{h}班" for n, b, h in results
        ]
        self._search_results = results
        if results:
            self.combo_name.event_generate("<Down>")

    def _on_name_selected(self, event):
        idx = self.combo_name.current()
        if idx < 0 or idx >= len(getattr(self, "_search_results", [])):
            return
        name, block, han = self._search_results[idx]
        self.var_name.set(name)
        self.var_block.set(block)
        self.var_han.set(han)

    # ------------------------------------------------------ 入力取得
    def _get_inputs(self):
        name = self.var_name.get().strip()
        block = self.var_block.get().strip()
        han = self.var_han.get().strip()
        honorific = self.var_honorific.get().strip() or "様"
        amount_raw = self.var_amount.get().strip()

        if not name or not amount_raw:
            messagebox.showwarning("入力エラー", "氏名と金額は必須入力です。")
            return None
        try:
            amount = int(amount_raw)
        except ValueError:
            messagebox.showwarning("入力エラー", "金額は数字で入力してください。")
            return None
        return name, block, han, honorific, amount

    def _clear_inputs(self):
        self.var_block.set("")
        self.var_han.set("")
        self.var_name.set("")
        self.var_amount.set("")

    # ------------------------------------------------------ ①記録して印刷
    def record_and_print(self):
        values = self._get_inputs()
        if values is None:
            return
        name, block, han, honorific, amount = values

        if not self._preview_and_confirm(name, honorific, amount,
                                          note="印刷を実行し、データを登録しますか？"):
            self.status.set("キャンセルしました。データは登録されていません。")
            return

        self._do_print(name, honorific, amount)
        today = db.record_and_print(name, block, han, amount)
        messagebox.showinfo("完了", "印刷とデータの更新が完了しました。")
        self.status.set(f"{name} 様 / {amount:,}円 / {today} 記録・印刷済み")
        self._clear_inputs()

    # ------------------------------------------------------ ②再印刷
    def reprint_only(self):
        values = self._get_inputs()
        if values is None:
            return
        name, block, han, honorific, amount = values

        if not self._preview_and_confirm(
                name, honorific, amount,
                note="【再印刷】を実行しますか？\n（データシートは更新されません）"):
            self.status.set("キャンセルしました。")
            return

        self._do_print(name, honorific, amount)
        messagebox.showinfo("完了", "再印刷が完了しました。")
        self.status.set(f"{name} 様 を再印刷しました（データ未更新）")
        self._clear_inputs()

    # ------------------------------------------------------ ③当日集計
    def daily_summary(self):
        today_str = date.today().strftime("%Y/%m/%d")
        target = simpledialog.askstring(
            "寄付金の集計", f"集計する日付を入力してください。\n例：{today_str}",
            initialvalue=today_str, parent=self)
        if not target:
            return

        rows, total, count = db.get_by_print_date(target)
        if count == 0:
            messagebox.showinfo("集計結果", f"{target} の記録は見つかりませんでした。")
            return

        lines = [f"{r['name']}（{r['block']}-{r['han']}）: {r['amount']:,}円" for r in rows]
        body = "\n".join(lines)
        messagebox.showinfo(
            "集計結果",
            f"集計日：{target}\n寄付人数：{count}名\n集計金額：{total:,}円\n\n{body}"
        )
        self.status.set(f"{target} 集計：{count}名 / {total:,}円")

    # ------------------------------------------------------ 印刷共通処理
    def _preview_and_confirm(self, name, honorific, amount, note: str) -> bool:
        """
        レイアウト調整スライダー付きのプレビュー画面。
        「印刷する」を押すと settings.json に保存し、self._last_settings
        に確定値を残す（直後の _do_print で同じ値を使うため）。
        """
        settings = printing.load_settings()
        self._last_settings = settings  # 「キャンセル」時のフォールバック用

        result = {"confirmed": False}

        preview = tk.Toplevel(self)
        preview.title("印刷プレビュー（調整可）")
        preview.resizable(False, False)

        img_frame = ttk.Frame(preview)
        img_frame.grid(row=0, column=0, padx=10, pady=10)
        img_label = ttk.Label(img_frame)
        img_label.pack()

        def refresh():
            path = printing.build_receipt_image(name, honorific, amount,
                                                  settings=settings)
            img = tk.PhotoImage(file=path)
            img_label.configure(image=img)
            img_label.image = img  # 参照保持

        ctrl_frame = ttk.Frame(preview)
        ctrl_frame.grid(row=0, column=1, sticky="n", padx=10, pady=10)

        def add_slider(row, label, key, frm, to):
            ttk.Label(ctrl_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.DoubleVar(value=settings[key])

            def on_change(_evt=None, key=key, var=var):
                settings[key] = var.get()
                refresh()

            scale = ttk.Scale(ctrl_frame, from_=frm, to=to, orient="horizontal",
                               variable=var, length=180, command=lambda _v: on_change())
            scale.grid(row=row, column=1, pady=2)
            return var

        add_slider(0, "氏名 高さ(%)", "name_height_ratio", 5, 100)
        add_slider(1, "氏名 左右位置(%)", "name_center_x", 0, 100)
        add_slider(2, "氏名 下端位置(%)", "name_bottom_y", 20, 100)
        add_slider(3, "金額 高さ(%)", "amount_height_ratio", 5, 100)
        add_slider(4, "金額 左右位置(%)", "amount_center_x", 0, 100)
        add_slider(5, "金額 下端位置(%)", "amount_bottom_y", 20, 100)
        add_slider(6, "文字の間隔", "line_gap", 0, 30)

        def on_ok():
            printing.save_settings(settings)  # 次回もこの設定を使う
            self._last_settings = settings
            result["confirmed"] = True
            preview.destroy()

        def on_cancel():
            preview.destroy()

        btn_frame = ttk.Frame(ctrl_frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=16)
        ttk.Button(btn_frame, text="印刷する", command=on_ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="キャンセル", command=on_cancel).pack(side="left", padx=4)
        ttk.Label(ctrl_frame, text=note, wraplength=200).grid(
            row=8, column=0, columnspan=2, pady=8, sticky="w")

        refresh()
        preview.transient(self)
        preview.grab_set()
        self.wait_window(preview)
        return result["confirmed"]

    def _do_print(self, name, honorific, amount):
        settings = getattr(self, "_last_settings", None) or printing.load_settings()
        path = printing.build_receipt_image(name, honorific, amount, settings=settings)
        try:
            printing.print_image_windows(path)
        except ImportError:
            messagebox.showwarning(
                "印刷スキップ",
                "pywin32 が見つからないため実際の印刷は行われていません。\n"
                "pip install pywin32 を実行してください。")
        except Exception as e:
            messagebox.showerror("印刷エラー", f"印刷に失敗しました：\n{e}")


if __name__ == "__main__":
    app = HanachoApp()
    app.mainloop()
