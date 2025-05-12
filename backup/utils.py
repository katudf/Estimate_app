# utils.py

import locale

# ロケールを設定してカンマ区切りを有効にする (アプリケーション開始時に一度だけ行うのが望ましい)
try:
    # Windowsの場合、日本語ロケールを設定 (UTF-8が利用できない場合がある)
    locale.setlocale(locale.LC_ALL, 'ja_JP')
except locale.Error:
    try:
        # 代替としてシステムのデフォルトロケールを使用
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        print("警告: ロケールの設定に失敗しました。数値フォーマットが正しく行われない可能性があります。")

def format_currency(value: float | int) -> str:
    """数値を円通貨形式（￥付き、カンマ区切り、整数）の文字列にフォーマットする"""
    try:
        # locale.format_string を使うとロケール依存の区切り文字になる
        # return f"￥{locale.format_string('%d', int(value), grouping=True)}"
        # より確実な f-string を使用
        return f"￥{int(value):,}"
    except (ValueError, TypeError):
        return "￥0" # エラー時は ￥0 を返す

def format_quantity(value: float) -> str:
    """数値を小数点以下1桁の文字列にフォーマットする"""
    try:
        return f"{float(value):.1f}"
    except (ValueError, TypeError):
        return "0.0" # エラー時は 0.0 を返す

def parse_number(text: str) -> float:
    """文字列から数値（float）をパースする（￥やカンマを除去）"""
    if not isinstance(text, str):
        return 0.0
    cleaned_text = text.replace("￥", "").replace(",", "").strip()
    try:
        # locale.atof を使うとロケール依存の小数点文字に対応できる
        # return locale.atof(cleaned_text or "0")
        # シンプルに float を使用
        return float(cleaned_text or 0.0)
    except ValueError:
        return 0.0 # パース失敗時は 0.0 を返す