# commands.py

from PySide6.QtGui import QUndoCommand, QStandardItemModel # QStandardItemModel をインポート (QComboBox用)
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QApplication, QComboBox
from typing import List, Dict, Optional, Callable # For type hinting
# DetailPageWidget を直接インポートすると循環参照になるため、型ヒントのみ使用
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from detail_page_widget import DetailPageWidget

class AddRowCommand(QUndoCommand):
    """行を追加するコマンド"""
    def __init__(self, table: QTableWidget, initialize_row_func: Callable[[int], None], description: str = "行追加"):
        super().__init__(description)
        self.table = table
        # 追加される行のインデックス（現在の行数）
        self.row_index = table.rowCount()
        self.initialize_row_func = initialize_row_func
        # print(f"AddRowCommand: row_index={self.row_index}") # Debug

    def redo(self):
        """行を追加し、初期化する"""
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        if self.initialize_row_func:
            self.initialize_row_func(self.row_index) # 行を初期化
        self.table.blockSignals(False)
        # print(f"Redo AddRow: Row {self.row_index} inserted.") # Debug

    def undo(self):
        """追加した行を削除する"""
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)
        # print(f"Undo AddRow: Row {self.row_index} removed.") # Debug

class InsertRowCommand(QUndoCommand):
    """指定した位置に行を挿入するコマンド"""
    def __init__(self, table: QTableWidget, row_index: int, initialize_row_func: Callable[[int], None], description: str = "行挿入"):
        super().__init__(description)
        self.table = table
        self.row_index = row_index # 挿入する位置
        self.initialize_row_func = initialize_row_func
        # print(f"InsertRowCommand: row_index={self.row_index}") # Debug

    def redo(self):
        """指定位置に行を挿入し、初期化する"""
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        if self.initialize_row_func:
            self.initialize_row_func(self.row_index) # 行を初期化
        self.table.blockSignals(False)
        # print(f"Redo InsertRow: Row inserted at {self.row_index}.") # Debug

    def undo(self):
        """挿入した行を削除する"""
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)
        # print(f"Undo InsertRow: Row at {self.row_index} removed.") # Debug
class RemoveRowCommand(QUndoCommand):
    """行を削除するコマンド"""
    def __init__(self, table: QTableWidget, row_index: int, row_data: List[Optional[QTableWidgetItem]], description: str = "行削除"):
        super().__init__(description)
        self.table = table
        self.row_index = row_index
        # 削除される行のアイテムデータ (クローン) を保持
        self.row_data_cloned = row_data
        # print(f"RemoveRowCommand: row_index={self.row_index}") # Debug

    def redo(self):
        """行を削除する"""
        self.table.blockSignals(True)
        self.table.removeRow(self.row_index)
        self.table.blockSignals(False)
        # print(f"Redo RemoveRow: Row {self.row_index} removed.") # Debug

    def undo(self):
        """削除した行を復元する"""
        self.table.blockSignals(True)
        self.table.insertRow(self.row_index)
        # 保持していたアイテムデータを復元
        for col, cloned_item in enumerate(self.row_data_cloned):
            if cloned_item:
                # クローンしたアイテムをセット
                self.table.setItem(self.row_index, col, cloned_item.clone()) # 再度クローンしてセット
            else:
                self.table.setItem(self.row_index, col, QTableWidgetItem("")) # 空アイテム
        self.table.blockSignals(False)
        # print(f"Undo RemoveRow: Row {self.row_index} restored.") # Debug


class MoveRowCommand(QUndoCommand):
    """行を移動するコマンド (ドラッグ＆ドロップ用)"""
    def __init__(self, table: QTableWidget, source_row: int, dest_row: int, description: str = "行移動"):
        super().__init__(description)
        self.table = table
        self.source_row = source_row
        # 挿入先の行インデックス (removeRow後の実際のインデックス)
        self.actual_dest_row = dest_row
        if self.source_row < self.actual_dest_row:
            self.actual_dest_row -= 1

        # 移動する行のデータを保持 (アイテムまたはウィジェット情報)
        self.row_data_cloned = []
        for col in range(table.columnCount()):
            item = table.item(source_row, col)
            widget = table.cellWidget(source_row, col)
            if widget and isinstance(widget, QComboBox): # QComboBox の場合
                # クラスと現在のテキストを保存
                self.row_data_cloned.append((type(widget), {'currentText': widget.currentText()}))
            elif item:
                self.row_data_cloned.append(item.clone()) # アイテムはクローン
            else:
                self.row_data_cloned.append(None) # それ以外は None
        # print(f"MoveRowCommand: source={self.source_row}, dest={dest_row}, actual_dest={self.actual_dest_row}") # Debug

    def redo(self):
        """行を移動する (Remove -> Insert -> Set)"""
        self.table.blockSignals(True)
        try:
            # 1. 移動元の行を削除
            self.table.removeRow(self.source_row)
            # 2. 新しい行を挿入
            self.table.insertRow(self.actual_dest_row)
            # 3. 保存したアイテムデータを新しい行にセット
            for col, data in enumerate(self.row_data_cloned):
                if isinstance(data, QTableWidgetItem):
                    self.table.setItem(self.actual_dest_row, col, data.clone()) # アイテムは再度クローン
                elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], type) and issubclass(data[0], QComboBox):
                    # QComboBox の情報を復元
                    widget_class, properties = data
                    # DetailPageWidget のメソッドを借りて ComboBox を作成・設定
                    combo = self.table.parent()._create_unit_combobox() # 親ウィジェットのメソッドを呼び出す想定
                    combo.setCurrentText(properties.get('currentText', ''))
                    self.table.setCellWidget(self.actual_dest_row, col, combo)
                else:
                    # None の場合
                    self.table.setItem(self.actual_dest_row, col, QTableWidgetItem(""))
        finally:
            self.table.blockSignals(False)
        self.table.selectRow(self.actual_dest_row) # 移動先を選択
        # print(f"Redo MoveRow: Row {self.source_row} moved to {self.actual_dest_row}") # Debug


    def undo(self):
        """行移動を元に戻す (Remove -> Insert -> Set)"""
        self.table.blockSignals(True)
        try:
            # 1. redo で挿入された行を削除
            self.table.removeRow(self.actual_dest_row)
            # 2. 元の位置に新しい行を挿入
            self.table.insertRow(self.source_row)
            # 3. 保存したアイテムデータを元の位置に復元
            for col, data in enumerate(self.row_data_cloned):
                if isinstance(data, QTableWidgetItem):
                    self.table.setItem(self.source_row, col, data.clone()) # アイテムは再度クローン
                elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], type) and issubclass(data[0], QComboBox):
                    # QComboBox の情報を復元
                    widget_class, properties = data
                    combo = self.table.parent()._create_unit_combobox() # 親ウィジェットのメソッドを呼び出す想定
                    combo.setCurrentText(properties.get('currentText', ''))
                    self.table.setCellWidget(self.source_row, col, combo)
                else:
                    # None の場合
                    self.table.setItem(self.source_row, col, QTableWidgetItem(""))
        finally:
            self.table.blockSignals(False)
        self.table.selectRow(self.source_row) # 元の位置を選択
        # print(f"Undo MoveRow: Row moved back from {self.actual_dest_row} to {self.source_row}") # Debug


class ChangeItemCommand(QUndoCommand):
    """テーブルアイテムの内容を変更するコマンド"""
    # セル変更を一意に識別するためのID (mergeWithで使用)
    # row * col_count + col のような形式で計算
    CHANGE_ITEM_ID = 1001

    def __init__(self, table: QTableWidget, row: int, col: int, old_text: str, new_text: str, description: str = "セル編集"):
        super().__init__(description)
        self.table = table
        self.row = row
        self.col = col
        self.old_text = old_text
        self.new_text = new_text
        # DetailPageWidget のインスタンスを取得 (列インデックス定数を使うため)
        # 直接インポートせず、親ウィジェットから取得することで循環参照を回避
        parent_widget = table.parent()
        self.detail_page: Optional['DetailPageWidget'] = parent_widget if hasattr(parent_widget, 'COL_ITEM') else None
        # print(f"ChangeItemCommand: ({row}, {col}) Old='{old_text}', New='{new_text}'") # Debug

    def _format_text(self, text: str) -> str:
        """列に応じてテキストをフォーマットする"""
        if not self.detail_page: return text # DetailPageWidget がなければそのまま返す

        try:
            # 単位列はフォーマットしない
            if self.col == self.detail_page.COL_UNIT:
                return text

            cleaned_text = text.replace(",", "").replace("￥", "").strip()
            value = float(cleaned_text or 0.0)

            if self.col == self.detail_page.COL_QUANTITY:
                formatted = f"{value:,.1f}" # カンマ区切りを追加
                # print(f"DEBUG: Formatting Quantity ({self.row}, {self.col}): Input='{text}', Output='{formatted}'") # デバッグプリント追加
                return formatted
            elif self.col == self.detail_page.COL_UNIT_PRICE or self.col == self.detail_page.COL_AMOUNT:
                # 単価と金額は整数カンマ区切り
                return f"{int(value):,}"
            else:
                return text # その他の列はそのまま
        except (ValueError, TypeError, AttributeError):
            return text # エラー時は元のテキストを返す

    def redo(self):
        """変更後のテキストをセルに設定する"""
        is_unit_column = self.col == 2
        formatted_text = self._format_text(self.new_text) # フォーマット処理を追加

        if is_unit_column:
            widget = self.table.cellWidget(self.row, self.col)
            if isinstance(widget, QComboBox):
                # QComboBox の currentTextChanged シグナルが再トリガーされないようにブロック
                was_blocked = widget.signalsBlocked()
                widget.blockSignals(True)
                widget.setCurrentText(formatted_text) # フォーマット済みテキストを設定
                widget.blockSignals(was_blocked)
                # print(f"Redo ChangeItem (ComboBox): ({self.row}, {self.col}) set to '{self.new_text}'") # Debug
        else:
            item = self.table.item(self.row, self.col)
            if item:
                # QTableWidgetItem の setText は QUndoStack が管理するのでシグナルブロック不要
                item.setText(formatted_text) # フォーマット済みテキストを設定
                # print(f"Redo ChangeItem (Item): ({self.row}, {self.col}) set to '{self.new_text}'") # Debug

    def undo(self):
        """変更前のテキストをセルに設定する"""
        is_unit_column = self.col == 2 # 列番号で判定
        formatted_text = self._format_text(self.old_text) # フォーマット処理を追加

        if is_unit_column:
            widget = self.table.cellWidget(self.row, self.col)
            if isinstance(widget, QComboBox):
                was_blocked = widget.signalsBlocked()
                widget.blockSignals(True)
                widget.setCurrentText(self.old_text)
                # widget.setCurrentText(formatted_text) # QComboBox は元のテキストをそのまま戻す
                widget.blockSignals(was_blocked)
                # print(f"Undo ChangeItem (ComboBox): ({self.row}, {self.col}) restored to '{self.old_text}'") # Debug
        else:
            item = self.table.item(self.row, self.col)
            if item:
                item.setText(formatted_text) # フォーマット済みテキストを設定
                # print(f"Undo ChangeItem (Item): ({self.row}, {self.col}) restored to '{self.old_text}'") # Debug

    def id(self) -> int:
        # 同じセルへの連続変更をマージするために、セル位置に基づいたIDを返す
        return self.CHANGE_ITEM_ID + self.row * self.table.columnCount() + self.col

    def mergeWith(self, other: QUndoCommand) -> bool:
        # 同じIDを持つ連続したコマンドの場合、新しいテキストで上書き
        if other.id() == self.id():
            self.new_text = other.new_text # Keep the latest text
            # print(f"Merged ChangeItem: ({self.row}, {self.col}) New text is now '{self.new_text}'") # Debug
            return True
        return False


class DuplicateRowCommand(QUndoCommand):
    """指定した行を複製して、その下に挿入するコマンド"""
    # __init__ の型ヒントを修正: QTableWidgetItem だけでなく、タプルも含む可能性
    def __init__(self, table: QTableWidget, source_row: int, row_data_to_copy: List[Optional[QTableWidgetItem | tuple]], description: str = "行複写"):
        super().__init__(description)
        self.table = table
        self.source_row = source_row
        self.insert_row = source_row + 1 # 挿入位置は元の行のすぐ下
        # 複製するデータを保持 (QTableWidgetItem はクローン済み、ウィジェット情報はタプル)
        self.row_data_to_copy = row_data_to_copy
        # QComboBox 用の unit_list を DetailPageWidget から取得して保持 (初回のみ)
        # Note: DetailPageWidget がテーブルの親であることを想定
        self.unit_list = getattr(table.parent(), 'unit_list', [])

        # print(f"DuplicateRowCommand: source={source_row}, insert_at={self.insert_row}") # Debug

    def redo(self):
        """指定位置に行を挿入し、複製データをセットする"""
        self.table.blockSignals(True) # テーブル全体のシグナルをブロック
        self.table.insertRow(self.insert_row)

        for col, data_to_copy in enumerate(self.row_data_to_copy): # row_data_cloned -> row_data_to_copy
            if isinstance(data_to_copy, QTableWidgetItem):
                 # QTableWidgetItem の場合は clone() してセット
                 self.table.setItem(self.insert_row, col, data_to_copy.clone())
            elif isinstance(data_to_copy, tuple) and len(data_to_copy) == 2 and isinstance(data_to_copy[0], type) and issubclass(data_to_copy[0], QComboBox):
                # QComboBox の情報を復元
                widget_class, properties = data_to_copy
                # DetailPageWidget のメソッドを借りて ComboBox を作成・設定
                parent_widget = self.table.parent()
                if hasattr(parent_widget, '_create_unit_combobox'):
                    combo = parent_widget._create_unit_combobox()
                    combo.setCurrentText(properties.get('currentText', ''))
                    self.table.setCellWidget(self.insert_row, col, combo)
                else:
                    print(f"警告: 親ウィジェットに _create_unit_combobox が見つかりません。({self.insert_row}, {col})")
            else:
                 # None またはその他の場合 (空アイテムをセット)
                 self.table.setItem(self.insert_row, col, QTableWidgetItem(""))
        self.table.blockSignals(False)
        self.table.selectRow(self.insert_row) # 挿入した行を選択
        # print(f"Redo DuplicateRow: Row inserted at {self.insert_row} with data from {self.source_row}") # Debug

    def undo(self):
        """挿入した行を削除する"""
        self.table.blockSignals(True)
        self.table.removeRow(self.insert_row)
        self.table.blockSignals(False)
        self.table.selectRow(self.source_row) # 元の行を選択し直す
        # print(f"Undo DuplicateRow: Row at {self.insert_row} removed.") # Debug