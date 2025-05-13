# commands.py

from PySide6.QtGui import QUndoCommand, QStandardItemModel # QStandardItemModel をインポート (QComboBox用)
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QApplication, QComboBox
# ↓↓↓ 型ヒント用のクラスをインポート ↓↓↓
from typing import List, Optional, Callable, Tuple, Type, Dict
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
    pass

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
    pass
        # print(f"Undo InsertRow: Row at {self.row_index} removed.") # Debug
class RemoveRowCommand(QUndoCommand):
    """行を削除するコマンド"""
    # row_data の型ヒントを更新 (タプルも含む)
    def __init__(self, table: QTableWidget, row_index: int, row_data: List[Optional[QTableWidgetItem | Tuple[Type[QComboBox], Dict]]], description: str = "行削除"):
        super().__init__(description)
        self.table = table
        self.row_index = row_index
        # 削除される行のアイテム/ウィジェットデータを保持
        self.row_data_saved = row_data # 変数名を変更 (任意)
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
        # 保持していたアイテム/ウィジェットデータを復元
        for col, saved_data in enumerate(self.row_data_saved): # 正しい変数名を使用
            if isinstance(saved_data, QTableWidgetItem):
                # QTableWidgetItem -> cloneしてsetItem
                self.table.setItem(self.row_index, col, saved_data.clone())
            elif isinstance(saved_data, tuple) and len(saved_data) == 2 and isinstance(saved_data[0], type) and issubclass(saved_data[0], QComboBox):
                # QComboBox タプル -> 再生成して setCellWidget
                widget_class, properties = saved_data
                parent_widget = self.table.parent() # 親ウィジェット(DetailPageWidget)を取得
                # 親ウィジェットにコンボボックス作成メソッドがあるか確認
                if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                    combo = parent_widget._create_unit_combobox() # ヘルパーメソッドで作成
                    combo.setCurrentText(properties.get('currentText', '')) # 保存したテキストを設定
                    self.table.setCellWidget(self.row_index, col, combo) # セルにウィジェットを設定
                else:
                    # メソッドが見つからない場合のエラー処理
                    print(f"警告(RemoveRow.undo): 親ウィジェットに _create_unit_combobox が見つかりません。({self.row_index}, {col})")
                    self.table.setItem(self.row_index, col, QTableWidgetItem("復元エラー")) # エラー表示
            elif saved_data is None:
                # None -> 空のアイテムを設定
                self.table.setItem(self.row_index, col, QTableWidgetItem(""))
            else:
                # 予期しないデータ型
                print(f"警告(RemoveRow.undo): 未知のデータ型 {type(saved_data)} を復元できません。 ({self.row_index}, {col})")
                self.table.setItem(self.row_index, col, QTableWidgetItem("復元エラー"))

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

# c:\Users\katuy\OneDrive\Estimate_app\commands.py の MoveRowCommand.redo メソッド

    def redo(self):
        """行を移動する (Remove -> Insert -> Set)"""
        self.table.blockSignals(True)
        print(f"DEBUG: MoveRowCommand.redo START - Moving row {self.source_row} to {self.actual_dest_row}") # 開始ログ
        try:
            # 1. 移動元の行を削除
            print(f"DEBUG: MoveRowCommand.redo - Removing row {self.source_row}")
            self.table.removeRow(self.source_row)
            print(f"DEBUG: MoveRowCommand.redo - Row {self.source_row} removed. Current row count: {self.table.rowCount()}")
            # 2. 新しい行を挿入
            print(f"DEBUG: MoveRowCommand.redo - Inserting row at {self.actual_dest_row}")
            self.table.insertRow(self.actual_dest_row)
            print(f"DEBUG: MoveRowCommand.redo - Row inserted at {self.actual_dest_row}. Current row count: {self.table.rowCount()}")
            # 3. 保存したアイテムデータを新しい行にセット
            print(f"DEBUG: MoveRowCommand.redo - Setting data for row {self.actual_dest_row}")
            for col, data in enumerate(self.row_data_cloned):
                if isinstance(data, QTableWidgetItem):
                    print(f"  DEBUG: Setting item at ({self.actual_dest_row}, {col})")
                    self.table.setItem(self.actual_dest_row, col, data.clone()) # アイテムは再度クローン
                elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], type) and issubclass(data[0], QComboBox):
                    widget_class, properties = data # タプルからクラスとプロパティを取得
                    # DetailPageWidget のメソッドを借りて ComboBox を作成・設定
                    parent_widget = self.table.parent() # 親ウィジェット(DetailPageWidget)を取得
                    if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                        combo = parent_widget._create_unit_combobox() # ヘルパーメソッドで作成
                        combo.setCurrentText(properties.get('currentText', '')) # 保存したテキストを設定
                        self.table.setCellWidget(self.actual_dest_row, col, combo) # セルにウィジェットを設定
                        # ウィジェット設定後の確認ログ (任意)
                        widget_check = self.table.cellWidget(self.actual_dest_row, col)
                        print(f"  DEBUG: Set widget at ({self.actual_dest_row}, {col}). Widget check: {'Exists' if widget_check else 'None'}")
                    else:
                        # メソッドが見つからない場合のエラー処理
                        print(f"ERROR(MoveRow.redo): 親ウィジェットに _create_unit_combobox が見つかりません。({self.actual_dest_row}, {col})")
                        self.table.setItem(self.actual_dest_row, col, QTableWidgetItem("復元エラー")) # エラー表示
                else:
                    # None の場合
                    print(f"  DEBUG: Setting empty item at ({self.actual_dest_row}, {col}) for None data")
                    self.table.setItem(self.actual_dest_row, col, QTableWidgetItem(""))
            print(f"DEBUG: MoveRowCommand.redo - Data setting finished for row {self.actual_dest_row}")
            # 最終確認: 行が存在するか？
            if self.actual_dest_row >= self.table.rowCount():
                print(f"ERROR: Row {self.actual_dest_row} seems to be missing after redo operations!")
            else:
                # 念のため最初のセルの内容を確認
                item_check = self.table.item(self.actual_dest_row, 0)
                print(f"DEBUG: Row {self.actual_dest_row} final check. Item at col 0: {'Exists' if item_check else 'None'}")
        except Exception as e:
            print(f"ERROR in MoveRowCommand.redo during execution: {e}") # 例外ログ
            import traceback
            traceback.print_exc() # 詳細なトレースバックを出力
        finally:
            self.table.blockSignals(False)
        # self.table.selectRow(self.actual_dest_row) # 移動先を選択 (一時的にコメントアウト)
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
    pass


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
    pass


# c:\Users\katuy\OneDrive\Estimate_app\commands.py 内

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
        """複製した行データを新しい行に挿入する"""
        self.table.blockSignals(True)
        try:
            # 1. 新しい行を挿入
            self.table.insertRow(self.insert_row)
            # 2. コピーしたデータを新しい行にセット
            for col, data in enumerate(self.row_data_to_copy):
                if isinstance(data, QTableWidgetItem):
                    self.table.setItem(self.insert_row, col, data.clone()) # アイテムはクローン
                elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], type) and issubclass(data[0], QComboBox):
                    # QComboBox の情報を復元
                    widget_class, properties = data
                    parent_widget = self.table.parent()
                    if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                        combo = parent_widget._create_unit_combobox()
                        combo.setCurrentText(properties.get('currentText', ''))
                        self.table.setCellWidget(self.insert_row, col, combo)
                    else:
                        print(f"ERROR(DuplicateRow.redo): Parent widget does not have _create_unit_combobox method. Cannot restore ComboBox at ({self.insert_row}, {col})")
                        self.table.setItem(self.insert_row, col, QTableWidgetItem("復元エラー")) # Fallback
                else:
                    # None の場合やその他のデータ型
                    self.table.setItem(self.insert_row, col, QTableWidgetItem(""))

        except Exception as e:
            # エラーログは DuplicateRowCommand 用に修正
            print(f"ERROR in DuplicateRowCommand.redo: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.table.blockSignals(False)
        self.table.selectRow(self.insert_row) # 挿入した行を選択
        # print(f"Redo DuplicateRow: Row inserted at {self.insert_row}") # Debug

    def undo(self):
        """挿入した行を削除する"""
        self.table.blockSignals(True)
        self.table.removeRow(self.insert_row)
        self.table.blockSignals(False)
        self.table.selectRow(self.source_row) # 元の行を選択し直す
        # print(f"Undo DuplicateRow: Row at {self.insert_row} removed.") # Debug
    # pass # 不要な pass を削除

# commands.py に追加

# ... (他の import やクラス定義) ...

class RemoveMultipleRowsCommand(QUndoCommand):
    """複数の行をまとめて削除するコマンド"""
    def __init__(self, table: QTableWidget, rows: List[int], rows_data: Dict[int, List[Optional[QTableWidgetItem | Tuple[Type[QComboBox], Dict]]]], description: str = "複数行削除"):
        # rows は昇順で渡されることを想定
        super().__init__(description)
        self.table = table
        self.rows_ascending = sorted(rows) # 昇順のインデックスリスト
        self.rows_descending = sorted(rows, reverse=True) # 降順のインデックスリスト
        self.rows_data_saved = rows_data # {row_index: row_data} の辞書
        # print(f"RemoveMultipleRowsCommand: rows={self.rows_ascending}") # Debug

    def redo(self):
        """複数の行を削除する (降順で処理)"""
        self.table.blockSignals(True)
        # print(f"Redo RemoveMultipleRows: removing rows {self.rows_descending}") # Debug
        for row in self.rows_descending: # 必ず降順で削除
            self.table.removeRow(row)
        self.table.blockSignals(False)

    def undo(self):
        """削除した複数の行を復元する (昇順で処理)"""
        self.table.blockSignals(True)
        # print(f"Undo RemoveMultipleRows: restoring rows {self.rows_ascending}") # Debug
        for row in self.rows_ascending: # 昇順で挿入
            self.table.insertRow(row)
            row_data = self.rows_data_saved.get(row, []) # 保存したデータを取得
            # print(f"  Restoring row {row} with data: {len(row_data)} items") # Debug
            for col, saved_data in enumerate(row_data):
                if isinstance(saved_data, QTableWidgetItem):
                    self.table.setItem(row, col, saved_data.clone())
                elif isinstance(saved_data, tuple) and len(saved_data) == 2 and isinstance(saved_data[0], type) and issubclass(saved_data[0], QComboBox):
                    widget_class, properties = saved_data
                    parent_widget = self.table.parent()
                    if hasattr(parent_widget, '_create_unit_combobox') and callable(parent_widget._create_unit_combobox):
                        combo = parent_widget._create_unit_combobox()
                        combo.setCurrentText(properties.get('currentText', ''))
                        self.table.setCellWidget(row, col, combo)
                    else: self.table.setItem(row, col, QTableWidgetItem("復元エラー")) # Fallback
                else:
                    self.table.setItem(row, col, QTableWidgetItem(""))
        self.table.blockSignals(False)

# ... (他のコマンドクラス) ...