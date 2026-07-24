# -*- coding: utf-8 -*-
"""
金額を「大字（だいじ）」表記に変換するモジュール。
Excel の NumberFormatLocal '"一金"[DBNum2]G/標準"円也"' と同じ見た目を再現する。
例: 30000 -> "参萬円也" / 12345 -> "壱萬弐仟参佰四拾伍円也"
"""

_DIGITS = ["", "壱", "弐", "参", "四", "伍", "陸", "七", "八", "九"]
_SMALL_UNITS = ["", "拾", "佰", "仟"]
_BIG_UNITS = ["", "萬", "億", "兆"]


def to_daiji(n: int) -> str:
    """0以上の整数を大字表記に変換する（円は付けない）"""
    if n < 0:
        raise ValueError("金額は0以上で指定してください")
    if n == 0:
        return "零"

    s = str(n)
    groups = []
    while s:
        groups.append(s[-4:])
        s = s[:-4]
    # groups[0] が下4桁、groups[1] が次の4桁...

    result = ""
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi].zfill(4)
        part = ""
        for i, ch in enumerate(g):
            d = int(ch)
            if d == 0:
                continue
            unit = _SMALL_UNITS[3 - i]
            # 「壱拾」ではなく「拾」だけにする慣習があるが、金額表記では
            # 誤読防止のため「壱」も明記するのが一般的なのでそのまま出す
            part += _DIGITS[d] + unit
        if part:
            result += part + _BIG_UNITS[gi]

    return result if result else "零"


def to_receipt_string(amount: int, prefix: str = "一金", suffix: str = "円也") -> str:
    """領収書に印字する「一金〇〇円也」形式の文字列を返す"""
    return f"{prefix}{to_daiji(int(amount))}{suffix}"


if __name__ == "__main__":
    tests = [0, 1, 5, 10, 30000, 12345, 100000, 3000, 800, 55555]
    for t in tests:
        print(t, "->", to_receipt_string(t))
