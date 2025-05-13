# commands.py
import os
import shutil
import pickle # pickle をインポート
from PySide6.QtGui import QUndoCommand # QUndoCommand のみ QtGui から
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QApplication, QComboBox, QHeaderView # QComboBox, QHeaderView をインポート
from PySide6.QtCore import Qt # Qt をインポート
from typing import List, Optional, Callable, Tuple, Type, Dict, Any, Union
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from detail_page_widget import DetailPageWidget # 循環参照を避けるための型チェック用インポート

class AddRowCommand(QUndoCommand):
    """行を追加するコマンド"""
    def __init__(self, table: QTableWidget, initialize_row_func: Callable[[int], None], description: str = "行追加"):
        super().__init__(description)
        self.table = table
        self.row_index = table.rowCount()
        self.initialize_row_func = initialize_row_func

    def redo(self):
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        if self.initialize_row_func:
            self.initialize_row_func(self.row_index)
        self.table.blockSignals(False)

    def undo(self):
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)

class InsertRowCommand(QUndoCommand):
    """指定した位置に行を挿入するコマンド"""
    def __init__(self, table: QTableWidget, row_index: int, initialize_row_func: Callable[[int], None], description: str = "行挿入"):
        super().__init__(description)
        self.table = table
        self.row_index = row_index
        self.initialize_row_func = initialize_row_func

    def redo(self):
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        if self.initialize_row_func:
            self.initialize_row_func(self.row_index)
        self.table.blockSignals(False)

    def undo(self):
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)

class RemoveRowCommand(QUndoCommand):
    """行を削除するコマンド (単一行用、現在はRemoveMultipleRowsCommandに統合されることが多い)"""
    def __init__(self, table: QTableWidget, row_index: int, row_data: List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict]]]], description: str = "行削除"):
        super().__init__(description)
        self.table = table
        self.row_index = row_index
        self.row_data_saved = row_data

    def redo(self):
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)

    def undo(self):
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        for col, saved_data in enumerate(self.row_data_saved):
            if isinstance(saved_data, QTableWidgetItem):
                self.table.setItem(self.row_index, col, saved_data.clone())
            elif isinstance(saved_data, tuple) and len(saved_data) == 2 and isinstance(saved_data[0], type) and issubclass(saved_data[0], QComboBox):
                widget_class, properties = saved_data
                parent_widget = self.table.parent()
                if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                    combo = parent_widget._create_unit_combobox()
                    combo.setCurrentText(properties.get('currentText', ''))
                    self.table.setCellWidget(self.row_index, col, combo)
                else:
                    self.table.setItem(self.row_index, col, QTableWidgetItem("復元エラー"))
            elif saved_data is None:
                self.table.setItem(self.row_index, col, QTableWidgetItem(""))
            else:
                self.table.setItem(self.row_index, col, QTableWidgetItem("復元エラー"))
        self.table.blockSignals(False)


class ChangeItemCommand(QUndoCommand):
    """テーブルアイテムの内容を変更するコマンド"""
    CHANGE_ITEM_ID = 1001

    def __init__(self, table: QTableWidget, row: int, col: int, old_text: str, new_text: str, description: str = "セル編集"):
        super().__init__(description)
        self.table = table
        self.row = row
        self.col = col
        self.old_text = old_text
        self.new_text = new_text
        parent_widget = table.parent()
        self.detail_page: Optional['DetailPageWidget'] = parent_widget if hasattr(parent_widget, 'COL_ITEM') else None

    def _format_text(self, text: str) -> str:
        if not self.detail_page: return text
        try:
            if self.col == self.detail_page.COL_UNIT:
                return text
            cleaned_text = text.replace(",", "").replace("￥", "").strip()
            value = float(cleaned_text or 0.0)
            if self.col == self.detail_page.COL_QUANTITY:
                return f"{value:,.1f}"
            elif self.col == self.detail_page.COL_UNIT_PRICE or self.col == self.detail_page.COL_AMOUNT:
                return f"{int(value):,}"
            else:
                return text
        except (ValueError, TypeError, AttributeError):
            return text

    def redo(self):
        is_unit_column = self.detail_page and self.col == self.detail_page.COL_UNIT
        formatted_text = self._format_text(self.new_text)

        if is_unit_column:
            widget = self.table.cellWidget(self.row, self.col)
            if isinstance(widget, QComboBox):
                was_blocked = widget.signalsBlocked()
                widget.blockSignals(True)
                widget.setCurrentText(formatted_text) # QComboBoxにはフォーマット前のテキストが良い場合もある
                widget.blockSignals(was_blocked)
        else:
            item = self.table.item(self.row, self.col)
            if item:
                item.setText(formatted_text)

    def undo(self):
        is_unit_column = self.detail_page and self.col == self.detail_page.COL_UNIT
        formatted_text = self._format_text(self.old_text)

        if is_unit_column:
            widget = self.table.cellWidget(self.row, self.col)
            if isinstance(widget, QComboBox):
                was_blocked = widget.signalsBlocked()
                widget.blockSignals(True)
                widget.setCurrentText(self.old_text) # QComboBoxは元のテキストをそのまま戻す
                widget.blockSignals(was_blocked)
        else:
            item = self.table.item(self.row, self.col)
            if item:
                item.setText(formatted_text)

    def id(self) -> int:
        return self.CHANGE_ITEM_ID + self.row * self.table.columnCount() + self.col

    def mergeWith(self, other: QUndoCommand) -> bool:
        if other.id() == self.id() and isinstance(other, ChangeItemCommand): # 型チェック追加
            self.new_text = other.new_text
            return True
        return False


class DuplicateRowCommand(QUndoCommand):
    """指定した行を複製して、その下に挿入するコマンド (単一行用、現在はDuplicateMultipleRowsCommandに統合されることが多い)"""
    def __init__(self, table: QTableWidget, source_row: int, row_data_to_copy: List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict]]]], description: str = "行複写"):
        super().__init__(description)
        self.table = table
        self.source_row = source_row
        self.insert_row = source_row + 1
        self.row_data_to_copy = row_data_to_copy

    def redo(self):
        self.table.blockSignals(True)
        try:
            self.table.insertRow(self.insert_row)
            for col, data_cell in enumerate(self.row_data_to_copy): # 変数名を data_cell に変更
                if isinstance(data_cell, QTableWidgetItem): # QTableWidgetItem の場合はクローンしてセット
                    self.table.setItem(self.insert_row, col, data_cell.clone())
                elif isinstance(data_cell, dict) and 'text' in data_cell: # 辞書形式の場合
                    text_value = data_cell['text']
                    item = QTableWidgetItem()
                    item.setText(str(text_value)) # 必ず文字列に変換
                    if 'flags' in data_cell and data_cell['flags'] is not None:
                        item.setFlags(Qt.ItemFlags(data_cell['flags']))
                    if 'textAlignment' in data_cell and data_cell['textAlignment'] is not None:
                        item.setTextAlignment(data_cell['textAlignment'])
                    self.table.setItem(self.insert_row, col, item)
                elif isinstance(data_cell, tuple) and len(data_cell) == 2 and isinstance(data_cell[0], type) and issubclass(data_cell[0], QComboBox):
                    widget_class, properties = data_cell
                    parent_widget = self.table.parent()
                    if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                        combo = parent_widget._create_unit_combobox()
                        combo.setCurrentText(properties.get('currentText', ''))
                        self.table.setCellWidget(self.insert_row, col, combo)
                    else:
                        self.table.setItem(self.insert_row, col, QTableWidgetItem("復元エラー"))
                else: # None やその他の場合
                    self.table.setItem(self.insert_row, col, QTableWidgetItem(""))
        except Exception as e:
            print(f"ERROR in DuplicateRowCommand.redo: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.table.blockSignals(False)
        self.table.selectRow(self.insert_row)

    def undo(self):
        self.table.blockSignals(True)
        self.table.removeRow(self.insert_row)
        self.table.blockSignals(False)
        self.table.selectRow(self.source_row)


class MoveMultipleRowsCommand(QUndoCommand):
    def __init__(self,
                 table: QTableWidget,
                 source_rows_indices: List[int],
                 rows_data_to_move: List[List[Any]],
                 dest_row_before_removal: int,
                 description: str = "複数行移動"):
        super().__init__(description)
        self.table = table
        self.source_indices_asc = sorted(list(set(source_rows_indices)))
        self.rows_data_to_move = rows_data_to_move
        self.dest_row_before_removal = dest_row_before_removal
        self.data_of_rows_at_original_source_positions: List[List[Any]] = []
        self.actual_dest_insertion_start_row_in_redo: int = -1
        self.num_rows_moved = len(self.source_indices_asc)
        self.is_noop = self._check_if_noop()

    def _check_if_noop(self) -> bool:
        if not self.source_indices_asc or self.num_rows_moved == 0:
            return True
        num_removed_before_dest = sum(1 for removed_idx in self.source_indices_asc if removed_idx < self.dest_row_before_removal)
        prospective_actual_insert_start_row = self.dest_row_before_removal - num_removed_before_dest
        if prospective_actual_insert_start_row < 0:
             prospective_actual_insert_start_row = 0
        prospective_new_indices = [prospective_actual_insert_start_row + i for i in range(self.num_rows_moved)]
        return prospective_new_indices == self.source_indices_asc

    def _get_row_data_from_table(self, row_index: int) -> List[Any]:
        row_data = []
        for col in range(self.table.columnCount()):
            widget = self.table.cellWidget(row_index, col)
            item = self.table.item(row_index, col)
            if widget and isinstance(widget, QComboBox):
                row_data.append((type(widget), {'currentText': widget.currentText()}))
            elif item:
                # print(f"DEBUG MoveCmd._get_row_data_from_table: row={row_index}, col={col}, item.text()='{item.text()}', type={type(item.text())}")
                row_data.append({'text': item.text(), 'flags': item.flags().value, 'textAlignment': item.textAlignment()})
            else:
                row_data.append(None)
        return row_data

    def _set_row_data_to_table(self, row_index: int, row_data: List[Any]):
        for col, data_cell in enumerate(row_data):
            # print(f"DEBUG _set_row_data_to_table: Processing col {col}, data_cell type: {type(data_cell)}, data_cell: {data_cell}")
            if isinstance(data_cell, dict) and 'text' in data_cell:
                text_value = data_cell['text']
                if not isinstance(text_value, str):
                    # print(f"WARNING _set_row_data_to_table: text_value for item is not str: {type(text_value)}, converting for col {col}.")
                    text_value = str(text_value)
                item = QTableWidgetItem()
                item.setText(text_value)
                # print(f"DEBUG _set_row_data_to_table: For col {col}, called item.setText('{text_value}'). Item now reports text: '{item.text()}'")
                if 'flags' in data_cell and data_cell['flags'] is not None:
                    item.setFlags(Qt.ItemFlags(data_cell['flags']))
                if 'textAlignment' in data_cell and data_cell['textAlignment'] is not None:
                    item.setTextAlignment(data_cell['textAlignment'])
                self.table.setItem(row_index, col, item)
            elif isinstance(data_cell, tuple) and len(data_cell) == 2 and isinstance(data_cell[0], type) and issubclass(data_cell[0], QComboBox):
                widget_class, properties = data_cell
                parent_widget = self.table.parent()
                if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                    combo = parent_widget._create_unit_combobox()
                    combo.setCurrentText(properties.get('currentText', ''))
                    self.table.setCellWidget(row_index, col, combo)
                else:
                    self.table.setItem(row_index, col, QTableWidgetItem("[Widget Placeholder]"))
            elif data_cell is None:
                self.table.setItem(row_index, col, None)
            else: # フォールバックとして文字列に変換
                self.table.setItem(row_index, col, QTableWidgetItem(str(data_cell)))


    def redo(self):
        if self.is_noop:
            self.setText(f"{self.text()} (変更なし)")
            return

        self.table.blockSignals(True)
        self.data_of_rows_at_original_source_positions.clear()
        source_indices_desc = sorted(self.source_indices_asc, reverse=True)
        temp_original_data_map = {}
        for row_idx_to_remove in source_indices_desc:
            temp_original_data_map[row_idx_to_remove] = self._get_row_data_from_table(row_idx_to_remove)
            self.table.removeRow(row_idx_to_remove)
        for row_idx in self.source_indices_asc: # 元の順序で保存
            self.data_of_rows_at_original_source_positions.append(temp_original_data_map[row_idx])

        num_removed_before_dest = sum(1 for removed_idx in self.source_indices_asc if removed_idx < self.dest_row_before_removal)
        self.actual_dest_insertion_start_row_in_redo = self.dest_row_before_removal - num_removed_before_dest

        if self.actual_dest_insertion_start_row_in_redo > self.table.rowCount():
            self.actual_dest_insertion_start_row_in_redo = self.table.rowCount()
        if self.actual_dest_insertion_start_row_in_redo < 0:
            self.actual_dest_insertion_start_row_in_redo = 0

        for i in range(self.num_rows_moved):
            current_insert_row = self.actual_dest_insertion_start_row_in_redo + i
            self.table.insertRow(current_insert_row)
            # print(f"DEBUG MoveCmd.redo: Setting row {current_insert_row} with data: {self.rows_data_to_move[i]}")
            # print(f"DEBUG MoveCmd.redo: Type of text for first cell: {type(self.rows_data_to_move[i][0]['text']) if self.rows_data_to_move[i] and isinstance(self.rows_data_to_move[i][0], dict) and 'text' in self.rows_data_to_move[i][0] else 'N/A'}")
            self._set_row_data_to_table(current_insert_row, self.rows_data_to_move[i])
        self.table.blockSignals(False)

    def undo(self):
        if self.is_noop:
            return
        self.table.blockSignals(True)
        for i in range(self.num_rows_moved - 1, -1, -1): # 挿入された順の逆で削除
            row_to_remove = self.actual_dest_insertion_start_row_in_redo + i
            self.table.removeRow(row_to_remove)

        # 元のインデックスの昇順で復元
        for i in range(len(self.source_indices_asc)):
            original_idx = self.source_indices_asc[i]
            row_data = self.data_of_rows_at_original_source_positions[i]
            self.table.insertRow(original_idx)
            self._set_row_data_to_table(original_idx, row_data)
        self.table.blockSignals(False)


class DuplicateMultipleRowsCommand(QUndoCommand):
    def __init__(self, table: QTableWidget,
                 source_rows_data_map: Dict[int, List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict]]]]],
                 description: str = "複数行複写"):
        super().__init__(description)
        self.table = table
        self.source_rows_data_map = dict(sorted(source_rows_data_map.items()))
        self.source_indices_desc = sorted(source_rows_data_map.keys(), reverse=True)
        self.source_indices_asc = sorted(source_rows_data_map.keys())
        self.inserted_row_indices_in_redo: List[int] = []

    def redo(self):
        self.table.blockSignals(True)
        self.inserted_row_indices_in_redo.clear()
        try:
            if not self.source_indices_asc:
                return
            insert_start_row = self.source_indices_desc[0] + 1
            for i, original_row_index in enumerate(self.source_indices_asc):
                row_data_to_copy = self.source_rows_data_map[original_row_index]
                current_insert_pos = insert_start_row + i
                self.table.insertRow(current_insert_pos)
                self.inserted_row_indices_in_redo.append(current_insert_pos)
                for col, data in enumerate(row_data_to_copy):
                    if isinstance(data, QTableWidgetItem): # QTableWidgetItem の場合はクローンしてセット
                        self.table.setItem(current_insert_pos, col, data.clone())
                    # --- ここから MoveMultipleRowsCommand._set_row_data_to_table と同様のロジック ---
                    elif isinstance(data, dict) and 'text' in data:
                        text_value = data['text']
                        if not isinstance(text_value, str):
                            text_value = str(text_value)
                        item = QTableWidgetItem()
                        item.setText(text_value)
                        if 'flags' in data and data['flags'] is not None:
                            item.setFlags(Qt.ItemFlags(data['flags']))
                        if 'textAlignment' in data and data['textAlignment'] is not None:
                            item.setTextAlignment(data['textAlignment'])
                        self.table.setItem(current_insert_pos, col, item)
                    # --- ここまで ---
                    elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], type) and issubclass(data[0], QComboBox):
                        widget_class, properties = data
                        parent_widget = self.table.parent()
                        if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                            combo = parent_widget._create_unit_combobox()
                            combo.setCurrentText(properties.get('currentText', ''))
                            self.table.setCellWidget(current_insert_pos, col, combo)
                        else:
                            self.table.setItem(current_insert_pos, col, QTableWidgetItem("復元エラー"))
                    else:
                        self.table.setItem(current_insert_pos, col, QTableWidgetItem(""))
        finally:
            self.table.blockSignals(False)

    def undo(self):
        self.table.blockSignals(True)
        for row_to_remove in sorted(self.inserted_row_indices_in_redo, reverse=True):
            self.table.removeRow(row_to_remove)
        self.table.blockSignals(False)


class RemoveMultipleRowsCommand(QUndoCommand):
    def __init__(self, table: QTableWidget, rows: List[int], rows_data: Dict[int, List[Optional[Union[QTableWidgetItem, Tuple[Type[QComboBox], Dict]]]]], description: str = "複数行削除"):
        super().__init__(description)
        self.table = table
        self.rows_ascending = sorted(rows)
        self.rows_descending = sorted(rows, reverse=True)
        self.rows_data_saved = rows_data # ここで渡される rows_data の形式に注意

    def redo(self):
        self.table.blockSignals(True)
        for row in self.rows_descending:
            self.table.removeRow(row)
        self.table.blockSignals(False)

    def undo(self):
        self.table.blockSignals(True)
        for row in self.rows_ascending:
            self.table.insertRow(row)
            row_data = self.rows_data_saved.get(row, [])
            for col, saved_data in enumerate(row_data):
                if isinstance(saved_data, QTableWidgetItem): # QTableWidgetItem の場合はクローンしてセット
                    self.table.setItem(row, col, saved_data.clone())
                # --- ここから MoveMultipleRowsCommand._set_row_data_to_table と同様のロジック ---
                elif isinstance(saved_data, dict) and 'text' in saved_data:
                    text_value = saved_data['text']
                    if not isinstance(text_value, str):
                        text_value = str(text_value)
                    item = QTableWidgetItem()
                    item.setText(text_value)
                    if 'flags' in saved_data and saved_data['flags'] is not None:
                        item.setFlags(Qt.ItemFlags(saved_data['flags']))
                    if 'textAlignment' in saved_data and saved_data['textAlignment'] is not None:
                        item.setTextAlignment(saved_data['textAlignment'])
                    self.table.setItem(row, col, item)
                # --- ここまで ---
                elif isinstance(saved_data, tuple) and len(saved_data) == 2 and isinstance(saved_data[0], type) and issubclass(saved_data[0], QComboBox):
                    widget_class, properties = saved_data
                    parent_widget = self.table.parent()
                    if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                        combo = parent_widget._create_unit_combobox()
                        combo.setCurrentText(properties.get('currentText', ''))
                        self.table.setCellWidget(row, col, combo)
                    else: self.table.setItem(row, col, QTableWidgetItem("復元エラー"))
                else:
                    self.table.setItem(row, col, QTableWidgetItem(""))
        self.table.blockSignals(False)
