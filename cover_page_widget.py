# cover_page_widget.py (デバッグプリント削除・スタイル修正済み)

import sys
import os
from PySide6.QtWidgets import (
    QWidget, QTableWidget, QLineEdit, QLabel,
    QDateEdit, QVBoxLayout, QTextEdit, QTableWidgetItem, QPushButton, QFrame, QApplication, # QApplication をインポート
    QAbstractItemView
)
from PySide6.QtCore import QDate, Qt, Signal, Slot # Slot をインポート
from PySide6.QtGui import QFont, QMouseEvent, QKeyEvent # QKeyEvent をインポート

# 定数とカスタムウィジェットをインポート
from constants import (
    APP_FONT_FAMILY, APP_FONT_SIZE, TABLE_ROWS, TABLE_COLS,
    DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, TAX_RATE, WIDGET_BASE_STYLE, STYLE_BORDER_BLACK, COLOR_ERROR_BG, # COLOR_ERROR_BG をインポート
    COLOR_WHITE, COLOR_LIGHT_BLUE, COLOR_EDIT_DISABLED, # 色定数をインポート
    HANKO_IMAGE_PATH # HANKO_IMAGE_PATH は widgets.py で使われるが念のため
)
from widgets import ConstructionPeriodWidget, DraggableLabel

# --------------------------------------------------------------------------
# 編集不可セルの選択を防ぐテーブルウィジェット
# --------------------------------------------------------------------------
class NonEditableSelectionTableWidget(QTableWidget):
    """編集不可セルがクリックされても選択状態にならない QTableWidget"""
    def mousePressEvent(self, event: QMouseEvent):
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            item = self.item(index.row(), index.column()) # <- .col() を .column() に修正
            # アイテムが存在し、かつ編集不可フラグが立っていない場合のみ選択を許可
            if item and not (item.flags() & Qt.ItemIsEditable): # 編集不可フラグのチェック
                # 編集不可セルをクリックした場合、選択状態を変更せずイベントを無視
                event.ignore()
                # print(f"編集不可セル ({index.row()}, {index.col()}) のクリックを無視") # Debug
                return # ここで処理を終了し、基底クラスのイベントを呼ばない
            # else:
                # print(f"編集可能セル ({index.row()}, {index.col()}) またはアイテムなし") # Debug

        # 上記以外の場合（編集可能セル、アイテムがないセル、テーブル外）は通常の処理
        super().mousePressEvent(event)

    # --- Enter/Shift+Enter キー処理 (手動検索) ---
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        # Enter, Shift+Enter, Tab, Shift+Tab (Backtab) を処理対象とする
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab):
            current_widget = QApplication.focusWidget()
            if not current_widget or not self.isAncestorOf(current_widget):
                super().keyPressEvent(event)
                return # テーブル外のウィジェットならデフォルト動作

            current_row, current_col, _ = self._find_focused_widget_cell(current_widget)

            if current_row == -1:
                super().keyPressEvent(event)
                return

            next_widget_to_focus = None
            # Shift+Enter または Shift+Tab(Backtab) の場合に逆方向へ移動
            go_backwards = (key in (Qt.Key_Return, Qt.Key_Enter) and modifiers == Qt.ShiftModifier) or \
                           (key == Qt.Key_Backtab)

            r, c = current_row, current_col
            while True:
                if go_backwards:
                    c -= 1
                    if c < 0:
                        r -= 1
                        if r < 0: break # テーブルの先頭まで来た
                        c = self.columnCount() - 1
                else:
                    c += 1
                    if c >= self.columnCount():
                        r += 1
                        if r >= self.rowCount(): break # テーブルの末尾まで来た
                        c = 0

                widget = self.cellWidget(r, c)
                if self._is_target_widget_for_focus(widget):
                    potential_focus_target = self._get_actual_focusable_widget(widget, go_backwards)
                    if potential_focus_target:
                        next_widget_to_focus = potential_focus_target
                        break # フォーカス対象が見つかった

            if next_widget_to_focus:
                next_widget_to_focus.setFocus()
                if isinstance(next_widget_to_focus, (QLineEdit, QTextEdit)):
                    next_widget_to_focus.selectAll()
                event.accept() # キーイベントを処理済みとしてマークし、デフォルト動作を抑制
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _find_focused_widget_cell(self, focused_widget):
        """現在フォーカスされているウィジェットがどのセルにあるかを探す"""
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                widget = self.cellWidget(r, c)
                if widget == focused_widget:
                    return r, c, widget
                if isinstance(widget, ConstructionPeriodWidget):
                    if focused_widget in (widget.start_edit, widget.end_edit):
                        return r, c, focused_widget
        return -1, -1, None

    def _is_target_widget_for_focus(self, widget):
        """ウィジェットがフォーカス移動の対象となる種類か判定"""
        # QLineEdit, QDateEdit, QTextEdit, ConstructionPeriodWidget のいずれか
        return isinstance(widget, (QLineEdit, QDateEdit, QTextEdit, ConstructionPeriodWidget))

    def _get_actual_focusable_widget(self, widget, go_backwards=False):
        """指定されたウィジェット、またはその子要素のうち、実際にフォーカスすべきウィジェットを返す"""
        if isinstance(widget, ConstructionPeriodWidget):
            # ConstructionPeriodWidget の場合、start_edit または end_edit を返す
            target = None
            if go_backwards:
                # 戻る場合: end_edit が有効なら end_edit、そうでなければ start_edit
                if widget.end_edit.isEnabled() and widget.end_edit.isVisible():
                    target = widget.end_edit
                elif widget.start_edit.isEnabled() and widget.start_edit.isVisible():
                    target = widget.start_edit
            else:
                # 進む場合: start_edit が有効なら start_edit、そうでなければ end_edit
                if widget.start_edit.isEnabled() and widget.start_edit.isVisible():
                    target = widget.start_edit
                elif widget.end_edit.isEnabled() and widget.end_edit.isVisible():
                    target = widget.end_edit
            return target # isEnabled/isVisible チェック済みのものを返す
        elif widget is not None and widget.isEnabled() and widget.isVisible() and \
             widget.focusPolicy() != Qt.NoFocus:
             # その他のウィジェットは、有効かつ可視でフォーカスを受け付けるなら返す
            return widget
        else:
            return None # フォーカス対象外

class CoverPageWidget(QWidget):
    """見積書 表紙ウィジェット"""
    details_requested = Signal() # 明細ページ表示要求シグナル

    def __init__(self):
        super().__init__()
        self.resize(900, 550) # ウィジェットの推奨サイズ

        # --- 初期化処理の呼び出し ---
        self._setup_table()        # QTableWidget の基本設定
        self._define_styles()      # スタイルシート文字列の定義
        self._apply_base_style()   # 基本スタイルをウィジェット全体に適用
        self._create_widgets()     # 個々のウィジェット(ラベル、入力欄など)を作成
        self._setup_layout()       # 作成したウィジェットをテーブルに配置
        self._connect_signals()    # ウィジェットのシグナルとスロットを接続

        # --- 印影ラベルの特別な配置 ---
        if hasattr(self, 'hanko_label') and hasattr(self, 'table'):
            self.hanko_label.setParent(self.table.viewport())
            self.hanko_label.move(660, 220) # 初期表示位置 (適宜調整)
            self.hanko_label.show()
        else:
            print("警告: hanko_label または table が初期化されていません。")

        # --- メインレイアウト ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # 余白なし
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

        # --- 初期状態の必須項目チェック ---
        self._validate_required_field(self.no_edit.text())
        self._validate_required_field(self.client_edit.text())

    # --------------------------------------------------------------------------
    # UI構築ヘルパーメソッド群
    # --------------------------------------------------------------------------

    def _setup_table(self):
        """テーブルウィジェット(QTableWidget)の初期設定"""
        # self.table = QTableWidget(TABLE_ROWS, TABLE_COLS, self) # 変更前
        self.table = NonEditableSelectionTableWidget(TABLE_ROWS, TABLE_COLS, self) # 変更後
        self.table.verticalHeader().setVisible(False)    # 行ヘッダー非表示
        self.table.horizontalHeader().setVisible(False)  # 列ヘッダー非表示
        self.table.setShowGrid(False)                   # QTableWidget 自身のグリッド線非表示
        # 選択モードはデフォルト(SingleSelection or ExtendedSelection)のままで良い

        # デフォルトの行高と列幅を設定
        for c in range(self.table.columnCount()):
            self.table.setColumnWidth(c, DEFAULT_COL_WIDTH)
        for r in range(self.table.rowCount()):
            self.table.setRowHeight(r, DEFAULT_ROW_HEIGHT)

    def _define_styles(self):
        """個別ウィジェット用のスタイルシート文字列を定義"""
        self.style_title = f"font-family: '{APP_FONT_FAMILY}'; font-size: 26pt; font-weight: bold;"
        self.style_client = f"font-family: '{APP_FONT_FAMILY}'; font-size: 18pt; font-weight: bold;"

        # background-color の重複を修正済み
        self.style_total_label = f"""
            font-family: '{APP_FONT_FAMILY}'; font-size: 20pt; font-weight: bold;
            background-color: {COLOR_LIGHT_BLUE}; /* 定数を使用 */
            border: {STYLE_BORDER_BLACK};
            padding: 2px;
        """
        # background-color の重複を修正済み
        self.style_total_edit = f"""
            font-family: '{APP_FONT_FAMILY}'; font-size: 24pt; font-weight: bold;
            background-color: {COLOR_EDIT_DISABLED}; /* 定数を使用 */
            border: {STYLE_BORDER_BLACK};
            padding: 2px;
        """
        self.style_price_tax_edit = f"font-family: '{APP_FONT_FAMILY}'; font-size: 12pt; padding: 1px;"
        self.style_remarks_box = f"border: {STYLE_BORDER_BLACK}; background-color: {COLOR_WHITE};"
        self.style_border_cell = f"border:{STYLE_BORDER_BLACK}; background-color: {COLOR_WHITE};"

    def _apply_base_style(self):
        """ウィジェット全体に基本スタイルシートを適用"""
        self.setStyleSheet(WIDGET_BASE_STYLE)

    def _create_widgets(self):
        """主要なウィジェットの作成と初期設定"""
        # --- ヘッダー情報 ---
        self.title_label = self._create_label("御　見　積　書", align=Qt.AlignCenter, style=self.style_title)
        self.no_label = self._create_label("見積 No")
        self.no_edit = QLineEdit()
        self.date_label = self._create_label("　見積日")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy年MM月dd日")
        # 見積番号は必須項目
        self.no_edit.setProperty("required", True)
        self.no_edit.setProperty("has_error", False) # 初期状態はエラーなし

        # --- 宛先 ---
        self.client_edit = QLineEdit()
        self.client_edit.setPlaceholderText("ー　相手先名　ー")
        # 宛名は必須項目
        self.client_edit.setProperty("required", True)
        self.client_edit.setProperty("has_error", False) # 初期状態はエラーなし

        self.greeting_label = self._create_label("下記の通りお見積り申し上げます。", align=Qt.AlignLeft | Qt.AlignVCenter)

        # --- 金額欄 ---
        style_to_apply_label = getattr(self, 'style_total_label', '')
        self.total_label = self._create_label("合計(税込)", align=Qt.AlignCenter, style=style_to_apply_label)
        self.total_label.setAutoFillBackground(True) # 背景色有効化（重複削除済み）

        style_to_apply_edit = getattr(self, 'style_total_edit', '')
        self.total_edit = QLineEdit("￥0")
        self.total_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total_edit.setReadOnly(True)
        self.total_edit.setStyleSheet(style_to_apply_edit) # スタイル適用

        # --- 工事金額・消費税額 ---
        self.price_label = self._create_label("工事金額")
        self.price_edit = QLineEdit()
        self.price_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.price_edit.setReadOnly(True) # ★★★ この行を追加 ★★★
        if hasattr(self, 'style_price_tax_edit'):
            self.price_edit.setStyleSheet(self.style_price_tax_edit)

        self.tax_label = self._create_label("消費税額")
        self.tax_edit = QLineEdit()
        self.tax_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tax_edit.setReadOnly(True)
        if hasattr(self, 'style_price_tax_edit'):
             self.tax_edit.setStyleSheet(self.style_price_tax_edit)

        # --- 工事項目 ---
        self.project_name_label = self._create_label("工 事 名", align=Qt.AlignCenter)
        self.project_name_edit = QLineEdit()

        self.project_location_label = self._create_label("工事場所", align=Qt.AlignCenter)
        self.project_location_edit = QLineEdit()

        self.period_label = self._create_label("工　　期", align=Qt.AlignCenter)
        self.period_widget = ConstructionPeriodWidget()

        self.expiry_label = self._create_label("有効期限", align=Qt.AlignCenter)
        self.expiry_date_edit = QDateEdit(QDate.currentDate().addMonths(6))
        self.expiry_date_edit.setCalendarPopup(True)
        self.expiry_date_edit.setDisplayFormat("yyyy年MM月dd日")

        self.payment_label = self._create_label("支払条件", align=Qt.AlignCenter)
        self.payment_edit = QLineEdit()

    # --- 備考欄 ---
        self.remarks_label = self._create_label("備考")
        self.remarks_box = QTextEdit()

    # ↓↓↓ スタイル適用部分を一時的に書き換え ↓↓↓
    # if hasattr(self, 'style_remarks_box'):
    #     self.remarks_box.setStyleSheet(self.style_remarks_box)
    # 上記の代わりに、直接シンプルなスタイルを適用してみる
        self.remarks_box.setStyleSheet("border: 1px solid black;") # 太くて赤い枠線（目立つように）
    # ↑↑↑ スタイル適用部分を一時的に書き換え ↑↑↑

        # --- 会社情報 ---
        self.corp_box = QLabel()
        self.corp_box.setTextFormat(Qt.RichText)
        self.corp_box.setText(
            f"<div style='font-family: \"{APP_FONT_FAMILY}\"; font-size:8pt; line-height: 1.2;'>"
            f"<b style='font-size:12pt;'>有限会社 木村塗装工業</b><br>"
            "　代表取締役　木村賢二<br>"
            "　岩手県奥州市水沢字川端213-1<br>"
            "　TEL：0197-23-4459<br>"
            "　FAX：0197-23-4465"
            "</div>"
        )
        self.corp_box.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # --- 印影ラベル ---
        self.hanko_label = DraggableLabel()

        # --- 担当者名 ---
        self.staff_label = self._create_label("担当者名", align=Qt.AlignLeft, font_size=11)
        self.staff_edit = QLineEdit()

        # --- 明細編集ボタン (ツールバーに移動したので削除) ---
        # self.detail_button = QPushButton("明細編集へ >>")
        # ... (スタイル設定も削除) ...


    def _setup_layout(self):
        """ウィジェットのテーブルへの配置とセル結合"""
        # (row, col, widget, span=(rowspan, colspan))
        self._set_widget(0, 6, self.title_label, span=(3, 14))
        self._set_widget(4, 1, self.no_label, span=(1, 2))
        self._set_widget(4, 3, self.no_edit, span=(1, 6))
        self._set_widget(4, 19, self.date_label, span=(1, 2))
        self._set_widget(4, 21, self.date_edit, span=(1, 5))
        self._set_widget(7, 1, self.client_edit, span=(2, 14))
        self._set_widget(9, 1, self.greeting_label, span=(1, 7))
        self._set_widget(11, 1, self.total_label, span=(2, 5))
        self._set_widget(11, 6, self.total_edit, span=(2, 10))
        self._set_widget(13, 1, self.price_label, span=(1, 2))
        self._set_widget(13, 3, self.price_edit, span=(1, 5))
        self._set_widget(13, 9, self.tax_label, span=(1, 2))
        self._set_widget(13, 11, self.tax_edit, span=(1, 5))
        self._set_widget(17, 1, self.project_name_label, span=(1, 2))
        self._set_widget(17, 3, self.project_name_edit, span=(1, 10))
        self._set_widget(18, 1, self.project_location_label, span=(1, 2))
        self._set_widget(18, 3, self.project_location_edit, span=(1, 10))
        self._set_widget(19, 1, self.period_label, span=(1, 2))
        self._set_widget(19, 3, self.period_widget, span=(1, 10))
        self._set_widget(20, 1, self.expiry_label, span=(1, 2))
        self._set_widget(20, 3, self.expiry_date_edit, span=(1, 10))
        self._set_widget(21, 1, self.payment_label, span=(1, 2))
        self._set_widget(21, 3, self.payment_edit, span=(1, 10))
        self._set_widget(16, 14, self.remarks_label)
        self._set_widget(17, 14, self.remarks_box, span=(5, 14))
        self._set_widget(7, 18, self.corp_box, span=(3, 8))
        self._set_widget(10, 18, self.staff_label, span=(1, 2))
        self._set_widget(10, 20, self.staff_edit, span=(1, 5))
        self._put_border_cell(12, 18, span=(2, 2))
        self._put_border_cell(12, 20, span=(2, 2))
        self._put_border_cell(12, 22, span=(2, 2))
        # self._set_widget(23, 20, self.detail_button, span=(1, 6)) # レイアウトからも削除
        # --- レイアウト設定後に入力部以外のセルをロック ---
        self._lock_non_editable_cells()

    def _connect_signals(self):
        """シグナルとスロット(または他のシグナル)の接続"""
        # 金額計算関連の接続は削除またはコメントアウトされている想定

        # 必須項目チェック (ここが正しくインデントされていることを確認)
        if hasattr(self, 'no_edit'):
            self.no_edit.textChanged.connect(self._validate_required_field)
        if hasattr(self, 'client_edit'):
            self.client_edit.textChanged.connect(self._validate_required_field)
            # client_edit はテキスト有無で色も変えるので、スタイル適用も接続
            self.client_edit.textChanged.connect(self._apply_client_style)

        # 初期スタイル適用 (接続後に行う)
        if hasattr(self, 'client_edit'):
            self._apply_client_style() # client_edit の初期スタイル
        if hasattr(self, 'no_edit'):
            self._apply_required_style(self.no_edit) # no_edit の初期スタイル

        # もし上記の処理も全てコメントアウト/削除していてメソッド内が空になる場合は、
        # 以下のように pass を記述します。
        # pass

    # --------------------------------------------------------------------------
    # スロット / データ処理メソッド
    # --------------------------------------------------------------------------

    @Slot(str)
    def _validate_required_field(self, text: str):
        """必須項目フィールドの入力値を検証し、スタイルを更新するスロット"""
        sender_widget = self.sender()
        if not isinstance(sender_widget, QLineEdit) or not sender_widget.property("required"):
            return # QLineEdit 以外、または必須項目でない場合は無視

        is_empty = not text.strip()
        has_error_property = sender_widget.property("has_error")

        if is_empty != has_error_property: # エラー状態が変わった場合のみスタイル更新
            sender_widget.setProperty("has_error", is_empty)
            if sender_widget == self.client_edit:
                # client_edit は色変更もあるので専用メソッドでスタイル適用
                self._apply_client_style()
            else:
                # その他の必須項目は共通メソッドでスタイル適用
                self._apply_required_style(sender_widget)

    def _apply_client_style(self):
        """client_edit のスタイル（枠線と文字色）を適用する"""
        if not hasattr(self, 'client_edit'): return

        style = self.style_client # 基本スタイル
        is_empty = not self.client_edit.text().strip()
        has_error = self.client_edit.property("has_error")

        if has_error:
            style += f" border: 1px solid {COLOR_ERROR_BG};" # エラー時は赤い枠線
            style += " color: lightgray;" # プレースホルダーの色
        else:
            # style += " border: 1px solid gray;" # 通常時の枠線 (任意、デフォルトに任せるなら不要)
            style += f" color: {'lightgray' if is_empty else 'black'};" # テキスト有無で色変更

        self.client_edit.setStyleSheet(style)

    def _apply_required_style(self, widget: QLineEdit):
        """必須項目QLineEditの枠線スタイルを適用する"""
        has_error = widget.property("has_error")
        border_style = f"border: 1px solid {COLOR_ERROR_BG};" if has_error else "" # エラー時のみ赤枠
        widget.setStyleSheet(border_style)

    def _update_totals(self):
        """工事金額入力完了時に消費税額と税込合計を計算・表示"""
        if not all(hasattr(self, attr) for attr in ['price_edit', 'tax_edit', 'total_edit']):
            print("エラー: 金額関連ウィジェットが不足しています。")
            return

        text = self.price_edit.text().replace("￥", "").replace(",", "").strip()
        try:
            if text:
                price = int(text)
                tax = int(price * TAX_RATE) # Use TAX_RATE from constants [cite: 1]
                total = price + tax
                self.price_edit.setText(f"￥{price:,}")
                self.tax_edit.setText(f"￥{tax:,}")
                self.total_edit.setText(f"￥{total:,}")
            else:
                self.price_edit.setText("")
                self.tax_edit.setText("")
                self.total_edit.setText("￥0")
        except ValueError:
            print(f"無効な入力です: '{text}'。数字のみ入力してください。")
            self.price_edit.setText("")
            self.tax_edit.setText("")
            self.total_edit.setText("￥0")
        except Exception as e:
            print(f"金額計算中にエラーが発生しました: {e}")

    # --------------------------------------------------------------------------
    # データ取得用メソッド (main.py から呼ばれる)
    # --------------------------------------------------------------------------

    def get_project_name(self) -> str:
        return self.project_name_edit.text() if hasattr(self, 'project_name_edit') else ""

    def get_client_name(self) -> str:
        return self.client_edit.text() if hasattr(self, 'client_edit') else ""

    def get_total(self) -> str:
        return self.total_edit.text() if hasattr(self, 'total_edit') else "￥0"

    def get_subtotal(self) -> str:
        return self.price_edit.text() if hasattr(self, 'price_edit') else ""

    def get_tax(self) -> str:
        return self.tax_edit.text() if hasattr(self, 'tax_edit') else ""

    def get_period_text(self) -> str:
        return self.period_widget.period_text() if hasattr(self, 'period_widget') else ""

    # --- データ設定用メソッド (main.py から呼ばれる) ---
    def set_totals(self, subtotal: str, tax: str, total: str):
        """明細画面から受け取った金額を設定する"""
        if hasattr(self, 'price_edit'):
            self.price_edit.setText(subtotal)
        if hasattr(self, 'tax_edit'):
            self.tax_edit.setText(tax)
        if hasattr(self, 'total_edit'):
            self.total_edit.setText(total)
    # --------------------------------------------------------------------------
    # ユーティリティメソッド
    # --------------------------------------------------------------------------

    def _create_label(self, text, align=Qt.AlignLeft, bold=False, font_size=None, style=None) -> QLabel:
        """QLabel を作成して返すユーティリティ"""
        lbl = QLabel(text)
        lbl.setAlignment(align | Qt.AlignVCenter)
        f = lbl.font()
        base_font_size = APP_FONT_SIZE # Use base font size from constants [cite: 1]
        f.setPointSize(font_size if font_size is not None else base_font_size)
        if bold:
            f.setBold(True)
        lbl.setFont(f)
        if style:
            lbl.setStyleSheet(style) # Apply specific style if provided
        return lbl

    def _set_widget(self, row, col, widget, span=(1, 1)):
        """指定したセルにウィジェットを配置し、必要ならセルを結合する"""
        if not hasattr(self, 'table'):
             print("エラー: table が初期化されていません。")
             return
        rspan, cspan = span
        if rspan > 1 or cspan > 1:
            self.table.setSpan(row, col, rspan, cspan)
        self.table.setCellWidget(row, col, widget)

    # cover_page_widget.py の _put_border_cell を再度修正

    def _put_border_cell(self, row, col, text="", span=(1, 1)):
        """罫線付きの空セル（QFrame）を作成して配置する (押印欄などに使用)"""
        frame = QFrame()

        # ネイティブの枠描画は使用しない
        frame.setFrameShape(QFrame.NoFrame)
        # frame.setFrameShadow(QFrame.Plain) # NoFrame の場合 Shadow は影響しないはず

        # スタイルシートで背景色と枠線の両方を定義
        # (定数 STYLE_BORDER_BLACK と STYLE_BG_WHITE を利用)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE}; /* 定数を使用 */
                border: {STYLE_BORDER_BLACK};
            }}
        """)
        # background-color が確実に描画されるようにする
        frame.setAutoFillBackground(True)

        # 必要であれば最小サイズも設定
        # frame.setMinimumSize(50, 50)

        self._set_widget(row, col, frame, span=span)

    def _lock_non_editable_cells(self):
        """テーブル内の入力ウィジェットが配置されていないセルを編集不可にする"""
        if not hasattr(self, 'table'):
            print("エラー: table が初期化されていません。")
            return

        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                # セルウィジェットがない場合、または編集可能でないウィジェットの場合
                widget = self.table.cellWidget(r, c)
                if widget is None or not isinstance(widget, (QLineEdit, QDateEdit, QTextEdit, ConstructionPeriodWidget)):
                    item = self.table.item(r, c)
                    if item is None:
                        item = QTableWidgetItem()
                        self.table.setItem(r, c, item)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable) # 編集不可フラグを設定
# --- Optional: Test code if run directly ---
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     app.setFont(QFont(APP_FONT_FAMILY, APP_FONT_SIZE)) # Set app font from constants [cite: 1]
#     widget = CoverPageWidget()
#     widget.show()
#     sys.exit(app.exec())