# C:\Users\katuy\OneDrive\Estimate_app\main.py
import sys
import os
from PySide6.QtCore import (
    Qt, Slot, Signal, QStandardPaths, QSettings, QPoint, QSize, QLocale,
    QDate, QMarginsF, QTimer # QTimer をインポート
)
from PySide6.QtGui import (
    QAction, QIcon, QKeySequence, QPalette, QColor, QScreen, QPainter,
    QPageSize, QPageLayout, QUndoStack
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QDateEdit, QPushButton, QTableWidget, QHeaderView, QAbstractItemView,
    QTableWidgetItem, QComboBox, QStyledItemDelegate, QDoubleSpinBox,
    QGridLayout, QSizePolicy, QSpacerItem, QFrame, QDialog,
    QDialogButtonBox, QPlainTextEdit
)
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog



# --- 定数 ---
APP_NAME = "EstimateApp"
APP_VERSION = "0.1.0"
ORGANIZATION_NAME = "MyCompany" # QSettings用
ORGANIZATION_DOMAIN = "mycompany.com" # QSettings用
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
COLOR_BACKGROUND = "#F0F0F0"
COLOR_PRIMARY = "#4A90E2"
COLOR_SECONDARY = "#50E3C2"
COLOR_TEXT = "#333333" # メニューなどの基本的な文字色
COLOR_WHITE = "#FFFFFF"
COLOR_ERROR = "#D0021B"
COLOR_LIGHT_GRAY = "#D3D3D3" # 非活性時の文字色などに使用
COLOR_SUCCESS = "#7ED321"
COLOR_WARNING = "#F5A623"

# アイコンディレクトリのパスを設定
script_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(script_dir, "icons")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("--- main.py モジュール読み込み開始 ---") # 起動確認用
        print("--- インポート完了 ---") # 起動確認用

        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT) # 初期位置とサイズ

        # --- アプリケーション全体のパレット設定 ---
        main_palette = self.palette()
        main_palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BACKGROUND))
        main_palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
        main_palette.setColor(QPalette.ColorRole.Base, QColor(COLOR_WHITE)) # QLineEditなどの背景
        main_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_SECONDARY)) # QComboBoxのドロップダウンなど
        main_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLOR_WHITE))
        main_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_TEXT))
        main_palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT)) # QLineEditなどのテキスト
        main_palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_PRIMARY))
        main_palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_WHITE))
        main_palette.setColor(QPalette.ColorRole.BrightText, QColor(COLOR_ERROR)) # エラーメッセージなど
        main_palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_PRIMARY)) # 選択時のハイライト
        main_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_WHITE))
        self.setPalette(main_palette)
        self.setAutoFillBackground(True) # パレット背景の描画を有効にする

        # --- UNDO スタックの作成 ---
        # self.undo_stack = QUndoStack(self) # Undo/Redo機能が必要な場合はコメント解除
        self.undo_stack = QUndoStack(self) # QUndoStack を初期化

        # --- ウィジェットの作成 ---
        try:
            from detail_page_widget import DetailPageWidget
            from cover_page_widget import CoverPageWidget
        except ModuleNotFoundError as e:
            QMessageBox.critical(self, "エラー", f"必要なモジュールが見つかりません: {e}\nアプリケーションを終了します。")
            sys.exit(1)


        self.cover_page = CoverPageWidget()
        if self.undo_stack:
            self.detail_page = DetailPageWidget(self.undo_stack)
        else:
            pass  # Placeholder to ensure the method has a valid body
            pass  # Placeholder to ensure the method has a valid body
            pass  # Placeholder to ensure the method has a valid body
            self.detail_page = DetailPageWidget(self.undo_stack) # undo_stack (None) を渡す

        # --- QStackedWidget の設定 ---
        self.stacked_widget = QStackedWidget()
        stack_palette = self.stacked_widget.palette()
        stack_palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_WHITE))
        self.stacked_widget.setPalette(stack_palette)
        self.stacked_widget.setAutoFillBackground(True)
        self.stacked_widget.addWidget(self.cover_page)
        self.stacked_widget.addWidget(self.detail_page)

        self.setCentralWidget(self.stacked_widget)

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()

        self.cover_page.details_requested.connect(self.show_detail_page)
        self.detail_page.cover_requested.connect(self.show_cover_page)
        self.stacked_widget.currentChanged.connect(self._on_page_changed)
        if hasattr(self.detail_page, 'table') and self.detail_page.table: # table属性の存在確認
            self.detail_page.table.itemSelectionChanged.connect(self._on_detail_selection_changed)
        else:
            print("WARN: DetailPageWidget does not have 'table' attribute or it is None. itemSelectionChanged signal not connected.")

        if hasattr(self.detail_page, 'status_message_requested'): # シグナルの存在確認
            self.detail_page.status_message_requested.connect(self.show_status_message)

        self.show_cover_page()
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _create_actions(self):
        """アクションを作成する"""
        # --- UNDO アクション ---
        if self.undo_stack:
            self.undo_action = self.undo_stack.createUndoAction(self, "元に戻す")
            self.redo_action = self.undo_stack.createRedoAction(self, "やり直し")
        else:
            self.undo_action = QAction("元に戻す (無効)", self)
            self.redo_action = QAction("やり直し (無効)", self)
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)

        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setIcon(QIcon(os.path.join(icon_dir, "undo.png")))
        self.undo_action.setToolTip("直前の操作を元に戻します")

        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setIcon(QIcon(os.path.join(icon_dir, "redo.png")))
        self.redo_action.setToolTip("元に戻した操作をやり直します")

        self.add_row_action = QAction("行追加", self)
        self.add_row_action.setIcon(QIcon(os.path.join(icon_dir, "add_row.png")))
        self.add_row_action.setToolTip("明細に新しい行を追加します")
        self.add_row_action.triggered.connect(self._add_detail_row)

        self.remove_row_action = QAction("行削除", self)
        self.remove_row_action.setIcon(QIcon(os.path.join(icon_dir, "remove_row.png")))
        self.remove_row_action.setToolTip("選択した行を明細から削除します")
        self.remove_row_action.triggered.connect(self._remove_detail_row)

        self.duplicate_row_action = QAction("行複製", self)
        self.duplicate_row_action.setIcon(QIcon(os.path.join(icon_dir, "duplicate_row.png")))
        self.duplicate_row_action.setToolTip("選択した行を複製します")
        self.duplicate_row_action.triggered.connect(self._duplicate_detail_row)

        self.go_to_detail_action = QAction("明細編集へ", self)
        self.go_to_detail_action.setToolTip("明細編集画面に移動します")
        self.go_to_detail_action.setIcon(QIcon(os.path.join(icon_dir, "go_to_detail.png")))
        self.go_to_detail_action.triggered.connect(self.show_detail_page)

        self.go_to_cover_action = QAction("表紙へ戻る", self)
        self.go_to_cover_action.setToolTip("表紙画面に戻ります")
        self.go_to_cover_action.setIcon(QIcon(os.path.join(icon_dir, "go_to_cover.png")))
        self.go_to_cover_action.triggered.connect(self.show_cover_page)

        self.save_action = QAction("上書き保存", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.setIcon(QIcon(os.path.join(icon_dir, "save.png")))
        self.save_action.setToolTip("現在の内容をファイルに上書き保存します")
        self.save_action.triggered.connect(self._save_data)

        self.save_as_action = QAction("名前を付けて保存...", self) # 新しいアクション
        # self.save_as_action.setShortcut(QKeySequence.SaveAs) # 標準的なショートカットがあれば
        self.save_as_action.setIcon(QIcon(os.path.join(icon_dir, "save_as.png"))) # アイコンは適宜用意
        self.save_as_action.setToolTip("現在の内容を新しい名前でファイルに保存します")
        self.save_as_action.triggered.connect(self._save_data_as)


        self.print_action = QAction("印刷プレビュー", self)
        self.print_action.setIcon(QIcon(os.path.join(icon_dir, "print.png")))
        self.print_action.setToolTip("印刷プレビューを表示します")
        self.print_action.triggered.connect(self._print_preview)

        self.exit_action = QAction("終了", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

    def _create_menus(self):
        file_menu = self.menuBar().addMenu("ファイル")
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action) # メニューに追加
        file_menu.addAction(self.print_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("編集")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.add_row_action)
        edit_menu.addAction(self.remove_row_action)
        edit_menu.addAction(self.duplicate_row_action)

    def _create_toolbars(self):
        self.main_toolbar = self.addToolBar("メイン操作")
        self.main_toolbar.addAction(self.undo_action)
        self.main_toolbar.addAction(self.redo_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.add_row_action)
        self.main_toolbar.addAction(self.remove_row_action)
        self.main_toolbar.addAction(self.duplicate_row_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.go_to_detail_action)
        self.main_toolbar.addAction(self.go_to_cover_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.save_action)
        self.main_toolbar.addAction(self.print_action)
        if self.stacked_widget: # stacked_widget が None でないことを確認
            self._update_action_states(self.stacked_widget.currentIndex())
        else:
            self._update_action_states(0) # フォールバック

    def _create_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("準備完了", 3000)

    @Slot()
    def show_cover_page(self):
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            # 明細ページが表示されていた場合、合計金額を表紙に反映
            current_subtotal_str = "￥0" # デフォルト値
            current_tax_str = "￥0"     # デフォルト値
            current_total_str = "￥0"   # デフォルト値
            try:
                if hasattr(self.detail_page, 'get_current_subtotal'):
                    current_subtotal_str = self.detail_page.get_current_subtotal()
                if hasattr(self.detail_page, 'get_current_tax'):
                    current_tax_str = self.detail_page.get_current_tax()
                if hasattr(self.detail_page, 'get_current_total'):
                    current_total_str = self.detail_page.get_current_total()
                
                if hasattr(self.cover_page, 'set_totals'):
                    self.cover_page.set_totals(current_subtotal_str, current_tax_str, current_total_str)
                else:
                    print("WARN: CoverPageWidget does not have 'set_totals' method.")
            except Exception as e:
                print(f"Error updating totals on cover page from detail page: {e}")
        
        if self.stacked_widget:
            self.stacked_widget.setCurrentWidget(self.cover_page)
        self.setWindowTitle(WINDOW_TITLE + " - 表紙")

    @Slot()
    def show_detail_page(self):
        """明細ページを表示する"""
        project_name = ""
        client_name = ""
        period_text = ""

        try:
            # CoverPageWidget から情報を取得
            if hasattr(self.cover_page, 'get_project_name'):
                project_name = self.cover_page.get_project_name()
            else:
                print("WARN: CoverPageWidget does not have 'get_project_name' method.")
            
            if hasattr(self.cover_page, 'get_client_name'):
                client_name = self.cover_page.get_client_name()
            else:
                print("WARN: CoverPageWidget does not have 'get_client_name' method.")

            if hasattr(self.cover_page, 'get_period_text'):
                period_text = self.cover_page.get_period_text()
            else:
                print("WARN: CoverPageWidget does not have 'get_period_text' method.")

        except AttributeError as e:
            print(f"WARN: Error accessing attributes from CoverPageWidget: {e}")
            # フォールバック値を設定（エラー発生時）
            project_name = project_name if project_name else "（表紙情報取得エラー）"
            client_name = client_name if client_name else "（表紙情報取得エラー）"
            period_text = period_text if period_text else "（表紙情報取得エラー）"

        if hasattr(self.detail_page, 'update_header'):
            # DetailPageWidgetのヘッダーを更新
            # 金額関連は明細ページ側で計算・表示されるため、ここでは初期値またはプレースホルダーを渡す
            self.detail_page.update_header(
                project_name,
                client_name,
                period_text,
                "---",  # total (明細ページで計算)
                "---",  # subtotal (明細ページで計算)
                "---"   # tax (明細ページで計算)
            )
            # 明細ページが表示される際に、現在のテーブル内容に基づいて合計を強制的に再計算・表示させる
            if hasattr(self.detail_page, '_update_detail_totals'):
                self.detail_page._update_detail_totals()
        else:
            print("WARN: DetailPageWidget does not have 'update_header' method.")

        if self.stacked_widget:
            self.stacked_widget.setCurrentWidget(self.detail_page)
        self.setWindowTitle(WINDOW_TITLE + " - 明細")

    @Slot()
    def _on_detail_selection_changed(self):

        # itemSelectionChanged が短時間に複数回発行されることがあるため、
        # QTimer.singleShot を使って実際の更新処理を遅延させ、
        # イベントが落ち着いた後の状態でアクションを更新します。
        QTimer.singleShot(0, self._deferred_update_actions_for_selection)

    def _deferred_update_actions_for_selection(self):
        """ _on_detail_selection_changed から遅延実行されるアクション更新処理 """
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            self._update_action_states(self.stacked_widget.currentIndex())

    @Slot(int)
    def _on_page_changed(self, index: int):
        self._update_action_states(index)

    def _update_action_states(self, index: int):

        if not self.stacked_widget: # stacked_widget が None の場合は何もしない
            return

        is_detail_page = (self.stacked_widget.currentWidget() == self.detail_page)
        is_cover_page = (self.stacked_widget.currentWidget() == self.cover_page)

        if self.undo_stack:
            self.undo_action.setEnabled(is_detail_page and self.undo_stack.canUndo())
            self.redo_action.setEnabled(is_detail_page and self.undo_stack.canRedo())
        else: # undo_stack がない場合は常に無効
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)


        self.add_row_action.setVisible(is_detail_page)
        self.remove_row_action.setVisible(is_detail_page)
        self.duplicate_row_action.setVisible(is_detail_page)
        self.add_row_action.setEnabled(is_detail_page)

        can_remove_or_duplicate = False
        if is_detail_page and hasattr(self.detail_page, 'table') and self.detail_page.table:
                    # selectedItems() は QList<QTableWidgetItem*> を返すので、空かどうかで判断
                    if self.detail_page.table.selectionModel() and self.detail_page.table.selectionModel().hasSelection():
                         # 選択されている行があるかどうかも確認するとより確実
                        can_remove_or_duplicate = bool(list(set(idx.row() for idx in self.detail_page.table.selectedIndexes())))
        else:
            pass
        self.remove_row_action.setEnabled(is_detail_page and can_remove_or_duplicate)
        self.duplicate_row_action.setEnabled(is_detail_page and can_remove_or_duplicate)


        self.go_to_detail_action.setVisible(is_cover_page)
        self.go_to_detail_action.setEnabled(is_cover_page)
        self.go_to_cover_action.setVisible(is_detail_page)
        self.go_to_cover_action.setEnabled(is_detail_page)

        self.save_action.setEnabled(is_detail_page)
        self.save_as_action.setEnabled(is_detail_page) # Save As も明細ページでのみ有効
        self.print_action.setEnabled(True)

    @Slot()
    def _add_detail_row(self):
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            if hasattr(self.detail_page, 'add_row'):
                self.detail_page.add_row()
            else:
                print("WARN: DetailPageWidget does not have 'add_row' method.")


    @Slot()
    def _remove_detail_row(self):
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            if hasattr(self.detail_page, 'remove_row'):
                self.detail_page.remove_row()
            else:
                print("WARN: DetailPageWidget does not have 'remove_row' method.")

    @Slot()
    def _duplicate_detail_row(self):
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            if hasattr(self.detail_page, 'duplicate_row'):
                self.detail_page.duplicate_row()
            else:
                print("WARN: DetailPageWidget does not have 'duplicate_row' method.")

    @Slot()
    def _save_data(self):
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            if hasattr(self.detail_page, 'handle_save_file'):
                self.detail_page.handle_save_file()
            else:
                print("WARN: DetailPageWidget does not have 'handle_save_file' method.")
                if self.statusBar(): self.statusBar().showMessage("保存機能が実装されていません。", 3000)
        # else: # _update_action_states で制御しているので、この分岐は不要になる
            # if self.statusBar(): self.statusBar().showMessage("保存は明細ページでのみ可能です", 3000)
    @Slot()
    def _save_data_as(self):
        """現在のデータを新しい名前を付けてファイルに保存する"""
        if self.stacked_widget and self.stacked_widget.currentWidget() == self.detail_page:
            if hasattr(self.detail_page, 'handle_save_as_file'):
                self.detail_page.handle_save_as_file()
            else:
                print("WARN: DetailPageWidget does not have 'handle_save_as_file' method.")
                if self.statusBar(): self.statusBar().showMessage("名前を付けて保存機能が実装されていません。", 3000)

    @Slot()
    def _print_preview(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.paintRequested.connect(self._handle_paint_request)
        preview_dialog.exec()
        if self.statusBar(): self.statusBar().showMessage("印刷プレビューを表示しました (仮)", 3000)
        print("印刷プレビュー処理を実行 (仮)")

    def _handle_paint_request(self, printer):
        print("実際に印刷する処理 (未実装)")

    @Slot(str, int)
    def show_status_message(self, message: str, timeout: int = 3000):
        if self.statusBar():
            self.statusBar().showMessage(message, timeout)
        else:
            print(f"Status: {message}")

    def closeEvent(self, event):
        event.accept()


if __name__ == '__main__':
    print("--- main.py モジュール読み込み開始 ---")
    print("--- インポート完了 ---")
    app = QApplication(sys.argv)

    # --- スタイルシートの適用例 ---
    # メニューの文字色を COLOR_TEXT (濃い灰色) に設定
    # 背景色や選択時の色も調整しています。環境によって微調整が必要な場合があります。
    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: {COLOR_BACKGROUND};
        }}
        QMenuBar {{
            background-color: {COLOR_BACKGROUND}; /* メニューバー自体の背景色 */
            color: {COLOR_TEXT}; /* メニューバーのトップレベル項目の文字色 */
        }}
        QMenuBar::item {{
            background-color: transparent; /* 通常時のアイテム背景は透明に */
            color: {COLOR_TEXT}; /* 通常時のアイテム文字色 */
            padding: 4px 8px; /* 少し余白を調整 */
        }}
        QToolButton:disabled {{ /* 非活性時のツールバーボタン */
            color: {COLOR_LIGHT_GRAY}; /* 文字色を薄いグレーに */
            /* background-color: transparent; */ /* 背景は通常時と同じでよければ */
        }}
        QMenuBar::item:selected {{ /* マウスオーバー時や選択時 */
            background-color: {COLOR_PRIMARY}; /* 選択時の背景色 */
            color: {COLOR_WHITE}; /* 選択時の文字色 */
        }}
        QMenuBar::item:pressed {{ /* クリック時 */
            background-color: {COLOR_SECONDARY};
        }}
        QMenu {{
            background-color: {COLOR_WHITE}; /* ドロップダウンメニューの背景色 */
            color: {COLOR_TEXT}; /* ドロップダウンメニューの文字色 */
            border: 1px solid #CCCCCC; /* メニューの境界線 */
        }}
        QMenu::item {{
            padding: 4px 20px; /* アイテムの余白 */
        }}
        QMenu::item:selected {{
            background-color: {COLOR_PRIMARY};
            color: {COLOR_WHITE};
        }}
        QToolBar {{
            background-color: {COLOR_BACKGROUND};
            border: none;
        }}
        QToolButton {{ /* ツールバー上のボタン */
            color: {COLOR_TEXT}; /* 通常時の文字色 */
            background-color: transparent; /* 通常時は背景透明 */
            padding: 4px;
            margin: 1px;
        }}
        QPushButton {{
            background-color: {COLOR_PRIMARY};
            color: {COLOR_WHITE};
            border-radius: 5px;
            padding: 5px;
        }}
        QPushButton:hover {{
            background-color: #3a80d2; /* 少し暗い青 */
        }}
        QLineEdit, QDateEdit, QDoubleSpinBox, QComboBox {{
            border: 1px solid #CCCCCC;
            padding: 5px;
            border-radius: 3px;
            background-color: {COLOR_WHITE};
            color: {COLOR_TEXT};
        }}
        QTableWidget {{
            gridline-color: #DDDDDD;
        }}
        QStatusBar {{ /* ★★★ ここから追加 ★★★ */
            color: {COLOR_TEXT}; /* 文字色を constants.py の COLOR_TEXT (例: #333333) に設定 */
            background-color: {COLOR_LIGHT_GRAY}; /* 背景色を薄いグレーに (お好みで調整) */
            /* font-weight: bold; */ /* 必要であれば太字に */
            padding: 2px 5px;      /* 少しパディングを追加して見やすく */
        }}                         /* ★★★ ここまで追加 ★★★ */
    """)

    main_window = MainWindow()
    main_window.show()
    print("--- アプリケーション開始 ---")
    sys.exit(app.exec())
