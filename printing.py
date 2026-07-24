# -*- coding: utf-8 -*-
"""
Excelの「印刷」シート（A1:A15結合＝氏名、B1:B15結合＝金額、縦書き・行書体・
中央揃え・下揃え）と同じ見た目のレシート画像を作り、Windowsのプリンタへ
送るモジュール。

ポイント：
- 見た目の再現は PIL(Pillow) で画像を組み立てる方式にしている。
  Excelのセル結合＋縦書き設定を直接コードで再現するより、
  「1枚の絵を作ってそのまま印刷する」方が調整も配布も簡単。
- 実際のプリンタへの送信は pywin32 (win32print/win32ui) を使う。
  Windows専用なので、開発中の動作確認(プレビュー)は画像保存だけで行い、
  印刷だけ本番のWindows機で確認する想定。
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from kanji import to_receipt_string

# ==== 見た目の設定（Excel側のレイアウトに合わせて調整可） ====
CANVAS_SIZE = (900, 1400)          # 用紙内でのレシート領域(px)
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\HGGYOSOTF.ttc",  # HG行書体（環境によりファイル名が違う場合あり）
    r"C:\Windows\Fonts\HGGYOSOTF.TTC",
    r"C:\Windows\Fonts\yumin.ttf",      # 游明朝（代替）
    r"C:\Windows\Fonts\msmincho.ttc",   # MS明朝（代替）
]

SETTINGS_PATH = Path(__file__).with_name("layout_settings.json")

# レイアウトのデフォルト値。
# ・center_x / bottom_y はキャンバスに対する割合(%)
# ・height_ratio は「用紙の縦の長さに対して何%の高さで文字を並べるか」。
#   文字数(桁数)が変わっても、この比率になるようフォントサイズを自動計算する。
DEFAULT_SETTINGS = {
    "name_height_ratio": 30,     # 氏名は縦の30%
    "amount_height_ratio": 92,   # 金額はほぼ用紙いっぱい
    "name_center_x": 25,         # % … 氏名は左側
    "name_bottom_y": 95,         # %
    "amount_center_x": 68,       # % … 金額は右側
    "amount_bottom_y": 95,       # %
    "line_gap": 6,
    "min_font_size": 12,
    "max_font_size": 400,
}


def load_settings() -> dict:
    """保存済みのレイアウト設定を読み込む。無ければデフォルトを返す。"""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)
            return settings
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # どのフォントも見つからない場合はデフォルトフォント（見た目は簡素になる）
    return ImageFont.load_default()


def _stack_height(draw, text, font, line_gap):
    sizes = [draw.textbbox((0, 0), ch, font=font) for ch in text]
    heights = [b[3] - b[1] for b in sizes]
    return sum(heights) + line_gap * (len(text) - 1)


def _fit_font_size(draw, text, target_height, line_gap,
                    min_size: int = 12, max_size: int = 400):
    """縦に並べた時の合計の高さが target_height 以下になる、
    最大のフォントサイズを二分探索で求める。"""
    if not text:
        return min_size
    lo, hi, best = min_size, max_size, min_size
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _load_font(mid)
        h = _stack_height(draw, text, font, line_gap)
        if h <= target_height:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _draw_vertical_text(draw: ImageDraw.ImageDraw, text: str, font,
                         center_x: int, bottom_y: int, line_gap: int = 6):
    """1文字ずつ縦に並べて描画する（簡易縦書き）。"""
    sizes = [draw.textbbox((0, 0), ch, font=font) for ch in text]
    heights = [b[3] - b[1] for b in sizes]
    widths = [b[2] - b[0] for b in sizes]
    total_h = sum(heights) + line_gap * (len(text) - 1)

    y = bottom_y - total_h
    for ch, h, w in zip(text, heights, widths):
        x = center_x - w // 2
        draw.text((x, y), ch, font=font, fill="black")
        y += h + line_gap


def build_receipt_image(name: str, honorific: str, amount: int,
                         out_path: str = "receipt_preview.png",
                         settings: dict | None = None) -> str:
    """レシート画像を作成し、保存したパスを返す。

    settings を渡すとフォントサイズ・位置をその場で変えられる
    (プレビュー画面のスライダーから呼ばれる想定)。省略時は保存済み
    設定 (無ければデフォルト) を使う。
    """
    if settings is None:
        settings = load_settings()

    honorific = honorific or "様"
    img = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(img)

    line_gap = int(settings.get("line_gap", 6))
    min_size = int(settings.get("min_font_size", 12))
    max_size = int(settings.get("max_font_size", 400))

    name_text = f"{name}{honorific}"
    amount_text = to_receipt_string(amount)

    # 高さの比率(%) → 実際のpx → その高さに収まる最大フォントサイズ、の順で決める。
    # こうすると文字数(桁数)が変わっても常に指定した比率の高さで表示される。
    name_target_h = CANVAS_SIZE[1] * settings["name_height_ratio"] / 100
    amount_target_h = CANVAS_SIZE[1] * settings["amount_height_ratio"] / 100

    name_size = _fit_font_size(draw, name_text, name_target_h, line_gap, min_size, max_size)
    amount_size = _fit_font_size(draw, amount_text, amount_target_h, line_gap, min_size, max_size)

    # 氏名（左側の列）
    _draw_vertical_text(draw, name_text, _load_font(name_size),
                         center_x=int(CANVAS_SIZE[0] * settings["name_center_x"] / 100),
                         bottom_y=int(CANVAS_SIZE[1] * settings["name_bottom_y"] / 100),
                         line_gap=line_gap)

    # 金額（右側の列、大字表記）
    _draw_vertical_text(draw, amount_text, _load_font(amount_size),
                         center_x=int(CANVAS_SIZE[0] * settings["amount_center_x"] / 100),
                         bottom_y=int(CANVAS_SIZE[1] * settings["amount_bottom_y"] / 100),
                         line_gap=line_gap)

    img.save(out_path)
    return out_path


def print_image_windows(image_path: str, printer_name: str | None = None):
    """
    生成した画像をWindowsのプリンタへ送る。
    Windows環境かつ pywin32 (pip install pywin32) が必要。
    """
    import win32print
    import win32ui
    from PIL import ImageWin

    if printer_name is None:
        printer_name = win32print.GetDefaultPrinter()

    img = Image.open(image_path)

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    hdc.StartDoc(image_path)
    hdc.StartPage()

    printable_area = hdc.GetDeviceCaps(8), hdc.GetDeviceCaps(10)  # HORZRES, VERTRES
    scale = min(printable_area[0] / img.width, printable_area[1] / img.height)
    w, h = int(img.width * scale), int(img.height * scale)

    dib = ImageWin.Dib(img)
    dib.draw(hdc.GetHandleOutput(), (0, 0, w, h))

    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()


if __name__ == "__main__":
    path = build_receipt_image("山田太郎", "様", 30000)
    print("preview saved to", path)
