# detail_page_widget.py (パレットで背景色を修正)
import operator
import os
import csv
import pickle # pickle をインポート
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


from PySide6.QtWidgets import (
    QMessageBox, QComboBox, QCompleter, QLineEdit,
    QWidget, QTableWidget, QVBoxLayout, QTableWidgetItem, QHeaderView, QApplication,
    QLabel, QPushButton, QGridLayout, QFrame, QHBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QEvent, QModelIndex, QItemSelectionModel, QMimeData, QPoint
from PySide6.QtGui import (
    QPalette, QColor, QDropEvent, QDragEnterEvent, QDragMoveEvent,
    QContextMenuEvent, QAction, QKeySequence, QBrush, QDrag, QMouseEvent
)

from typing import List, Optional, Callable, Union, Type, Dict, Any, Tuple

from constants import WIDGET_BASE_STYLE, COLOR_LIGHT_GRAY, COLOR_WHITE, COLOR_ERROR_BG
from commands import (
    AddRowCommand, InsertRowCommand, RemoveRowCommand, ChangeItemCommand,
    DuplicateRowCommand, RemoveMultipleRowsCommand, DuplicateMultipleRowsCommand,
    MoveMultipleRowsCommand
)

from utils import format_currency, format_quantity, parse_number

# --------------------------------------------------------------------------
# ドラッグ＆ドロップ可能なテーブルウィジェット
# --------------------------------------------------------------------------
class DraggableTableWidget(QTableWidget):
    """行のドラッグ＆ドロップによる並べ替えが可能な QTableWidget"""

    row_moved = Signal(int, int)
    context_action_requested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack = None
        self._drag_start_position: Optional[QPoint] = None # ドラッグ開始位置を保持
        self._configure_drag_drop()

    def _configure_drag_drop(self):
        """ドラッグ＆ドロップ関連の設定"""
        self.setDragEnabled(True) # テーブルからのドラッグを有効化
        self.setAcceptDrops(True) # テーブルへのドロップを有効化
        self.viewport().setAcceptDrops(True) # ビューポートもドロップを受け付ける
        self.setDragDropOverwriteMode(False) # ドロップ時に上書きしない
        self.setDropIndicatorShown(True) # ドロップ先のインジケータ表示
        self.setDragDropMode(QAbstractItemView.DragDrop) # カスタムMIMEデータのためDragDrop
        self.setSelectionMode(QAbstractItemView.ExtendedSelection) # 複数行選択を可能に
        self.setSelectionBehavior(QAbstractItemView.SelectRows) # 行単位で選択
    def _get_row_data_for_drag(self, row: int) -> List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict[str, Any]]]]]:
        """ドラッグ操作のために指定された行のデータを取得する"""
        data = []
        for col in range(self.columnCount()):
            widget = self.cellWidget(row, col)
            item = self.item(row, col)
            if widget and isinstance(widget, QComboBox):
                data.append((type(widget), {'currentText': widget.currentText()}))
            elif item:
                # QTableWidgetItem のクローンではなく、テキストなどの情報を保存
                try:
                    # item.flags() は QFlags オブジェクトなので .value で整数値を取得
                    print(f"DEBUG _get_row_data_for_drag: row={row}, col={col}, item.text()='{item.text()}', type={type(item.text())}")
                    flags_val = item.flags().value
                    # item.textAlignment() は既に int のようなので、そのまま使用
                    alignment_val = item.textAlignment()
                    data.append({'text': item.text(), 'flags': flags_val, 'textAlignment': alignment_val})
                except TypeError as e:
                    print(f"--- DIAGNOSTIC INFO ---")
                    print(f"Error converting flags/alignment for item text: '{item.text()}' (row {row}, col {col})")
                    print(f"  item.flags() -> Type: {type(item.flags())}, Value: {item.flags()}")
                    print(f"  item.textAlignment() -> Type: {type(item.textAlignment())}, Value: {item.textAlignment()}")
                    print(f"  Error message: {e}")
                    print(f"--- END DIAGNOSTIC INFO ---")
                    data.append({'text': item.text(), 'flags': None, 'textAlignment': None}) # エラー時は None を格納
            else:
                data.append(None)
        return data

    def startDrag(self, supportedActions: Qt.DropActions):
        """ドラッグ操作を開始する"""
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return

        selected_rows_indices = sorted(list(set(idx.row() for idx in selected_indexes)))
        if not selected_rows_indices:
            return

        # print(f"DEBUG: DraggableTableWidget.startDrag for rows: {selected_rows_indices}") # デバッグ用

        drag_data_payload = [self._get_row_data_for_drag(row_idx) for row_idx in selected_rows_indices]

        mime_data = QMimeData()
        encoded_data = pickle.dumps((selected_rows_indices, drag_data_payload))
        mime_data.setData("application/x-estimate-app-rows", encoded_data)

        drag = QDrag(self) # ドラッグのソースは自分自身 (DraggableTableWidget)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction) # 今回は移動のみを想定

    def mousePressEvent(self, event: QMouseEvent):
        """マウスボタンが押されたときのイベント"""
        # print(f"DEBUG: DraggableTableWidget.mousePressEvent - button: {event.button()}") # デバッグ用
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.pos()
            # print(f"DEBUG: DraggableTableWidget.mousePressEvent - _drag_start_position set to: {self._drag_start_position}") # デバッグ用
        super().mousePressEvent(event) # スーパークラスの処理も呼ぶ (選択などに必要)

    def mouseMoveEvent(self, event: QMouseEvent):
        """マウスが移動したときのイベント (ボタンが押された状態で)"""
        # print(f"DEBUG: DraggableTableWidget.mouseMoveEvent - buttons: {event.buttons()}") # デバッグ用
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_position is None: # mousePressEventが呼ばれていないか、左ボタンでなかった場合
            super().mouseMoveEvent(event)
            return

        distance = (event.pos() - self._drag_start_position).manhattanLength()
        if distance >= QApplication.startDragDistance():
            # print(f"DEBUG: DraggableTableWidget.mouseMoveEvent - Drag distance exceeded ({distance}), attempting to start drag.") # デバッグ用
            # startDrag を呼び出すのは QAbstractItemView の mouseMoveEvent の役割なので、ここでは super を呼ぶ
            pass
        super().mouseMoveEvent(event) # スーパークラスの処理を呼ぶ (startDragの呼び出しや選択処理)        

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-estimate-app-rows"):
            encoded_data = event.mimeData().data("application/x-estimate-app-rows")
            try:
                source_indices, moved_rows_data = pickle.loads(encoded_data)
                print(f"DEBUG DraggableTableWidget.dropEvent: Decoded moved_rows_data[0][0] = {moved_rows_data[0][0] if moved_rows_data and moved_rows_data[0] else 'N/A'}") # 最初の行の最初のセルのデータを確認
                print(f"DEBUG DraggableTableWidget.dropEvent: Type of moved_rows_data[0][0]['text'] = {type(moved_rows_data[0][0]['text']) if moved_rows_data and moved_rows_data[0] and isinstance(moved_rows_data[0][0], dict) and 'text' in moved_rows_data[0][0] else 'N/A'}")

            except Exception as e:
                print(f"Error decoding drag data in DraggableTableWidget: {e}")
                event.ignore()
                return

            drop_pos_in_table = event.position().toPoint()
            target_index = self.indexAt(drop_pos_in_table)
            dest_row_before_removal = target_index.row()

            if dest_row_before_removal == -1:
                dest_row_before_removal = self.rowCount()

            if not source_indices:
                event.ignore()
                return

            # ここでは event.source() のチェックは必須ではない (MIMEタイプで判断しているため)
            # if event.source() == self: # 同じテーブル内での移動
            event.setDropAction(Qt.MoveAction)
            event.accept()

            command = MoveMultipleRowsCommand(self, source_indices, moved_rows_data, dest_row_before_removal)
            if self.undo_stack and not command.is_noop:
                self.undo_stack.push(command)
            else:
                pass # No-op or no undo_stack
            # else:
            #     event.ignore() # 異なるソースからのドロップは無視
        else:
            event.ignore()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_index = self.currentIndex()
            if not current_index.isValid():
                super().keyPressEvent(event)
                return

            row, col = current_index.row(), current_index.column()
            next_row, next_col = row, col

            if modifiers == Qt.ShiftModifier:
                if col > 0:
                    next_col -= 1
                elif row > 0:
                    next_row -= 1
                    next_col = self.columnCount() - 1
                else:
                    super().keyPressEvent(event)
                    return
            else:
                if col < self.columnCount() - 1:
                    next_col += 1
                elif row < self.rowCount() - 1:
                    next_row += 1
                    next_col = 0
                else:
                    super().keyPressEvent(event)
                    return

            next_index = self.model().index(next_row, next_col)
            if next_index.isValid():
                self.setCurrentIndex(next_index)
                self.edit(next_index)
            event.accept()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet("color: black;")
        index = self.indexAt(event.pos())
        clicked_row = index.row() if index.isValid() else -1

        add_action = QAction("行追加", self)
        remove_action = QAction("行削除", self)
        duplicate_action = QAction("複写", self)

        add_action.triggered.connect(lambda: self.context_action_requested.emit('add', clicked_row))
        remove_action.triggered.connect(lambda: self.context_action_requested.emit('remove', clicked_row))
        duplicate_action.triggered.connect(lambda: self.context_action_requested.emit('duplicate', clicked_row))

        if clicked_row >= 0:
            remove_action.setEnabled(True)
            duplicate_action.setEnabled(True)
        else:
            remove_action.setEnabled(False)
            duplicate_action.setEnabled(False)

        menu.addAction(add_action)
        menu.addAction(remove_action)
        menu.addAction(duplicate_action)
        menu.exec(event.globalPos())

# --------------------------------------------------------------------------
# 明細ページウィジェット
# --------------------------------------------------------------------------
class DetailPageWidget(QWidget):
    cover_requested = Signal()
    status_message_requested = Signal(str)
    screen_flash_requested = Signal()

    COL_ITEM = 0
    COL_QUANTITY = 1
    COL_UNIT = 2
    COL_UNIT_PRICE = 3
    COL_AMOUNT = 4
    COL_REMARKS = 5
    NUM_COLS = 6

    HEADERS = ["項目", "数量", "単位", "単価", "金額", "備考"]
    INITIAL_WIDTHS = [300, 80, 60, 100, 120, 200]

    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.is_editing = False
        self.current_editing_cell: Optional[Tuple[int, int]] = None
        self.old_text: Optional[str] = None
        self.last_error_info = None
        self.unit_list = self._load_units()

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor('white'))
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
            # self.table.row_moved.connect(self._update_detail_totals) # コマンド経由で更新される
            self.table.context_action_requested.connect(self._handle_context_action)
        else:
            print("警告: self.table が未定義のためシグナルを接続できません。")
        self.setAcceptDrops(True) # DetailPageWidget自体もドロップを受け付ける (実際はテーブルが処理)


    def _load_units(self) -> list[str]:
        units_file = "units.txt"
        default_units = ["式", "個", "m", "m2", "本", "セット"]
        try:
            with open(units_file, "r", encoding="utf-8") as f:
                units = [line.strip() for line in f if line.strip()]
            return units if units else default_units
        except FileNotFoundError:
            print(f"警告: {units_file} が見つかりません。デフォルトの単位リストを使用します。")
            return default_units
        except Exception as e:
            print(f"エラー: {units_file} の読み込み中にエラーが発生しました: {e}")
            return default_units


    def _setup_ui(self):
        header_frame = self._create_header_widget()
        self.table = DraggableTableWidget()
        self.table.undo_stack = self.undo_stack
        self._configure_table()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        main_layout.addWidget(header_frame)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def _configure_table(self):
        if not hasattr(self, 'table'):
             print("エラー: self.table が _setup_ui で作成されていません。")
             return

        self.table.setColumnCount(self.NUM_COLS)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        header = self.table.horizontalHeader()
        for i, width in enumerate(self.INITIAL_WIDTHS):
            header.resizeSection(i, width)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setVisible(True)
        self.table.verticalHeader().setVisible(True)

        test_data = [
            {"item": "テスト項目1", "quantity": 10.0, "unit": "式", "unit_price": 1000, "remarks": "テスト備考1"},
            {"item": "テスト項目2", "quantity": 5.0, "unit": "個", "unit_price": 500, "remarks": ""},
            {"item": "テスト項目3", "quantity": 1.0, "unit": "m2", "unit_price": 15000, "remarks": "長い備考テスト"},
            {"item": "テスト項目4", "quantity": 20.5, "unit": "本", "unit_price": 800, "remarks": ""},
            {"item": "テスト項目5", "quantity": 1.0, "unit": "セット", "unit_price": 50000, "remarks": "セット品"},
        ]

        self.table.setRowCount(len(test_data))
        self.table.blockSignals(True)
        for row, data in enumerate(test_data):
            item_item = QTableWidgetItem(data["item"])
            quantity_item = QTableWidgetItem(f"{data['quantity']:.1f}")
            unit_price_item = QTableWidgetItem(f"{data['unit_price']:,.0f}")
            remarks_item = QTableWidgetItem(data["remarks"])

            quantity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            unit_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            amount = data["quantity"] * data["unit_price"]
            amount_item = QTableWidgetItem(f"{amount:,.0f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, self.COL_ITEM, item_item)
            self.table.setItem(row, self.COL_QUANTITY, quantity_item)
            unit_combo = self._create_unit_combobox()
            unit_combo.setCurrentText(data.get("unit", ""))
            self.table.setCellWidget(row, self.COL_UNIT, unit_combo)
            self.table.setItem(row, self.COL_UNIT_PRICE, unit_price_item)
            self.table.setItem(row, self.COL_AMOUNT, amount_item)
            self.table.setItem(row, self.COL_REMARKS, remarks_item)
        self.table.blockSignals(False)
        self._update_detail_totals()

    def _create_header_widget(self) -> QWidget:
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
        for label in [self.project_name_value, self.client_name_value, self.period_value,
                      self.total_value, self.subtotal_value, self.tax_value]:
            label.setStyleSheet(value_style)

        main_h_layout = QHBoxLayout()
        main_h_layout.setContentsMargins(0, 0, 0, 5)
        main_h_layout.setSpacing(20)

        left_v_layout = QVBoxLayout()
        left_v_layout.setSpacing(5)
        for label, value in [(self.project_name_label, self.project_name_value),
                             (self.client_name_label, self.client_name_value),
                             (self.period_label, self.period_value)]:
            h_layout = QHBoxLayout()
            h_layout.addWidget(label)
            h_layout.addWidget(value, 1)
            left_v_layout.addLayout(h_layout)

        right_grid_layout = QGridLayout()
        right_grid_layout.setSpacing(5)
        right_grid_layout.addWidget(self.subtotal_label, 0, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.subtotal_value, 0, 1, Qt.AlignRight | Qt.AlignVCenter)
        right_grid_layout.addWidget(self.tax_label, 1, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.tax_value, 1, 1, Qt.AlignRight | Qt.AlignVCenter)
        right_grid_layout.addWidget(self.total_label, 2, 0, Qt.AlignRight)
        right_grid_layout.addWidget(self.total_value, 2, 1, Qt.AlignRight | Qt.AlignVCenter)

        main_h_layout.addLayout(left_v_layout, 1)
        main_h_layout.addLayout(right_grid_layout)

        final_layout = QVBoxLayout(header_widget)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addLayout(main_h_layout)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        final_layout.addWidget(line)
        return header_widget

    def update_header(self, project_name, client_name, period_text, total, subtotal, tax):
        self.project_name_value.setText(project_name if project_name else "---")
        self.client_name_value.setText(client_name if client_name else "---")
        self.period_value.setText(period_text if period_text else "---")
        self.total_value.setText(total if total else "---")
        self.subtotal_value.setText(subtotal if subtotal else "---")
        self.tax_value.setText(tax if tax else "---")

    def _create_unit_combobox(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems(self.unit_list)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        completer = QCompleter(self.unit_list)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)
        combo.view().setStyleSheet("color: black; background-color: white;")
        combo.setStyleSheet("color: black;")
        combo.currentTextChanged.connect(self._on_unit_changed)
        # QComboBoxの編集開始を捉えるために、focusInEventをオーバーライドするか、
        # lineEdit() の focusGained シグナルを使うなどの工夫が必要になる場合がある
        # ここでは、cellPressed で QComboBox の場合も old_text を記録するようにする
        return combo

    @Slot(int, int)
    def _on_cell_pressed(self, row, col):
        self.current_editing_cell = (row, col)
        self.is_editing = True
        if col == self.COL_UNIT:
            widget = self.table.cellWidget(row, col)
            if isinstance(widget, QComboBox):
                self.old_text = widget.currentText()
        else:
            item = self.table.item(row, col)
            if item and (item.flags() & Qt.ItemIsEditable):
                self.old_text = item.text()
            else: # 編集不可セルやアイテムがない場合は編集状態にしない
                self.is_editing = False
                self.current_editing_cell = None


    @Slot(str)
    def _on_unit_changed(self, new_text: str):
        sender_combo = self.sender()
        if not isinstance(sender_combo, QComboBox) or not self.is_editing:
            return

        # QComboBoxの位置から行を取得
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, self.COL_UNIT) == sender_combo:
                row = r
                break
        else: # ループで見つからなかった場合
            return

        if self.current_editing_cell != (row, self.COL_UNIT): return

        if hasattr(self, 'old_text') and self.old_text is not None and self.old_text != new_text:
            command = ChangeItemCommand(self.table, row, self.COL_UNIT, self.old_text, new_text)
            self.undo_stack.push(command)
        # self.is_editing = False # ChangeItemCommand後にis_editingをFalseにするのは_on_cell_changedで行う

    @Slot(str, int)
    def _handle_context_action(self, action_name: str, row: int):
        if action_name == 'add':
            if row >= 0: self.table.selectRow(row)
            else: self.table.clearSelection()
            self.add_row()
        elif action_name == 'remove':
            if row >= 0:
                self.table.selectRow(row)
                self.remove_row()
        elif action_name == 'duplicate':
            if row >= 0:
                self.table.selectRow(row)
                self.duplicate_row()

    @Slot(int, int)
    def _on_cell_changed(self, row, col):
        if not self.is_editing or self.current_editing_cell != (row, col):
            return
        if col == self.COL_UNIT: # 単位列は _on_unit_changed で処理
            self.is_editing = False # 単位列の編集が終わったことを示す
            return

        item = self.table.item(row, col)
        if not item: return
        new_text = item.text()
        is_valid_input = True

        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            try:
                cleaned_text = new_text.replace(",", "").replace("￥", "").strip()
                value = float(cleaned_text or 0.0)
                default_bg_color = self.table.palette().base().color()
                default_fg_color = QColor("black")
                item.setBackground(default_bg_color)
                item.setForeground(QBrush(default_fg_color))
                if self.last_error_info and self.last_error_info[:2] == (row, col):
                    self.last_error_info = None
                    self.status_message_requested.emit("")
            except ValueError:
                error_bg_color = QColor(COLOR_ERROR_BG)
                error_fg_color = QColor("red")
                item.setBackground(error_bg_color)
                item.setForeground(QBrush(error_fg_color))
                error_message = f"行 {row + 1}, 列 '{self.HEADERS[col]}' の入力が無効です: '{new_text}'"
                self.status_message_requested.emit(error_message)
                self.last_error_info = (row, col, error_message)
                self.screen_flash_requested.emit()
                is_valid_input = False

        if col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if hasattr(self, 'old_text') and self.old_text is not None and self.old_text != new_text:
            command = ChangeItemCommand(self.table, row, col, self.old_text, new_text)
            self.undo_stack.push(command)

        if is_valid_input and (col == self.COL_QUANTITY or col == self.COL_UNIT_PRICE):
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
        self.is_editing = False

    def _update_detail_totals(self):
        from constants import TAX_RATE
        subtotal = 0.0
        for row_idx in range(self.table.rowCount()):
            amount_item = self.table.item(row_idx, self.COL_AMOUNT)
            if amount_item and amount_item.text():
                try:
                    amount_val = float(amount_item.text().replace(",", "").replace("￥", "").strip())
                    subtotal += amount_val
                except ValueError:
                    pass # 無効な値は無視

        tax = int(subtotal * TAX_RATE)
        total = int(subtotal) + tax
        self.update_header(
            self.project_name_value.text(),
            self.client_name_value.text(),
            self.period_value.text(),
            f"￥{total:,}",
            f"￥{int(subtotal):,}",
            f"￥{tax:,}"
        )

    @Slot()
    def add_row(self):
        current_row = self.table.currentRow()
        insert_pos = self.table.rowCount() if current_row < 0 else current_row + 1
        command = InsertRowCommand(self.table, insert_pos, self._initialize_row, description="行追加")
        self.undo_stack.push(command)

    def _get_row_data(self, row: int) -> List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict[str, Any]]]]]:
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

    @Slot()
    def remove_row(self):
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "行削除", "削除する行が選択されていません。")
            return

        selected_rows = sorted(list(set(index.row() for index in selected_indexes if index.row() >= 0)))
        if not selected_rows: return

        rows_data_to_save = {}
        for row_idx in selected_rows:
            rows_data_to_save[row_idx] = self._get_row_data(row_idx)

        command = RemoveMultipleRowsCommand(self.table, selected_rows, rows_data_to_save)
        self.undo_stack.push(command)

    @Slot()
    def duplicate_row(self):
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "行複写", "複写する行が選択されていません。")
            return

        selected_rows = sorted(list(set(index.row() for index in selected_indexes if index.row() >= 0)))
        if not selected_rows:
            QMessageBox.warning(self, "行複写", "複写する行が選択されていません。")
            return

        rows_data_to_duplicate = {}
        for row_idx in selected_rows:
            rows_data_to_duplicate[row_idx] = self._get_row_data(row_idx)

        if rows_data_to_duplicate:
            command = DuplicateMultipleRowsCommand(self.table, rows_data_to_duplicate)
            self.undo_stack.push(command)
        else:
            QMessageBox.information(self, "行複写", "複写対象のデータがありませんでした。")

    def _initialize_row(self, row):
        self.table.blockSignals(True)
        amount_item = QTableWidgetItem("0")
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, self.COL_AMOUNT, amount_item)
        self.table.setCellWidget(row, self.COL_UNIT, self._create_unit_combobox())

        for col in range(self.NUM_COLS):
            if col != self.COL_AMOUNT and col != self.COL_UNIT:
                if self.table.item(row, col) is None:
                    self.table.setItem(row, col, QTableWidgetItem(""))
        self.table.blockSignals(False)

    def get_current_subtotal(self) -> str:
        return self.subtotal_value.text() if hasattr(self, 'subtotal_value') else ""

    def get_current_tax(self) -> str:
        return self.tax_value.text() if hasattr(self, 'tax_value') else ""

    def get_current_total(self) -> str:
        return self.total_value.text() if hasattr(self, 'total_value') else ""
