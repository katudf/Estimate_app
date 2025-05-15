# constants.py

# --- 定数定義 ---
APP_FONT_FAMILY = "Meiryo UI"  # main.py で使用
APP_FONT_SIZE = 10
TABLE_ROWS = 25 # 表紙用テーブル行数 (将来的に見直す可能性あり)
TABLE_COLS = 26 # 表紙用テーブル列数 (将来的に見直す可能性あり)
DEFAULT_COL_WIDTH = 30
DEFAULT_ROW_HEIGHT = 30
TAX_RATE = 0.10  # 消費税率 (10%)

# スタイルシート関連定数
STYLE_BORDER_BLACK = "1px solid black" # cover_page_widget.py で使用
COLOR_WHITE = "white"
COLOR_LIGHT_GRAY = "lightgray"
COLOR_LIGHT_BLUE = "#ddebf7"  # 合計(税込)ラベル背景
COLOR_EDIT_DISABLED = "#f0f0f0"  # ReadOnlyのLineEdit背景
COLOR_ERROR_BG = "pink"       # 入力エラー時の背景色
STYLE_NO_BORDER = "border: none;"

# 印影画像のパス
HANKO_IMAGE_PATH = "hanko.png"

# main.py で使用する定数
COLOR_STATUS_BAR_BG = "#333333" # 例: 暗いグレー
COLOR_STATUS_BAR_FG = "white"   # 例: 白文字
WINDOW_TITLE = "木村塗装工業見積書 作成アプリ"
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768

 # データベースファイル名
DATABASE_FILE_NAME = "estimates.db"

# ウィジェット共通スタイル
WIDGET_BASE_STYLE = f"""
    QWidget {{
        font-family: '{APP_FONT_FAMILY}';
        background-color: {COLOR_WHITE}; /* デフォルト背景を白に */
        font-size: {APP_FONT_SIZE}pt;
    }}
    QTableWidget {{
        background-color: {COLOR_WHITE};
        {STYLE_NO_BORDER}
        gridline-color: transparent; /* グリッド線が見えないように */
    }}
    QTableWidget::item {{
        /* {STYLE_NO_BORDER} セルのデフォルト罫線を削除 - テーブル全体で非表示にしているので不要かも */
        color: black; /* テーブルアイテムのデフォルト文字色を黒に再指定 */
    }}
    QTableWidget::item:selected {{
        background-color: #cceeff; /* 選択行の背景色 (薄い水色) */
        /* color: black; */       /* 選択行の文字色指定を削除 (setForegroundを優先させる) */
    }}
    QTableWidget::item:selected:focus {{ /* 選択かつフォーカスがある場合 */
        background-color: #cceeff; /* 選択行と同じ背景色を指定 */
        /* 必要なら文字色も指定: color: black; */
    }}
    QLineEdit, QDateEdit {{
        background-color: {COLOR_WHITE};
        color: black;
        border-top: none;
        border-left: none;
        border-right: none;
        border-bottom: 2px solid gray; /* 下線のみ表示 (色はgrayなどお好みで) */
        padding: 2px; /* 少し内側に余白を持たせると見栄えが良いです */
    }}
    QLabel {{
        color: black; /* 文字色を黒に再指定 */
        background-color: transparent; /* デフォルト背景を透明に */
    }}
    QTextEdit {{ /* QTextEdit (備考欄など) は枠線ありのままにする場合 */
        background-color: {COLOR_WHITE};
        color: black;
        border: 1px solid gray;
    }}
    QDateEdit::drop-down {{ /* QDateEdit のドロップダウンボタンの枠線も調整が必要な場合 */
        border: none; /* ボタンの枠線を消すか、下線に合わせる */
        /* background-color: transparent; */ /* ボタンの背景を透明にするなど */
    }}
    QCheckBox::indicator {{
         width: 15px;
         height: 15px;
         border: 1px solid gray;
         background-color: {COLOR_LIGHT_GRAY}; /* チェックなしのデフォルト */
    }}
    QCheckBox::indicator:checked {{
         background-color: {COLOR_WHITE}; /* チェックあり */
         /* image: url(checked.png); なども可能 */
    }}
    QHeaderView::section {{ /* テーブルヘッダーのスタイル */
        background-color: #f0f0f0; /* ヘッダー背景色 (少しグレーに) */
        color: black;             /* 文字色を黒に */
        padding: 4px;             /* 内側の余白 */
        border: 1px solid #d0d0d0; /* 枠線 (少し薄いグレー) */
        font-weight: bold        /* 文字を太字に (任意) */
    }}
"""
