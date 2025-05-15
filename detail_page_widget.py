# detail_page_widget.py (項目変更、utils.py連携 最終版)
import operator
import os
import csv
import pickle
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation # InvalidOperation もインポート


from PySide6.QtWidgets import (
    QMessageBox, QComboBox, QCompleter, QLineEdit,
    QWidget, QTableWidget, QVBoxLayout, QTableWidgetItem, QHeaderView, QApplication, QFileDialog,
    QLabel, QPushButton, QGridLayout, QFrame, QHBoxLayout, QAbstractItemView
)
from PySide6.QtCore import (
    Qt, Signal, Slot, QEvent, QModelIndex, QItemSelectionModel, QMimeData, QPoint, QByteArray
)
from PySide6.QtGui import (
    QPalette, QColor, QDropEvent, QDragEnterEvent, QDragMoveEvent,
    QContextMenuEvent, QAction, QKeySequence, QBrush, QDrag, QMouseEvent, QKeyEvent
)

from typing import List, Optional, Callable, Union, Type, Dict, Any, Tuple

from constants import (
    WIDGET_BASE_STYLE, COLOR_LIGHT_GRAY, COLOR_WHITE, COLOR_ERROR_BG,
    DATABASE_FILE_NAME, TAX_RATE
)
from commands import (
    AddRowCommand, InsertRowCommand, RemoveRowCommand, ChangeItemCommand,
    DuplicateRowCommand, RemoveMultipleRowsCommand, DuplicateMultipleRowsCommand,
    MoveMultipleRowsCommand
)

from utils import format_currency, format_quantity, parse_number

# (DraggableTableWidget クラスは変更なしのため、ここでは省略します)
# (もし DraggableTableWidget が別ファイルなら、このファイルから削除しても構いません)
class DraggableTableWidget(QTableWidget):
    row_moved = Signal(int, int)
    context_action_requested = Signal(str, int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack = None
        self._drag_start_position: Optional[QPoint] = None
        self._configure_drag_drop()
    def _configure_drag_drop(self):
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    def _get_row_data_for_drag(self, row: int) -> List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict[str, Any]]]]]:
        data = []
        for col in range(self.columnCount()):
            widget = self.cellWidget(row, col)
            item = self.item(row, col)
            if widget and isinstance(widget, QComboBox):
                data.append((type(widget), {'currentText': widget.currentText()}))
            elif item:
                try:
                    flags_val = item.flags().value
                    alignment_val = item.textAlignment()
                    data.append({'text': item.text(), 'flags': flags_val, 'textAlignment': alignment_val})
                except TypeError: # エラー処理は簡略化
                    data.append({'text': item.text(), 'flags': None, 'textAlignment': None})
            else:
                data.append(None)
        return data
    def startDrag(self, supportedActions: Qt.DropAction):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes: return
        selected_rows_indices = sorted(list(set(idx.row() for idx in selected_indexes)))
        if not selected_rows_indices: return
        drag_data_payload = [self._get_row_data_for_drag(row_idx) for row_idx in selected_rows_indices]
        mime_data = QMimeData()
        encoded_data_qbytearray = QByteArray(pickle.dumps((selected_rows_indices, drag_data_payload)))
        mime_data.setData("application/x-estimate-app-rows", encoded_data_qbytearray)
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(supportedActions)
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.pos()
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start_position is None:
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_position).manhattanLength() >= QApplication.startDragDistance():
            # スーパークラスがドラッグ開始を処理
            pass
        super().mouseMoveEvent(event)
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"): event.acceptProposedAction()
        else: event.ignore()
    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"): event.acceptProposedAction()
        else: event.ignore()
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"):
            encoded_data_qbytearray = event.mimeData().data("application/x-estimate-app-rows")
            encoded_data_bytes = b""
            if encoded_data_qbytearray:
                mem_view = encoded_data_qbytearray.data()
                if mem_view: encoded_data_bytes = bytes(mem_view)
            try:
                if not encoded_data_bytes:
                    event.ignore(); return
                source_indices, moved_rows_data = pickle.loads(encoded_data_bytes)
            except Exception as e:
                print(f"Error decoding drag data: {e}"); event.ignore(); return
            drop_pos_in_table = event.position().toPoint()
            target_index = self.indexAt(drop_pos_in_table)
            dest_row_before_removal = target_index.row() if target_index.isValid() else self.rowCount()
            if not source_indices: event.ignore(); return
            event.setDropAction(Qt.DropAction.MoveAction); event.accept()
            command = MoveMultipleRowsCommand(self, source_indices, moved_rows_data, dest_row_before_removal)
            if not command.is_noop:
                if self.undo_stack: self.undo_stack.push(command)
                else: command.redo()
        else: event.ignore()
    def keyPressEvent(self, event: QKeyEvent): # QKeyEventに変更
        key = event.key()
        modifiers = event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_index = self.currentIndex()
            if not current_index.isValid(): super().keyPressEvent(event); return
            row, col = current_index.row(), current_index.column()
            next_row, next_col = row, col
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                if col > 0: next_col -= 1
                elif row > 0: next_row -= 1; next_col = self.columnCount() - 1
                else: super().keyPressEvent(event); return
            else:
                if col < self.columnCount() - 1: next_col += 1
                elif row < self.rowCount() - 1: next_row += 1; next_col = 0
                else: super().keyPressEvent(event); return
            next_index = self.model().index(next_row, next_col)
            if next_index.isValid():
                self.setCurrentIndex(next_index); self.edit(next_index)
            event.accept()
        else: super().keyPressEvent(event)
    def contextMenuEvent(self, event: QContextMenuEvent):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self); menu.setStyleSheet("color: black;")
        index = self.indexAt(event.pos())
        clicked_row = index.row() if index.isValid() else -1
        add_action = QAction("行追加", self); remove_action = QAction("行削除", self); duplicate_action = QAction("複写", self)
        add_action.triggered.connect(lambda: self.context_action_requested.emit('add', clicked_row))
        remove_action.triggered.connect(lambda: self.context_action_requested.emit('remove', clicked_row))
        duplicate_action.triggered.connect(lambda: self.context_action_requested.emit('duplicate', clicked_row))
        if clicked_row >= 0: remove_action.setEnabled(True); duplicate_action.setEnabled(True)
        else: remove_action.setEnabled(False); duplicate_action.setEnabled(False)
        menu.addAction(add_action); menu.addAction(remove_action); menu.addAction(duplicate_action)
        menu.exec(event.globalPos())

# --------------------------------------------------------------------------
# 明細ページウィジェット
# --------------------------------------------------------------------------
class DetailPageWidget(QWidget):
    cover_requested = Signal()
    status_message_requested = Signal(str)
    screen_flash_requested = Signal()

    # --- 列定義の変更 ---
    COL_NAME = 0
    COL_SPECIFICATION = 1
    COL_QUANTITY = 2
    COL_UNIT = 3
    COL_UNIT_PRICE = 4
    COL_AMOUNT = 5
    COL_SUMMARY = 6
    NUM_COLS = 7

    HEADERS = ["名称", "仕様", "数量", "単位", "単価", "金額", "摘要"]
    INITIAL_WIDTHS = [180, 220, 70, 60, 90, 100, 180] # 幅を調整

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.is_editing = False
        self.current_editing_cell: Optional[Tuple[int, int]] = None
        self.old_text: Optional[str] = None
        self.db_file_path = os.path.join(os.getcwd(), DATABASE_FILE_NAME)
        self.current_estimate_id: Optional[int] = None
        self.last_error_info = None
        self.unit_list = self._load_units()

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor('white'))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        detail_page_style = WIDGET_BASE_STYLE + f"""
                QTableWidget {{
                    alternate-background-color: {COLOR_LIGHT_GRAY};
                }}
        """
        self.setStyleSheet(detail_page_style)

        self._setup_ui()
        self.table.cellPressed.connect(self._on_cell_pressed)
        self.table.cellChanged.connect(self._on_cell_changed)

        if hasattr(self, 'table'):
            self.table.context_action_requested.connect(self._handle_context_action)
        # self.setAcceptDrops(True) # テーブルがDropを受け付けるのでWidget自体は不要かも

    def _load_units(self) -> list[str]:
        units_file = "units.txt"
        default_units = ["式", "個", "m", "m2", "本", "セット"]
        try:
            with open(units_file, "r", encoding="utf-8") as f:
                units = [line.strip() for line in f if line.strip()]
            return units if units else default_units
        except FileNotFoundError:
            return default_units
        except Exception as e:
            print(f"エラー: {units_file} の読み込み中にエラーが発生しました: {e}")
            return default_units

    def _setup_ui(self):
        header_frame = self._create_header_widget()
        self.table = DraggableTableWidget() # DraggableTableWidget を使用
        self.table.undo_stack = self.undo_stack
        self._configure_table()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        main_layout.addWidget(header_frame)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def _configure_table(self):
        if not hasattr(self, 'table'): return

        self.table.setColumnCount(self.NUM_COLS)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        header = self.table.horizontalHeader()
        for i, width in enumerate(self.INITIAL_WIDTHS):
            header.resizeSection(i, width)

        self.table.setAlternatingRowColors(True)
        # DraggableTableWidget側で設定済みなので不要
        # self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setVisible(True)
        self.table.verticalHeader().setVisible(True) # 行番号表示のためTrueを推奨

        test_data = [
            {"name": "テスト名称1", "specification": "テスト仕様詳細1 H=1000, W=2000", "quantity": 10.0, "unit": "式", "unit_price": 1000.0, "summary": "テスト摘要1"},
            {"name": "テスト名称2", "specification": "標準品", "quantity": 5.0, "unit": "個", "unit_price": 500.0, "summary": ""},
        ]

        self.table.setRowCount(len(test_data)) # 初期行数をテストデータに合わせる
        self.table.blockSignals(True)
        for row, data_row in enumerate(test_data): # 変数名変更
            name_item = QTableWidgetItem(data_row["name"])
            specification_item = QTableWidgetItem(data_row["specification"])
            quantity_item = QTableWidgetItem(format_quantity(data_row["quantity"])) # utils.format_quantity を使用
            unit_price_item = QTableWidgetItem(format_currency(data_row["unit_price"])) # utils.format_currency を使用
            summary_item = QTableWidgetItem(data_row["summary"])

            quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            unit_price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # 金額計算 (Decimalで行うのが望ましいが、ここではfloatで)
            try:
                amount_val = Decimal(str(data_row["quantity"])) * Decimal(str(data_row["unit_price"]))
            except InvalidOperation:
                amount_val = Decimal('0')
            amount_item = QTableWidgetItem(format_currency(amount_val))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, self.COL_NAME, name_item)
            self.table.setItem(row, self.COL_SPECIFICATION, specification_item)
            self.table.setItem(row, self.COL_QUANTITY, quantity_item)
            unit_combo = self._create_unit_combobox()
            unit_combo.setCurrentText(data_row.get("unit", ""))
            self.table.setCellWidget(row, self.COL_UNIT, unit_combo)
            self.table.setItem(row, self.COL_UNIT_PRICE, unit_price_item)
            self.table.setItem(row, self.COL_AMOUNT, amount_item)
            self.table.setItem(row, self.COL_SUMMARY, summary_item)
        self.table.blockSignals(False)
        self._update_detail_totals() # 初期データ設定後に合計を更新

    def _create_header_widget(self) -> QWidget:
        # (変更なしのため省略 - 前回のコードを参照)
        header_widget = QWidget()
        self.project_name_label = QLabel("工事名:")
        self.project_name_value = QLabel("---")
        self.client_name_label = QLabel("相手先名:")
        self.client_name_value = QLabel("---")
        self.period_label = QLabel("工　　期:")
        self.period_value = QLabel("---")
        self.total_label = QLabel("合計(税込):")
        self.total_value = QLabel("---")
        self.subtotal_label = QLabel("工事金額:")
        self.subtotal_value = QLabel("---")
        self.tax_label = QLabel("消費税額:")
        self.tax_value = QLabel("---")
        value_style = "font-weight: bold;"
        for label_widget in [self.project_name_value, self.client_name_value, self.period_value, self.total_value, self.subtotal_value, self.tax_value]:
            label_widget.setStyleSheet(value_style)
        main_h_layout = QHBoxLayout(); main_h_layout.setContentsMargins(0,0,0,5); main_h_layout.setSpacing(20)
        left_v_layout = QVBoxLayout(); left_v_layout.setSpacing(5)
        for label_widget, value_widget in [(self.project_name_label, self.project_name_value), (self.client_name_label, self.client_name_value), (self.period_label, self.period_value)]:
            h_layout = QHBoxLayout(); h_layout.addWidget(label_widget); h_layout.addWidget(value_widget, 1); left_v_layout.addLayout(h_layout)
        right_grid_layout = QGridLayout(); right_grid_layout.setSpacing(5)
        right_grid_layout.addWidget(self.subtotal_label, 0, 0, Qt.AlignmentFlag.AlignRight); right_grid_layout.addWidget(self.subtotal_value, 0, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_grid_layout.addWidget(self.tax_label, 1, 0, Qt.AlignmentFlag.AlignRight); right_grid_layout.addWidget(self.tax_value, 1, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_grid_layout.addWidget(self.total_label, 2, 0, Qt.AlignmentFlag.AlignRight); right_grid_layout.addWidget(self.total_value, 2, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        main_h_layout.addLayout(left_v_layout, 1); main_h_layout.addLayout(right_grid_layout)
        final_layout = QVBoxLayout(header_widget); final_layout.setContentsMargins(0,0,0,0); final_layout.addLayout(main_h_layout)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFrameShadow(QFrame.Shadow.Sunken); final_layout.addWidget(line)
        return header_widget


    def update_header(self, project_name, client_name, period_text, total, subtotal, tax):
        # (変更なしのため省略 - 前回のコードを参照)
        self.project_name_value.setText(project_name if project_name else "---")
        self.client_name_value.setText(client_name if client_name else "---")
        self.period_value.setText(period_text if period_text else "---")
        self.total_value.setText(total if total else "---") # main.py から "---" が渡される
        self.subtotal_value.setText(subtotal if subtotal else "---") # main.py から "---" が渡される
        self.tax_value.setText(tax if tax else "---") # main.py から "---" が渡される

    def _create_unit_combobox(self) -> QComboBox:
        # (変更なしのため省略 - 前回のコードを参照)
        combo = QComboBox(); combo.addItems(self.unit_list); combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); completer = QCompleter(self.unit_list)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer); combo.view().setStyleSheet("color: black; background-color: white;"); combo.setStyleSheet("color: black;")
        combo.currentTextChanged.connect(self._on_unit_changed)
        return combo

    @Slot(int, int)
    def _on_cell_pressed(self, row, col):
        # (変更なしのため省略 - 前回のコードを参照)
        self.current_editing_cell = (row, col); self.is_editing = True
        if col == self.COL_UNIT:
            widget = self.table.cellWidget(row, col)
            if isinstance(widget, QComboBox): self.old_text = widget.currentText()
        else:
            item = self.table.item(row, col)
            if item and (item.flags() & Qt.ItemFlag.ItemIsEditable): self.old_text = item.text()
            else: self.is_editing = False; self.current_editing_cell = None

    @Slot(str)
    def _on_unit_changed(self, new_text: str):
        # (変更なしのため省略 - 前回のコードを参照)
        sender_combo = self.sender()
        if not isinstance(sender_combo, QComboBox) or not self.is_editing: return
        row = -1
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, self.COL_UNIT) == sender_combo: row = r; break
        if row == -1 or self.current_editing_cell != (row, self.COL_UNIT): return
        if hasattr(self, 'old_text') and self.old_text is not None and self.old_text != new_text:
            command = ChangeItemCommand(self.table, row, self.COL_UNIT, self.old_text, new_text)
            if self.undo_stack: self.undo_stack.push(command)
            else: command.redo()
        # _on_cell_changed が呼ばれるので、そこで _update_detail_totals() がトリガーされるはず
        # もし QComboBox の変更が _on_cell_changed をトリガーしない場合は、ここで直接呼ぶ
        self._update_detail_totals()


    @Slot(str, int)
    def _handle_context_action(self, action_name: str, row: int):
        # (変更なしのため省略 - 前回のコードを参照)
        if action_name == 'add':
            if row >= 0: self.table.selectRow(row)
            else: self.table.clearSelection()
            self.add_row()
        elif action_name == 'remove':
            if row >= 0:
                selected_indexes = self.table.selectedIndexes()
                is_clicked_row_selected = any(idx.row() == row for idx in selected_indexes)
                if not is_clicked_row_selected: self.table.clearSelection(); self.table.selectRow(row)
                self.remove_row()
        elif action_name == 'duplicate':
            if row >= 0:
                selected_indexes = self.table.selectedIndexes()
                is_clicked_row_selected = any(idx.row() == row for idx in selected_indexes)
                if not is_clicked_row_selected: self.table.clearSelection(); self.table.selectRow(row)
                self.duplicate_row()


    @Slot(int, int)
    def _on_cell_changed(self, row, col):
        # 編集中でない、または編集対象セルと一致しない場合は早期リターン
        # ただし、QComboBox(単位列)の場合は is_editing が先にFalseになることがあるので、
        # current_editing_cell が一致していれば処理を続けるようにする
        if not self.is_editing and self.current_editing_cell != (row, col):
            # プログラムによる変更で、かつ合計更新が必要な列の場合のみ対応するなどの考慮も可能
            # ここでは、ユーザー起因でない変更は基本的に無視するか、別途ハンドリング
            if col in [self.COL_QUANTITY, self.COL_UNIT_PRICE, self.COL_AMOUNT]:
                 # プログラムからの変更でも合計は更新した方が良い場合がある
                 # self._update_detail_totals()
                 pass # 今回はユーザー編集起因の問題に絞る
            return

        if col == self.COL_UNIT: # 単位列の変更は _on_unit_changed で処理済みと仮定
            self.is_editing = False
            self.current_editing_cell = None
            # _on_unit_changed で _update_detail_totals が呼ばれていることを確認
            return

        item = self.table.item(row, col)
        if not item: return

        # 編集後のセルに入っている実際のテキストを取得
        current_text_in_item = item.text()
        # コマンドに渡すための新しいテキスト（フォーマット後）
        new_text_for_command = current_text_in_item
        # 表示用のフォーマット済みテキスト
        formatted_display_text = current_text_in_item

        is_valid_input = True

        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            try:
                # utils.parse_number を使って文字列を数値(float)に変換
                value = parse_number(current_text_in_item)
                # ここで value に対する追加のバリデーション（例: マイナス値でないか等）も可能

                # エラー表示をクリア (バリデーション成功時)
                default_bg_brush = self.table.palette().base()
                default_fg_brush = self.table.palette().text()
                item.setBackground(default_bg_brush)
                item.setForeground(default_fg_brush)
                if self.last_error_info and self.last_error_info[:2] == (row, col):
                    self.last_error_info = None
                    self.status_message_requested.emit("", 100) # 短時間でクリアメッセージ

                # 表示用テキストをフォーマット
                if col == self.COL_QUANTITY:
                    formatted_display_text = format_quantity(value)
                elif col == self.COL_UNIT_PRICE:
                    formatted_display_text = format_currency(value) # 「￥」付きになる

                # UI上のセルのテキストをフォーマット済みのものに更新
                # この setText が再度 _on_cell_changed をトリガーするのを防ぐため、
                # テキストが実際に変更される場合のみ実行し、かつ blockSignals を使用する
                if item.text() != formatted_display_text:
                    self.table.blockSignals(True)
                    item.setText(formatted_display_text)
                    self.table.blockSignals(False)
                
                new_text_for_command = formatted_display_text # コマンドにもフォーマット済みテキストを渡す

            except ValueError as e: # parse_number がエラーを出すか、追加バリデーションで発生
                error_bg_color = QColor(COLOR_ERROR_BG)
                error_fg_color = QColor("red")
                item.setBackground(error_bg_color)
                item.setForeground(QBrush(error_fg_color))
                error_message = f"行 {row + 1}, 列 '{self.HEADERS[col]}' の入力が無効です: '{current_text_in_item}' ({e})"
                self.status_message_requested.emit(error_message, 7000)
                self.last_error_info = (row, col, error_message)
                # self.screen_flash_requested.emit() # 必要に応じて
                is_valid_input = False
                new_text_for_command = current_text_in_item # エラーの場合は元の入力テキストをコマンドに

        # 数量と単価列は右寄せ（フォーマット後にも適用されるように）
        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Undo/Redoコマンドの処理
        # old_text は _on_cell_pressed で取得した、編集前のフォーマット済みテキストのはず
        if hasattr(self, 'old_text') and self.old_text is not None and \
           self.old_text != new_text_for_command: # フォーマット後のテキストで比較
            command = ChangeItemCommand(self.table, row, col, self.old_text, new_text_for_command)
            if self.undo_stack:
                self.undo_stack.push(command) # push 時に redo が一度呼ばれる
            else:
                # undo_stack がない場合、UI は既に上で更新済み。
                # command.redo() を呼ぶと、コマンド側でもUI更新が行われる場合、二重更新になるか、
                # コマンド側がフォーマット済みテキストを持っているので問題ない。
                command.redo() # データモデルのみ更新するか、UIも更新するかはコマンドの実装による

        # 金額列の計算と表示更新 (数量または単価が妥当な場合)
        if is_valid_input and (col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE):
            quantity_item = self.table.item(row, self.COL_QUANTITY)
            unit_price_item = self.table.item(row, self.COL_UNIT_PRICE)
            
            # 金額計算には、フォーマットされた表示テキストから再度パースする
            quantity_val = parse_number(quantity_item.text() if quantity_item else "0")
            unit_price_val = parse_number(unit_price_item.text() if unit_price_item else "0")

            try:
                # 計算はDecimalで行う
                amount = Decimal(str(quantity_val)) * Decimal(str(unit_price_val))
            except InvalidOperation:
                amount = Decimal('0')

            amount_item = self.table.item(row, self.COL_AMOUNT)
            if amount_item is None:
                amount_item = QTableWidgetItem()
                self.table.setItem(row, self.COL_AMOUNT, amount_item)
                amount_item.setFlags(amount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.table.blockSignals(True)
            amount_item.setText(format_currency(amount)) # utils.format_currency を使用
            self.table.blockSignals(False)
        
        # 編集状態をリセット
        self.is_editing = False
        self.current_editing_cell = None
        self.old_text = None # 次の編集のためにクリア
        
        self._update_detail_totals() # 全体の合計を更新


    def _update_detail_totals(self):
        subtotal = Decimal('0.0')
        for row_idx in range(self.table.rowCount()):
            amount_item = self.table.item(row_idx, self.COL_AMOUNT)
            if amount_item and amount_item.text():
                try:
                    # parse_number は float を返すので、Decimal に変換
                    parsed_val = parse_number(amount_item.text())
                    subtotal += Decimal(str(parsed_val)) # floatからstr経由でDecimalへ
                except (ValueError, TypeError, InvalidOperation): # parse_numberが0.0を返したり、Decimal変換失敗
                    pass # 加算しない

        tax_rate_decimal = Decimal(str(TAX_RATE)) # constantsから
        
        subtotal_rounded = subtotal.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
        tax_calculated = subtotal * tax_rate_decimal # 税は丸める前の税抜合計から計算
        tax_rounded = tax_calculated.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
        # total_rounded = subtotal_rounded + tax_rounded # 請求書ベースの合計 (丸めた税抜 + 丸めた税)
        total_exact = subtotal + tax_calculated # より正確な合計
        total_final_display = total_exact.quantize(Decimal('0'), rounding=ROUND_HALF_UP) # 表示用合計


        self.update_header(
            self.project_name_value.text(),
            self.client_name_value.text(),
            self.period_value.text(),
            format_currency(total_final_display),
            format_currency(subtotal_rounded),
            format_currency(tax_rounded)
        )

    @Slot()
    def add_row(self):
        # (変更なしのため省略 - 前回のコードを参照)
        current_row = self.table.currentRow(); insert_pos = self.table.rowCount() if current_row < 0 else current_row + 1
        command = InsertRowCommand(self.table, insert_pos, self._initialize_row, description="行追加")
        if self.undo_stack: self.undo_stack.push(command)
        else: command.redo()
        self._update_detail_totals()


    def _get_row_data(self, row: int) -> List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict[str, Any]]]]]:
        # (変更なしのため省略 - 前回のコードを参照)
        data = []
        for col in range(self.table.columnCount()):
            widget = self.table.cellWidget(row, col); item = self.table.item(row, col)
            if widget and isinstance(widget, QComboBox): data.append((type(widget), {'currentText': widget.currentText()}))
            elif item: data.append(item.clone())
            else: data.append(None)
        return data


    @Slot()
    def remove_row(self):
        # (変更なしのため省略 - 前回のコードを参照)
        selected_indexes = self.table.selectedIndexes();
        if not selected_indexes: QMessageBox.warning(self, "行削除", "削除する行が選択されていません。"); return
        selected_rows_asc = sorted(list(set(index.row() for index in selected_indexes if index.row() >= 0)))
        if not selected_rows_asc: return
        rows_data_to_save = {row_idx: self._get_row_data(row_idx) for row_idx in selected_rows_asc}
        command = RemoveMultipleRowsCommand(self.table, selected_rows_asc, rows_data_to_save)
        if self.undo_stack: self.undo_stack.push(command)
        else: command.redo()
        self._update_detail_totals()


    @Slot()
    def duplicate_row(self):
        # (変更なしのため省略 - 前回のコードを参照)
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "行複写", "複写する行が選択されていません。"); return
        selected_rows = sorted(list(set(index.row() for index in selected_indexes if index.row() >= 0)))
        if not selected_rows: QMessageBox.warning(self, "行複写", "複写する行が選択されていません。"); return
        rows_data_to_duplicate = {row_idx: self._get_row_data(row_idx) for row_idx in selected_rows}
        if rows_data_to_duplicate:
            command = DuplicateMultipleRowsCommand(self.table, rows_data_to_duplicate)
            if self.undo_stack: self.undo_stack.push(command)
            else: command.redo()
            self._update_detail_totals()
        else: QMessageBox.information(self, "行複写", "複写対象のデータがありませんでした。")


    def _initialize_row(self, row):
        self.table.blockSignals(True)
        # 金額列の初期化
        amount_item = QTableWidgetItem(format_currency(0)) # format_currency を使用
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, self.COL_AMOUNT, amount_item)
        
        # 単位列の初期化
        self.table.setCellWidget(row, self.COL_UNIT, self._create_unit_combobox())

        # その他の列の初期化
        for col in range(self.NUM_COLS):
            if col not in [self.COL_AMOUNT, self.COL_UNIT]: # 金額と単位以外
                if self.table.item(row, col) is None:
                    self.table.setItem(row, col, QTableWidgetItem(""))
                
                current_item = self.table.item(row, col)
                if col == self.COL_QUANTITY:
                    current_item.setText(format_quantity(0.0)) # utils.format_quantity
                    current_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                elif col == self.COL_UNIT_PRICE:
                    current_item.setText(format_currency(0)) # utils.format_currency
                    current_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                # COL_NAME, COL_SPECIFICATION, COL_SUMMARY は左寄せの空文字列でOK
        self.table.blockSignals(False)

    def get_current_subtotal(self) -> str:
        # (変更なしのため省略 - 前回のコードを参照)
        return self.subtotal_value.text() if hasattr(self, 'subtotal_value') else ""

    def get_current_tax(self) -> str:
        # (変更なしのため省略 - 前回のコードを参照)
        return self.tax_value.text() if hasattr(self, 'tax_value') else ""

    def get_current_total(self) -> str:
        # (変更なしのため省略 - 前回のコードを参照)
        return self.total_value.text() if hasattr(self, 'total_value') else ""
    
    def _get_current_header_data_for_save(self) -> Dict[str, Any]:
        # (変更なしのため省略 - 前回のコードを参照)
        return {
            "project_name": self.project_name_value.text(),
            "client_name": self.client_name_value.text(),
            "period_text": self.period_value.text(),
            "subtotal_amount": parse_number(self.subtotal_value.text()), # floatが返る
            "tax_amount": parse_number(self.tax_value.text()),       # floatが返る
            "total_amount": parse_number(self.total_value.text()),     # floatが返る
        }

    def _get_current_detail_data_for_save(self) -> List[Dict[str, Any]]:
        details = []
        for row in range(self.table.rowCount()):
            unit_widget = self.table.cellWidget(row, self.COL_UNIT)
            unit_text = unit_widget.currentText() if isinstance(unit_widget, QComboBox) else ""
            
            name_item = self.table.item(row, self.COL_NAME)
            name_text_val = name_item.text() if name_item else ""

            spec_item = self.table.item(row, self.COL_SPECIFICATION) # 仕様列
            spec_text_val = spec_item.text() if spec_item else ""

            quantity_item = self.table.item(row, self.COL_QUANTITY)
            quantity_val = parse_number(quantity_item.text() if quantity_item else "0")

            unit_price_item = self.table.item(row, self.COL_UNIT_PRICE)
            unit_price_val = parse_number(unit_price_item.text() if unit_price_item else "0")

            amount_item = self.table.item(row, self.COL_AMOUNT)
            amount_val = parse_number(amount_item.text() if amount_item else "0")

            summary_item = self.table.item(row, self.COL_SUMMARY) # 摘要列
            summary_text_val = summary_item.text() if summary_item else ""
            
            details.append({
                "row_order": row,
                "name_text": name_text_val,
                "specification_text": spec_text_val, # 追加
                "quantity": quantity_val,            # float
                "unit_text": unit_text,
                "unit_price": unit_price_val,        # float
                "amount": amount_val,                # float
                "summary_text": summary_text_val,
            })
        return details

    def _execute_save_to_db(self) -> bool:
        header_data = self._get_current_header_data_for_save()
        detail_data_list = self._get_current_detail_data_for_save()

        if not header_data.get("project_name"):
            QMessageBox.warning(self, "保存エラー", "工事名が入力されていません。")
            return False

        conn = None
        try:
            conn = sqlite3.connect(self.db_file_path)
            cursor = conn.cursor()

            now_iso = datetime.now().isoformat(sep=' ', timespec='seconds')
            estimate_id_to_use = None

            if self.current_estimate_id is not None:
                cursor.execute("""
                    UPDATE estimates SET
                        project_name = ?, client_name = ?, period_text = ?,
                        subtotal_amount = ?, tax_amount = ?, total_amount = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (header_data["project_name"], header_data["client_name"], header_data["period_text"],
                        header_data["subtotal_amount"], header_data["tax_amount"], header_data["total_amount"],
                        now_iso, self.current_estimate_id))
                estimate_id_to_use = self.current_estimate_id
                cursor.execute("DELETE FROM details WHERE estimate_id = ?", (estimate_id_to_use,))
            else:
                cursor.execute("""
                    INSERT INTO estimates (base_estimate_id, revision_number, project_name, client_name, period_text,
                                        subtotal_amount, tax_amount, total_amount, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (None, 0, header_data["project_name"], header_data["client_name"], header_data["period_text"],
                        header_data["subtotal_amount"], header_data["tax_amount"], header_data["total_amount"],
                        now_iso, now_iso))
                estimate_id_to_use = cursor.lastrowid
                self.current_estimate_id = estimate_id_to_use

            if detail_data_list:
                details_to_insert = []
                for detail in detail_data_list:
                    details_to_insert.append((
                        estimate_id_to_use,
                        detail["row_order"],
                        detail["name_text"],
                        detail["specification_text"], # 追加
                        detail["quantity"],
                        detail["unit_text"],
                        detail["unit_price"],
                        detail["amount"],
                        detail["summary_text"]
                    ))
                
                cursor.executemany("""
                    INSERT INTO details (estimate_id, row_order, name_text, specification_text,
                                        quantity, unit_text, unit_price, amount, summary_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, details_to_insert)

            conn.commit()
            self.status_message_requested.emit(f"ファイル '{os.path.basename(self.db_file_path)}' に保存しました。")
            return True

        except sqlite3.Error as e:
            QMessageBox.critical(self, "データベースエラー", f"データの保存中にエラーが発生しました:\n{e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    @Slot()
    def handle_save_file(self):
        # (変更なしのため省略 - 前回のコードを参照)
        if not self._get_current_header_data_for_save().get("project_name"):
            QMessageBox.warning(self, "保存エラー", "工事名が入力されていません。"); return
        if self._execute_save_to_db(): pass

    @Slot()
    def handle_save_as_file(self):
        # (変更なしのため省略 - 前回のコードを参照)
        if not self._get_current_header_data_for_save().get("project_name"):
            QMessageBox.warning(self, "保存エラー", "工事名が入力されていません。"); return
        original_estimate_id = self.current_estimate_id; original_db_path = self.db_file_path
        options: QFileDialog.Options = QFileDialog.Options(0)
        new_db_path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", original_db_path, 
                                                   "SQLite Database Files (*.db);;All Files (*)", options=options)
        if new_db_path:
            self.current_estimate_id = None; self.db_file_path = new_db_path
            if self._execute_save_to_db():
                QMessageBox.information(self, "名前を付けて保存", f"新しい案件として '{os.path.basename(self.db_file_path)}' に保存しました。")
            else:
                self.current_estimate_id = original_estimate_id; self.db_file_path = original_db_path
                QMessageBox.warning(self, "保存失敗", "名前を付けて保存に失敗しました。")
        else:
            self.current_estimate_id = original_estimate_id # キャンセル時