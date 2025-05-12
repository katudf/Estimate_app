# detail_page_widget.py (パレットで背景色を修正)

# detail_page_widget.py の先頭に追加

import os
from PySide6.QtWidgets import (
    # ... (既存の QtWidgets インポート) ...
    QMessageBox, QComboBox, QCompleter, QLineEdit,
    QWidget, QTableWidget, QVBoxLayout, QTableWidgetItem, QHeaderView, QApplication,
    QLabel, QPushButton, QGridLayout, QFrame, QHBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QEvent, QModelIndex, QItemSelectionModel
from PySide6.QtGui import (
    # ... (既存の QtGui インポート) ...
    QPalette, QColor, QDropEvent, QDragEnterEvent, QDragMoveEvent,
    QContextMenuEvent, QAction, QKeySequence, QBrush
)

# ↓↓↓ typing から List と Optional をインポート ↓↓↓
from typing import List, Optional, Callable # Optional や Callable も使っている場合
# ↑↑↑ typing から List と Optional をインポート ↑↑↑

from constants import WIDGET_BASE_STYLE, COLOR_LIGHT_GRAY, COLOR_WHITE, COLOR_ERROR_BG
from commands import AddRowCommand, InsertRowCommand, RemoveRowCommand, MoveRowCommand, ChangeItemCommand, DuplicateRowCommand, RemoveMultipleRowsCommand
from utils import format_currency, format_quantity, parse_number

# ... (クラス定義以降) ...

# --------------------------------------------------------------------------
# ドラッグ＆ドロップ可能なテーブルウィジェット
# --------------------------------------------------------------------------
class DraggableTableWidget(QTableWidget):
    """行のドラッグ＆ドロップによる並べ替えが可能な QTableWidget"""

    # 行が移動されたときに発行されるシグナル
    row_moved = Signal(int, int) # 移動元、移動先の行インデックスを渡す
    # 右クリックメニューのアクションが要求されたときに発行されるシグナル
    context_action_requested = Signal(str, int) # アクション名 ('add', 'remove', 'duplicate'), 行インデックス

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack = None # MainWindow から設定される
        self._configure_drag_drop()

# detail_page_widget.py の DraggableTableWidget クラス内


    def _configure_drag_drop(self):
        """ドラッグ＆ドロップ関連の設定"""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        # ↓↓↓ 変更点 ↓↓↓
        self.setDragDropMode(QAbstractItemView.InternalMove) # InternalMove に変更
        self.setSelectionMode(QAbstractItemView.ExtendedSelection) # ExtendedSelection に変更
        # ↑↑↑ 変更点 ↑↑↑
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
    # --- ドラッグ＆ドロップ イベントハンドラ ---

    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグがウィジェット内に入ったときのイベント"""
        # print("\n--- DraggableTableWidget: dragEnterEvent 発生！ ---") # デバッグ削除
        # 自分自身からの移動操作か確認 (MIMEタイプで判断)
        if event.source() == self and event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            # print("  -> 受け入れ可能なドラッグです (acceptProposedAction)") # デバッグ削除
            event.acceptProposedAction()
        else:
            # print("  -> 受け入れ不可能なドラッグです (ignore)") # デバッグ削除
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """ドラッグ中にウィジェット内でマウスが移動したときのイベント"""
        # print("--- DraggableTableWidget: dragMoveEvent ---") # 頻繁なのでコメントアウト
        if event.source() == self and event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """ドロップされたときの処理"""
        # print("\n--- DraggableTableWidget: dropEvent 発生！ ---") # デバッグ削除
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on(event)
            if drop_row == -1: # 行の外なら末尾
                drop_row = self.rowCount()

            rows = sorted(list(set(item.row() for item in self.selectedItems())))
            # print(f"  選択行: {rows}, ドロップ目標行: {drop_row}") # デバッグ削除

            if not rows:
                # print("  選択行なし、無視") # デバッグ削除
                event.ignore()
                return

            # --- 単一行移動のみ実装 ---
            if len(rows) == 1:
                source_row = rows[0]
                # print(f"  移動元: {source_row}, 移動先(目標): {drop_row}") # デバッグ削除

                # 自分自身の上や直下にドロップしようとした場合は無視
                if source_row == drop_row or source_row + 1 == drop_row:
                    # print("  移動元と移動先が同じか隣接、無視") # デバッグ削除
                    event.ignore()
                    return

                # --- UNDO コマンドを作成して実行 ---
                if self.undo_stack:
                    # MoveRowCommand は removeRow 後の挿入位置を計算する
                    print(f"DEBUG: Creating MoveRowCommand (source={source_row}, dest={drop_row})") # コマンド作成ログ ★★★ ここに追加 ★★★
                    command = MoveRowCommand(self, source_row, drop_row)
                    self.undo_stack.push(command)
                    event.accept()
                    # print("  ドロップ操作を受け入れ (accept)") # デバッグ削除
                    # シグナル発行はコマンド実行後に行われる (redo 内で selectRow される)
                    # self.row_moved.emit(source_row, command.actual_dest_row) # 必要ならコマンドから実際の移動先を取得
                else:
                    print("警告: undo_stack が設定されていません。行移動は記録されません。")
                    event.ignore() # UNDOできない操作は許可しない方が良いかも
            else:
                # print("  複数行移動は未対応、無視") # デバッグ削除
                event.ignore()

    def drop_on(self, event: QDropEvent) -> int:
        """ドロップ位置から挿入すべき行インデックスを計算する"""
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            return -1 # テーブルの外側

        indicator = self.dropIndicatorPosition()
        row = index.row()

        if indicator == QAbstractItemView.DropIndicatorPosition.BelowItem:
            row += 1
        elif indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
             row = self.rowCount() # ビューポートなら末尾
        # AboveItem or OnItem の場合はそのままの行 (その行の上に挿入)

        return row

    def keyPressEvent(self, event):
        """キーボードイベントを処理してEnterキーでのセル移動を実現"""
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_index = self.currentIndex()
            if not current_index.isValid():
                super().keyPressEvent(event)
                return

            row, col = current_index.row(), current_index.column()
            next_row, next_col = row, col

            if modifiers == Qt.ShiftModifier: # Shift + Enter: 左へ、行頭なら前の行末へ
                if col > 0:
                    next_col -= 1
                elif row > 0:
                    next_row -= 1
                    next_col = self.columnCount() - 1
                else: # テーブルの左上端なら何もしない
                    super().keyPressEvent(event)
                    return
            else: # Enter: 右へ、行末なら次の行頭へ
                if col < self.columnCount() - 1:
                    next_col += 1
                elif row < self.rowCount() - 1:
                    next_row += 1
                    next_col = 0
                else: # テーブルの右下端なら何もしない (または新規行追加など)
                    super().keyPressEvent(event)
                    return

            next_index = self.model().index(next_row, next_col)
            if next_index.isValid():
                self.setCurrentIndex(next_index)
                self.edit(next_index) # 次のセルを編集モードにする
            event.accept() # Enterキーのデフォルト動作を抑制
        else:
            # Enterキー以外は通常のキーイベント処理
            super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """右クリック時にコンテキストメニューを表示"""
        from PySide6.QtWidgets import QMenu # ここでインポート

        menu = QMenu(self)

        # --- メニューの文字色を黒に設定 ---
        menu.setStyleSheet("color: black;")
        # 右クリックされた位置の行を取得
        index = self.indexAt(event.pos())
        clicked_row = index.row() if index.isValid() else -1

        # --- アクションの作成 ---
        add_action = QAction("行追加", self)
        remove_action = QAction("行削除", self)
        duplicate_action = QAction("複写", self)

        # --- アクションとシグナルを接続 ---
        # lambda を使って、クリックされた行の情報を渡す
        add_action.triggered.connect(lambda: self.context_action_requested.emit('add', clicked_row))
        remove_action.triggered.connect(lambda: self.context_action_requested.emit('remove', clicked_row))
        duplicate_action.triggered.connect(lambda: self.context_action_requested.emit('duplicate', clicked_row))

        # --- 行が選択されている場合のみ削除と複写を有効化 ---
        if clicked_row >= 0:
            remove_action.setEnabled(True)
            duplicate_action.setEnabled(True)
        else:
            remove_action.setEnabled(False)
            duplicate_action.setEnabled(False)

        menu.addAction(add_action)
        menu.addAction(remove_action)
        menu.addAction(duplicate_action)

        menu.exec(event.globalPos()) # グローバル座標でメニューを表示

# --------------------------------------------------------------------------
# 明細ページウィジェット
# --------------------------------------------------------------------------
class DetailPageWidget(QWidget):
    """見積明細の表示・入力ウィジェット"""

    # 画面切り替え要求シグナル
    cover_requested = Signal()
    # ステータスメッセージ表示要求シグナル (メッセージ文字列を渡す)
    status_message_requested = Signal(str)
    # 画面フラッシュ要求シグナル
    screen_flash_requested = Signal()

    # --- 列インデックス定数 ---
    COL_ITEM = 0
    COL_QUANTITY = 1
    COL_UNIT = 2       # <- 新しい単位列
    COL_UNIT_PRICE = 3 # <- インデックス変更
    COL_AMOUNT = 4     # <- インデックス変更
    COL_REMARKS = 5    # <- インデックス変更
    NUM_COLS = 6       # <- 列の総数を更新

    # --- ヘッダー情報 ---
    HEADERS = ["項目", "数量", "単位", "単価", "金額", "備考"] # <- ヘッダー追加
    INITIAL_WIDTHS = [300, 80, 60, 100, 120, 200] # <- 単位列の幅を追加

    # ↓↓↓ undo_stack を受け取るように変更 ↓↓↓
    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.is_editing = False # セル編集中フラグ (ChangeItemCommand用)
        self.last_error_info = None # 最後に発生したエラー情報 (row, col, message)
        self.unit_list = self._load_units() # 単位リストを読み込む

        # ↓↓↓ パレットでウィジェット自身の背景色を白に設定 ↓↓↓
        palette = self.palette()
        # QPalette.Window はウィジェットの主要な背景色の役割
        palette.setColor(QPalette.Window, QColor('white')) # 直接 'white' を指定
        self.setPalette(palette)
        # setAutoFillBackground(True) でパレット背景の描画を有効にする
        self.setAutoFillBackground(True)
        # ↑↑↑ パレットでウィジェット自身の背景色を白に設定 ↑↑↑

        # ↓↓↓ スタイルシートはフォントやテーブル交互色など、他の要素に適用 ↓↓↓
        detail_page_style = WIDGET_BASE_STYLE + f"""
            QTableWidget {{
                alternate-background-color: {COLOR_LIGHT_GRAY}; /* 定数 COLOR_LIGHT_GRAY を使用 */
            }}
            /* 必要に応じて、ここで DetailPageWidget 内の他の特定ウィジェットの
               スタイルを WIDGET_BASE_STYLE に追加/上書きすることも可能 */
        """
        self.setStyleSheet(detail_page_style)
        # ↑↑↑ スタイルシートはフォントやテーブル交互色など、他の要素に適用 ↑↑↑

        self._setup_ui()
        # ↓↓↓ セルの変更前後のデータを取得するため、cellChanged と cellEntered/cellPressed を使う ↓↓↓
        self.table.cellPressed.connect(self._on_cell_pressed) # 編集開始前の値を取得
        self.table.cellChanged.connect(self._on_cell_changed) # 編集完了後の値を取得
        # ↑↑↑ セルの変更前後のデータを取得するため、cellChanged と cellEntered/cellPressed を使う ↑↑↑
        # ↓↓↓ 行操作ボタンのシグナル接続 (ツールバーに移動したので削除) ↓↓↓
        # self.add_row_button.clicked.connect(self.add_row)
        # self.remove_row_button.clicked.connect(self.remove_row)
        # self.duplicate_row_button.clicked.connect(self.duplicate_row)
        # ↑↑↑ 行操作ボタンのシグナルを接続 ↑↑↑
        # ↓↓↓ テーブルの行移動シグナルを接続 ↓↓↓
        # _update_detail_totals は undo_stack.indexChanged に接続するので、ここでは不要
        if hasattr(self, 'table'):
            self.table.row_moved.connect(self._update_detail_totals)
            # print("self.table.row_moved シグナルを接続しました。") # デバッグ削除
        else:
            print("警告: self.table が未定義のため row_moved シグナルを接続できません。")
        # ↓↓↓ 右クリックメニューからのアクション要求シグナルを接続 ↓↓↓
        self.table.context_action_requested.connect(self._handle_context_action)
        # ↓↓↓ DetailPageWidget 自身もドロップを受け付けるように設定 ↓↓↓
        self.setAcceptDrops(True)

    def _load_units(self) -> list[str]:
        """units.txt から単位リストを読み込む"""
        units_file = "units.txt" # ファイル名を定数化しても良い
        default_units = ["式", "個", "m", "m2", "本", "セット"]
        try:
            with open(units_file, "r", encoding="utf-8") as f:
                units = [line.strip() for line in f if line.strip()]
            return units if units else default_units
        except FileNotFoundError:
            # ファイルが見つからない場合の警告を追加
            print(f"警告: {units_file} が見つかりません。デフォルトの単位リストを使用します。")
            return default_units
        except Exception as e:
            print(f"エラー: {units_file} の読み込み中にエラーが発生しました: {e}")
            return default_units

    # --- マウスイベント確認用 (デバッグ) ---
    def mousePressEvent(self, event):
        # print("\n--- DetailPageWidget: マウスクリック検出！ ---") # デバッグ削除
        super().mousePressEvent(event) # 元のイベント処理も呼ぶ

    def mouseMoveEvent(self, event):
        # print("--- DetailPageWidget: マウス移動 ---") # 頻繁に出るのでコメントアウト
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # print("--- DetailPageWidget: マウスリリース ---") # デバッグ削除
        super().mouseReleaseEvent(event)
    # --- ここまでマウスイベント確認用 ---
    # --- イベントフィルタは削除 ---

    def _setup_ui(self):
        """UI要素の作成と配置"""
        header_frame = self._create_header_widget()
        # ↓↓↓ DraggableTableWidget を使うように修正 ↓↓↓
        self.table = DraggableTableWidget()
        self.table.undo_stack = self.undo_stack # DraggableTableWidget に undo_stack を渡す
        self._configure_table()
        # self.back_button = QPushButton("<< 表紙へ戻る") # ツールバーに移動したので削除
        # ↓↓↓ 行操作ボタンを作成 (ツールバーに移動したので削除) ↓↓↓
        # self.add_row_button = QPushButton("行追加")
        # self.remove_row_button = QPushButton("行削除")
        # self.duplicate_row_button = QPushButton("複写")
        # ↑↑↑ 行操作ボタンを作成 (ツールバーに移動したので削除) ↑↑↑

        # ボタンのスタイル設定 (ユーザー提供コードから)
        button_style = """
            QPushButton {
                background-color: #E0E0E0; color: black;
                border: 1px solid #B0B0B0; padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: black; color: white;
                border: 1px solid black;
            }
            QPushButton:pressed {
                background-color: #333333; color: white;
                border: 1px solid black;
            }
        """
        # self.back_button.setStyleSheet(button_style) # 削除
        # ↓↓↓ 行操作ボタンにもスタイルを適用 (削除) ↓↓↓
        # self.add_row_button.setStyleSheet(button_style)
        # self.remove_row_button.setStyleSheet(button_style)
        # self.duplicate_row_button.setStyleSheet(button_style)
        # ↑↑↑ 行操作ボタンにもスタイルを適用 ↑↑↑

        # レイアウト設定
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        main_layout.addWidget(header_frame)
        main_layout.addWidget(self.table)
        # button_layout = QHBoxLayout() # ボタンレイアウト削除
        # ↓↓↓ 行操作ボタンをレイアウトに追加 (削除) ↓↓↓
        # button_layout.addWidget(self.remove_row_button)
        # button_layout.addWidget(self.duplicate_row_button)
        # button_layout.addWidget(self.add_row_button)
        # button_layout.addWidget(self.back_button)
        # button_layout.addStretch() # 削除
        # main_layout.addLayout(button_layout) # 削除
        self.setLayout(main_layout)


    def _configure_table(self):
        """明細テーブル(QTableWidget)の初期設定"""
        if not hasattr(self, 'table'):
             print("エラー: self.table が _setup_ui で作成されていません。")
             return

        self.table.setColumnCount(self.NUM_COLS)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        header = self.table.horizontalHeader()
        for i, width in enumerate(self.INITIAL_WIDTHS):
            header.resizeSection(i, width)

        self.table.setAlternatingRowColors(True) # 交互行色を有効化
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setVisible(True) # 水平ヘッダーを表示
        self.table.verticalHeader().setVisible(True)   # 垂直ヘッダーを表示 (行番号)

        # --- ドラッグ＆ドロップ設定は DraggableTableWidget 内で行う ---
        # --- ドラッグ＆ドロップ設定ここまで ---

        # self.table.setRowCount(10) # 初期行数 -> テストデータで設定するためコメントアウト

        # ↓↓↓ 金額列を編集不可にするための準備 (初期セル作成時に適用) ↓↓↓
        # for row in range(self.table.rowCount()):
        #     amount_item = QTableWidgetItem()
        #     amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable) # 編集不可フラグ
        #     self.table.setItem(row, self.COL_AMOUNT, amount_item)

        # --- テスト用初期データ ---
        test_data = [ # 単位列の初期値も設定
            {"item": "テスト項目1", "quantity": 10.0, "unit": "式", "unit_price": 1000, "remarks": "テスト備考1"}, # 修正
            {"item": "テスト項目2", "quantity": 5.0, "unit": "個", "unit_price": 500, "remarks": ""}, # 修正
            {"item": "テスト項目3", "quantity": 1.0, "unit": "m2", "unit_price": 15000, "remarks": "長い備考テスト"}, # 修正
            {"item": "テスト項目4", "quantity": 20.5, "unit": "本", "unit_price": 800, "remarks": ""}, # 修正
            {"item": "テスト項目5", "quantity": 1.0, "unit": "ｾｯﾄ", "unit_price": 50000, "remarks": "セット品"},
        ]

        self.table.setRowCount(len(test_data)) # データ件数に合わせて行数を設定
        self.table.blockSignals(True) # データ設定中のシグナルをブロック
        for row, data in enumerate(test_data):
            # 各列のアイテムを作成・設定
            item_item = QTableWidgetItem(data["item"])
            quantity_item = QTableWidgetItem(f"{data['quantity']:.1f}")
            # unit_item = QTableWidgetItem(data["unit"]) # <- QComboBox にするので削除
            unit_price_item = QTableWidgetItem(f"{data['unit_price']:,.0f}")
            remarks_item = QTableWidgetItem(data["remarks"])

            # アライメント設定
            quantity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # unit_item.setTextAlignment(Qt.AlignCenter) # unit_item はもう使わないので削除
            unit_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            # 金額計算
            amount = data["quantity"] * data["unit_price"]
            amount_item = QTableWidgetItem(f"{amount:,.0f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable) # 金額列は編集不可

            # テーブルにアイテムをセット
            self.table.setItem(row, self.COL_ITEM, item_item)
            self.table.setItem(row, self.COL_QUANTITY, quantity_item) # 数量
            # --- 単位列に QComboBox を設定 ---
            unit_combo = self._create_unit_combobox()
            unit_combo.setCurrentText(data.get("unit", "")) # 初期値を設定
            self.table.setCellWidget(row, self.COL_UNIT, unit_combo) # setCellWidget を使用
            # デバッグ: 設定されたウィジェットを確認
            #print(f"DEBUG: Set ComboBox at ({row}, {self.COL_UNIT}): {self.table.cellWidget(row, self.COL_UNIT)}")
            # ---
            self.table.setItem(row, self.COL_UNIT_PRICE, unit_price_item)
            self.table.setItem(row, self.COL_AMOUNT, amount_item) # 金額
            self.table.setItem(row, self.COL_REMARKS, remarks_item)
        self.table.blockSignals(False) # シグナルブロック解除

        # 初期データに基づいて合計を計算・表示
        self._update_detail_totals()
        # ↑↑↑ 初期セル作成は後で検討。まずは itemChanged で対応 ↑↑↑


    def _create_header_widget(self) -> QWidget:
        """明細ページ上部のヘッダー情報ウィジェットを作成する"""
        header_widget = QWidget()
        # layout = QGridLayout(header_widget) # QGridLayout をやめる
        # layout.setContentsMargins(0,0,0,5)
        # layout.setSpacing(5)

        self.project_name_label = QLabel("工事名:")
        self.project_name_value = QLabel("---") # 太字スタイルは後でまとめて適用
        self.client_name_label = QLabel("相手先名:")
        self.client_name_value = QLabel("---")
        self.period_label = QLabel("工　　期:") # 工期ラベル追加
        self.period_value = QLabel("---")      # 工期表示用ラベル追加
        self.total_label = QLabel("合計(税込):")
        self.total_value = QLabel("---")
        self.subtotal_label = QLabel("工事金額:")
        self.subtotal_value = QLabel("---")
        self.tax_label = QLabel("消費税額:")
        self.tax_value = QLabel("---")

        # 値ラベルに太字スタイルを適用
        value_style = "font-weight: bold;"
        self.project_name_value.setStyleSheet(value_style)
        self.client_name_value.setStyleSheet(value_style)
        self.period_value.setStyleSheet(value_style) # 工期にも太字スタイル適用
        self.total_value.setStyleSheet(value_style)
        self.subtotal_value.setStyleSheet(value_style)
        self.tax_value.setStyleSheet(value_style)

        # --- 新しいレイアウト (QHBoxLayout + QVBoxLayout) ---
        main_h_layout = QHBoxLayout() # 全体をまとめる水平レイアウト
        main_h_layout.setContentsMargins(0, 0, 0, 5)
        main_h_layout.setSpacing(20) # 左右のブロック間のスペース

        # 左側ブロック (工事名、宛先名、工期)
        left_v_layout = QVBoxLayout()
        left_v_layout.setSpacing(5)
        proj_h_layout = QHBoxLayout()
        proj_h_layout.addWidget(self.project_name_label)
        proj_h_layout.addWidget(self.project_name_value, 1) # stretch=1 で伸びるように
        client_h_layout = QHBoxLayout()
        client_h_layout.addWidget(self.client_name_label)
        client_h_layout.addWidget(self.client_name_value, 1) # stretch=1 で伸びるように
        period_h_layout = QHBoxLayout() # 工期用レイアウト追加
        period_h_layout.addWidget(self.period_label)
        period_h_layout.addWidget(self.period_value, 1) # stretch=1 で伸びるように
        left_v_layout.addLayout(proj_h_layout)
        left_v_layout.addLayout(client_h_layout)
        left_v_layout.addLayout(period_h_layout) # 工期レイアウトを追加
        # left_v_layout.addStretch() # 縦方向の伸縮は不要なので削除

        # 右側ブロック (金額) - QGridLayout を使うと揃えやすい
        right_grid_layout = QGridLayout()
        right_grid_layout.setSpacing(5)
        right_grid_layout.addWidget(self.subtotal_label, 0, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.subtotal_value, 0, 1, Qt.AlignRight | Qt.AlignVCenter) # 右寄せ追加
        right_grid_layout.addWidget(self.tax_label, 1, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.tax_value, 1, 1, Qt.AlignRight | Qt.AlignVCenter) # 右寄せ追加
        right_grid_layout.addWidget(self.total_label, 2, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.total_value, 2, 1, Qt.AlignRight | Qt.AlignVCenter) # 右寄せ追加

        main_h_layout.addLayout(left_v_layout, 1) # 左側を stretch=1 で優先的に伸ばす
        main_h_layout.addLayout(right_grid_layout) # 右側は固定幅

        # 全体レイアウトと区切り線
        final_layout = QVBoxLayout(header_widget)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addLayout(main_h_layout)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        final_layout.addWidget(line)
        # header_widget.setLayout(layout) # final_layout を設定済み
        return header_widget


    def update_header(self, project_name, client_name, period_text, total, subtotal, tax): # period_text 引数を追加
        """ヘッダーの情報を更新する"""
        self.project_name_value.setText(project_name if project_name else "---")
        self.client_name_value.setText(client_name if client_name else "---")
        self.period_value.setText(period_text if period_text else "---") # 工期を設定
        self.total_value.setText(total if total else "---")
        self.subtotal_value.setText(subtotal if subtotal else "---")
        self.tax_value.setText(tax if tax else "---")

    # --- スロットメソッド ---
    def _create_unit_combobox(self) -> QComboBox:
        """単位選択用の QComboBox を作成して返す"""
        combo = QComboBox()
        combo.addItems(self.unit_list)
        combo.setEditable(True) # 編集可能にする
        combo.setInsertPolicy(QComboBox.NoInsert) # 入力補完時に自動追加しない

        # コンプリータの設定 (入力補完)
        completer = QCompleter(self.unit_list)
        completer.setCaseSensitivity(Qt.CaseInsensitive) # 大文字小文字を区別しない
        completer.setFilterMode(Qt.MatchContains) # 部分一致で補完
        combo.setCompleter(completer)

        # --- ドロップダウンリストのスタイルを明示的に設定 ---
        # 文字色を黒、背景色を白に設定
        combo.view().setStyleSheet("color: black; background-color: white;")
        # --- QComboBox 本体（表示部分）の文字色も設定 ---
        # ドロップダウンリストとは別に設定が必要
        combo.setStyleSheet("color: black;")

        # QComboBox の値が変更されたときのシグナル接続 (UNDO/REDO用)
        # cellChanged の代わりに QComboBox のシグナルを使う
        combo.currentTextChanged.connect(self._on_unit_changed)
        # 編集開始前の値を取得するために focusGained イベントも利用
        combo.lineEdit().editingFinished.connect(lambda w=combo.lineEdit(): self._unit_editing_finished(w)) # 編集完了時
        combo.view().pressed.connect(lambda index, w=combo: self._unit_selection_started(w)) # ドロップダウン選択開始時

        return combo
        # デバッグ: 作成されたコンボボックスのアイテム数を確認
        # print(f"DEBUG: Created QComboBox with {combo.count()} items: {self.unit_list}")

    @Slot(int, int)
    def _on_cell_pressed(self, row, col):
        """セルがクリックされたとき（編集開始前）に元の値を記録"""
        item = self.table.item(row, col)
        if item and (item.flags() & Qt.ItemIsEditable) and col != self.COL_UNIT: # 単位列以外
            self.current_editing_cell = (row, col)
            self.old_text = item.text()
            self.is_editing = True # 編集中フラグを立てる
            # print(f"Editing started: ({row}, {col}), Old text: '{self.old_text}'") # Debug
        else:
            self.current_editing_cell = None
            self.is_editing = False

    # --- 単位 QComboBox 用のスロット ---
    def _unit_selection_started(self, combo_box: QComboBox):
        """QComboBox のドロップダウン選択開始時に元の値を記録"""
        row = self.table.indexAt(combo_box.pos()).row()
        if row != -1:
            self.current_editing_cell = (row, self.COL_UNIT)
            self.old_text = combo_box.currentText() # 選択開始時のテキストを記録
            self.is_editing = True
            # print(f"Unit selection started: ({row}, {self.COL_UNIT}), Old text: '{self.old_text}'") # Debug

    def _unit_editing_finished(self, line_edit: QLineEdit):
        """QComboBox の LineEdit 編集完了時に元の値を記録 (フォーカス喪失時など)"""
        combo_box = line_edit.parent()
        if isinstance(combo_box, QComboBox):
             row = self.table.indexAt(combo_box.pos()).row()
             if row != -1 and self.is_editing and self.current_editing_cell == (row, self.COL_UNIT):
                 # is_editing フラグが立っている場合のみ (currentTextChanged より後に呼ばれる想定)
                 # print(f"Unit editing finished: ({row}, {self.COL_UNIT})") # Debug
                 pass # old_text は currentTextChanged で使う

    @Slot(str)
    def _on_unit_changed(self, new_text: str):
        """単位 QComboBox のテキストが変更されたとき"""
        sender_combo = self.sender()
        if not isinstance(sender_combo, QComboBox) or not self.is_editing:
            return # QComboBox 以外からの呼び出し、または編集中でない場合は無視

        row = self.table.indexAt(sender_combo.pos()).row()
        if row == -1 or self.current_editing_cell != (row, self.COL_UNIT): return

        # print(f"Unit changed: ({row}, {self.COL_UNIT}), Old='{self.old_text}', New='{new_text}'") # Debug
        if hasattr(self, 'old_text') and self.old_text != new_text:
            command = ChangeItemCommand(self.table, row, self.COL_UNIT, self.old_text, new_text)
            self.undo_stack.push(command)
        self.is_editing = False # 編集終了

    @Slot(str, int)
    def _handle_context_action(self, action_name: str, row: int):
        """右クリックメニューのアクションを処理するスロット"""
        # print(f"Context action requested: {action_name}, row: {row}") # Debug
        if action_name == 'add':
            if row >= 0: self.table.selectRow(row) # 右クリックした行を選択
            else: self.table.clearSelection()      # 行外なら選択解除
            self.add_row() # 既存の add_row を呼び出す
        elif action_name == 'remove':
            if row >= 0:
                self.table.selectRow(row) # 対象行を選択状態にする
                self.remove_row() # 既存の remove_row を呼び出す
        elif action_name == 'duplicate':
            if row >= 0:
                self.table.selectRow(row) # 対象行を選択状態にする
                self.duplicate_row() # 既存の duplicate_row を呼び出す

# detail_page_widget.py の _on_cell_changed メソッドを修正

    @Slot(int, int)
    def _on_cell_changed(self, row, col):
        """テーブルのセル内容が変更されたときに呼び出されるスロット"""
        if not self.is_editing or self.current_editing_cell != (row, col):
            return
        if col == self.COL_UNIT:
            return

        item = self.table.item(row, col)
        if not item: return
        new_text = item.text()
        is_valid_input = True

        # --- 数値列の入力検証 ---
        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            try:
                cleaned_text = new_text.replace(",", "").replace("￥", "").strip()
                value = float(cleaned_text or 0.0)

                # 数値変換成功 -> デフォルトの背景/文字色に戻す
                default_bg_color = self.table.palette().base().color()
                default_fg_color = QColor("black") # デフォルト文字色は黒
                item.setBackground(default_bg_color)
                item.setForeground(QBrush(default_fg_color)) # setForeground で文字色をデフォルトに戻す
                # 最後にエラーが発生したセルが修正された場合、エラー情報をクリアし、ステータスバーもクリア
                if self.last_error_info and self.last_error_info[:2] == (row, col):
                    self.last_error_info = None
                    self.status_message_requested.emit("") # ステータスバーのメッセージをクリア
                # ↑↑↑ 正しい修正 ↑↑↑

                # --- 数量フォーマット処理 (必要なら) ---
                # if col == self.COL_QUANTITY:
                #     formatted_text = f"{value:.1f}"
                #     # setText を直接呼ばずに ChangeItemCommand で処理するのが Undo/Redo では望ましい
                #     # if item.text() != formatted_text:
                #     #     command = ChangeItemCommand(self.table, row, col, new_text, formatted_text, "数量フォーマット")
                #     #     self.undo_stack.push(command)
                #     # new_text = formatted_text # コマンドに渡す new_text も更新
                #     pass

            except ValueError:
                # 数値変換失敗 -> エラー背景色(ピンク)と文字色(赤)を設定
                error_bg_color = QColor(COLOR_ERROR_BG) # Pink
                error_fg_color = QColor("red") # エラー文字色は赤
                item.setBackground(error_bg_color)
                item.setForeground(QBrush(error_fg_color)) # setForeground で文字色を赤に設定
                # エラーメッセージをステータスバーに表示要求
                error_message = f"行 {row + 1}, 列 '{self.HEADERS[col]}' の入力が無効です: '{new_text}'"
                self.status_message_requested.emit(error_message)
                # エラー情報を記録
                self.last_error_info = (row, col, error_message)
                # 画面フラッシュを要求
                self.screen_flash_requested.emit()
                # ↑↑↑ 正しい修正 ↑↑↑
                is_valid_input = False

        # --- アライメント設定 ---
        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # --- UNDO コマンドの作成 ---
        if hasattr(self, 'old_text') and self.old_text != new_text:
            command = ChangeItemCommand(self.table, row, col, self.old_text, new_text)
            self.undo_stack.push(command)

        # --- 金額計算 ---
        # is_valid_input が True の場合のみ計算を実行する
        if is_valid_input and (col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE):
            # ... (既存の金額計算ロジックは変更なし) ...
            quantity_item = self.table.item(row, self.COL_QUANTITY)
            unit_price_item = self.table.item(row, self.COL_UNIT_PRICE)
            quantity_str = quantity_item.text() if quantity_item else "0"
            unit_price_str = unit_price_item.text() if unit_price_item else "0"
            try:
                quantity = float(quantity_str.replace(",", "").replace("￥", "").strip() or 0)
                unit_price = float(unit_price_str.replace(",", "").replace("￥", "").strip() or 0)
                amount = quantity * unit_price
            except ValueError:
                amount = 0.0
            amount_item = self.table.item(row, self.COL_AMOUNT)
            if amount_item is None:
                 amount_item = QTableWidgetItem()
                 self.table.setItem(row, self.COL_AMOUNT, amount_item)
                 amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
                 amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.table.blockSignals(True)
            amount_item.setText(f"{amount:,.0f}")
            self.table.blockSignals(False)

        self.is_editing = False # 編集終了
    def _update_detail_totals(self):
        """明細テーブルの合計金額を計算し、ヘッダーを更新する"""
        from constants import TAX_RATE # 消費税率をインポート

        subtotal = 0.0
        for row in range(self.table.rowCount()):
            amount_item = self.table.item(row, self.COL_AMOUNT)
            if amount_item and amount_item.text():
                try:
                    # フォーマットされた文字列から数値に戻す
                    amount_val = float(amount_item.text().replace(",", "").replace("￥", "").strip())
                    subtotal += amount_val
                except ValueError:
                    print(f"警告: 行 {row+1} の金額 '{amount_item.text()}' を数値に変換できませんでした。")

        tax = int(subtotal * TAX_RATE) # 消費税計算 (切り捨て)
        total = int(subtotal) + tax    # 税込合計

        # ヘッダーウィジェットの update_header を呼び出して表示を更新
        # update_header は文字列を受け取る想定なのでフォーマットする
        self.update_header(
            self.project_name_value.text(), # 工事名、宛先名、工期は現在の値を維持
            self.client_name_value.text(),
            self.period_value.text(),       # 工期テキストを追加
            f"￥{total:,}",
            f"￥{int(subtotal):,}", # 工事金額も整数カンマ区切り
            f"￥{tax:,}"
        )

    # --- 行操作スロット ---
    @Slot()
    def add_row(self):
        """
        行を追加する。
        行が選択されていない場合は最下部に、選択されている場合はその下に追加する。
        """
        current_row = self.table.currentRow()
        insert_pos = -1

        if current_row < 0: # 行が選択されていない場合
            insert_pos = self.table.rowCount() # 最下部
        else: # 行が選択されている場合
            insert_pos = current_row + 1 # 選択行の下

        command = InsertRowCommand(self.table, insert_pos, self._initialize_row, description="行追加")
        self.undo_stack.push(command)
        # テーブル操作と合計更新はコマンドの redo/undo と indexChanged で行われる

# detail_page_widget.py の DetailPageWidget クラス内

    # ( _get_row_data ヘルパーメソッドを事前に追加しておくと便利 )
    def _get_row_data(self, row: int) -> List[Optional[QTableWidgetItem | tuple]]:
         """指定された行のデータを取得 (アイテムはクローン、ウィジェットは情報タプル)"""
         data = []
         for col in range(self.table.columnCount()):
             widget = self.table.cellWidget(row, col)
             item = self.table.item(row, col)
             if widget and isinstance(widget, QComboBox):
                 data.append((type(widget), {'currentText': widget.currentText()}))
             elif item:
                 data.append(item.clone())
             else:
                 data.append(None)
         return data

# detail_page_widget.py 内 DetailPageWidget.remove_row

    @Slot()
    def remove_row(self):
        """現在選択されている複数の行を削除する (UNDO対応 - 複数行コマンド版)"""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "行削除", "削除する行が選択されていません。")
            return

        # 選択されている行のインデックスを取得し、重複を除いて昇順にソート
        selected_rows = sorted(list(set(index.row() for range_ in selected_ranges for index in self.table.selectedIndexes() if index.row() >= 0)))

        if not selected_rows: return

        # --- 削除するすべての行のデータを事前に取得 ---
        rows_data_to_save = {}
        for row in selected_rows:
            rows_data_to_save[row] = self._get_row_data(row) # ヘルパー関数を使用

        # --- 単一の複数行削除コマンドを作成してプッシュ ---
        # (マクロは不要)
        command = RemoveMultipleRowsCommand(self.table, selected_rows, rows_data_to_save)
        self.undo_stack.push(command)

        # 合計更新は stack.indexChanged でトリガーされる想定
    @Slot()
    def duplicate_row(self):
        """現在選択されている行を複製して、その下に挿入する (UNDO対応)"""
        current_row = self.table.currentRow()
        if current_row >= 0: # 行が選択されている場合のみ
            # 複製する行のデータを取得 (クローンしておく)
            row_data_cloned = []
            for col in range(self.table.columnCount()):
                widget = self.table.cellWidget(current_row, col)
                item = self.table.item(current_row, col)
                if widget and isinstance(widget, QComboBox):
                    # QComboBox の場合はクラスと現在のテキストをタプルで保存
                    row_data_cloned.append((type(widget), {'currentText': widget.currentText()}))
                elif item:
                    # QTableWidgetItem の場合はクローンして保存
                    row_data_cloned.append(item.clone())
                else:
                    # それ以外は None
                    row_data_cloned.append(None)

            command = DuplicateRowCommand(self.table, current_row, row_data_cloned)
            self.undo_stack.push(command)
            # テーブル操作と合計更新はコマンドの redo/undo と indexChanged で行われる
        else:
             # 選択されていない場合はメッセージ表示
             QMessageBox.warning(self, "行複写エラー", "複写する行が選択されていません。")

    def _initialize_row(self, row):
        """指定された行のセルを初期化する (特に金額列を編集不可に)"""
        self.table.blockSignals(True) # 初期化中のシグナルをブロック
        # 金額セルを作成し、編集不可・右寄せに設定
        amount_item = QTableWidgetItem("0") # 初期値は 0
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, self.COL_AMOUNT, amount_item)

        # 単位列に QComboBox を設定
        self.table.setCellWidget(row, self.COL_UNIT, self._create_unit_combobox())
        # デバッグ: 設定されたウィジェットを確認
        print(f"DEBUG: Initialized ComboBox at ({row}, {self.COL_UNIT}): {self.table.cellWidget(row, self.COL_UNIT)}")

        # 他の列も必要に応じて初期化 (例: 空のアイテムを設定)
        for col in range(self.NUM_COLS):
            if col != self.COL_AMOUNT: # 金額列以外
                if self.table.item(row, col) is None: # セルがまだなければ作成
                    self.table.setItem(row, col, QTableWidgetItem(""))

        self.table.blockSignals(False) # ブロック解除
    # --- ドラッグ＆ドロップ イベントハンドラは DraggableTableWidget に移動 ---

    # --- データ取得用メソッド (main.py から呼ばれる) ---
    def get_current_subtotal(self) -> str:
        return self.subtotal_value.text() if hasattr(self, 'subtotal_value') else ""

    def get_current_tax(self) -> str:
        return self.tax_value.text() if hasattr(self, 'tax_value') else ""

    def get_current_total(self) -> str:
        return self.total_value.text() if hasattr(self, 'total_value') else ""
