# main.py

import sys
import os # os モジュールをインポート
from PySide6.QtWidgets import (QStatusBar, # QStatusBar をインポート
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QToolBar, QStyle, # QToolBar, QStyle をインポート
    QMenuBar # <- QMenuBar をインポート
)
# ↓↓↓ QPalette, QColor をインポート ↓↓↓
from PySide6.QtGui import QFont, QPalette, QColor, QAction, QKeySequence, QUndoStack, QIcon  # <- QUndoStack を QtGui に移動
from PySide6.QtCore import Qt, Slot, QTimer # <- QTimer をインポート
# ↑↑↑ QPalette, QColor をインポート ↑↑↑
from PySide6.QtCore import Slot # <- Slot をインポート

# 定数、表紙ウィジェット、明細ウィジェットをインポート
from constants import APP_FONT_FAMILY, APP_FONT_SIZE
from cover_page_widget import CoverPageWidget
from detail_page_widget import DetailPageWidget

# --- スクリプトのディレクトリパスを取得 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(script_dir, "icon") # icon フォルダへのパス


class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("木村塗装工業見積書 作成アプリ")

        # ↓↓↓ メインウィンドウの背景色をパレットで白に設定 ↓↓↓
        main_palette = self.palette()
        main_palette.setColor(QPalette.Window, QColor('white'))
        # ↓↓↓ 基本的な文字色も黒に設定 ↓↓↓
        main_palette.setColor(QPalette.WindowText, QColor('black')) # ウィンドウのテキスト
        main_palette.setColor(QPalette.Text, QColor('black'))       # 入力ウィジェットなどのテキスト
        main_palette.setColor(QPalette.ButtonText, QColor('black')) # ボタンのテキスト
        self.setPalette(main_palette)
        self.setAutoFillBackground(True) # パレット背景の描画を有効にする
        # ↑↑↑ メインウィンドウの背景色をパレットで白に設定 ↑↑↑

        # --- UNDO スタックの作成 ---
        self.undo_stack = QUndoStack(self)

        # --- ウィジェットの作成 ---
        self.cover_widget = CoverPageWidget()
        # ↓↓↓ DetailPageWidget に undo_stack を渡す ↓↓↓
        self.detail_widget = DetailPageWidget(self.undo_stack)

        # --- QStackedWidget の設定 ---
        self.stacked_widget = QStackedWidget()
        # ↓↓↓ StackedWidget の背景色もパレットで白に設定 ↓↓↓
        stack_palette = self.stacked_widget.palette()
        stack_palette.setColor(QPalette.Window, QColor('white'))
        self.stacked_widget.setPalette(stack_palette)
        self.stacked_widget.setAutoFillBackground(True) # パレット背景の描画を有効にする
        # ↑↑↑ StackedWidget の背景色もパレットで白に設定 ↑↑↑
        self.stacked_widget.addWidget(self.cover_widget)  # Index 0: 表紙ページ
        self.stacked_widget.addWidget(self.detail_widget) # Index 1: 明細ページ

        # QStackedWidget をセントラルウィジェットに設定
        self.setCentralWidget(self.stacked_widget)

        # --- アクションとメニューの作成 ---
        self._create_actions()
        self._create_menus()
        # --- ツールバーの作成 ---
        self._create_toolbars()

        # --- ステータスバーの作成 ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("color: black;") # ステータスバーの文字色を黒に設定

        # --- シグナルとスロットの接続 ---
        self.cover_widget.details_requested.connect(self.show_detail_page)
        self.detail_widget.cover_requested.connect(self.show_cover_page)
        self.stacked_widget.currentChanged.connect(self._update_action_states) # ページ切り替え時にアクション状態を更新
        # ↓↓↓ UNDO/REDO スタックの変更時に明細合計を更新するよう接続 ↓↓↓
        self.undo_stack.indexChanged.connect(self.detail_widget._update_detail_totals)

        # ↓↓↓ DetailPageWidget からのステータスメッセージ要求を接続 ↓↓↓
        self.detail_widget.status_message_requested.connect(self.show_status_message)
        # ↓↓↓ DetailPageWidget からの画面フラッシュ要求を接続 ↓↓↓
        self.detail_widget.screen_flash_requested.connect(self.flash_screen)
        # --- 初期表示 ---
        self.show_cover_page() # 最初に表紙を表示

        # --- ウィンドウサイズの調整 ---
        self.resize(900, 780) # 初期サイズ (必要なら調整)
        # 画面サイズは QStackedWidget が中身に合わせてくれるので、
        # 個々のウィジェットのサイズが適切なら自動調整に任せても良い

    def _create_actions(self):
        """UNDO/REDO 用のアクションを作成する"""
        # --- UNDO アクション ---
        self.undo_action = self.undo_stack.createUndoAction(self, "元に戻す")
        self.undo_action.setShortcut(QKeySequence.Undo) # 標準ショートカット (Ctrl+Z)
        self.undo_action.setIcon(QIcon(os.path.join(icon_dir, "undo.png"))) # icon フォルダ内の画像を指定
        self.undo_action.setToolTip("直前の操作を元に戻します")

        # --- REDO アクション ---
        self.redo_action = self.undo_stack.createRedoAction(self, "やり直し")
        self.redo_action.setShortcut(QKeySequence.Redo) # 標準ショートカット (Ctrl+Y or Ctrl+Shift+Z)
        self.redo_action.setIcon(QIcon(os.path.join(icon_dir, "redo.png"))) # icon フォルダ内の画像を指定
        self.redo_action.setToolTip("元に戻した操作をやり直します")

        # --- 明細ページ用アクション ---
        # (アイコンは後で設定可能)
        self.add_row_action = QAction("行追加", self)
        self.add_row_action.setIcon(QIcon(os.path.join(icon_dir, "add_row.png"))) # icon フォルダ内の画像を指定
        self.add_row_action.setToolTip("明細に行を追加します")
        self.add_row_action.triggered.connect(self._add_detail_row)
        self.add_row_action.setEnabled(False) # 初期状態は無効

        self.remove_row_action = QAction("行削除", self)
        self.remove_row_action.setIcon(QIcon(os.path.join(icon_dir, "remove_row.png"))) # icon フォルダ内の画像を指定
        self.remove_row_action.setToolTip("選択した明細行を削除します")
        self.remove_row_action.triggered.connect(self._remove_detail_row)
        self.remove_row_action.setEnabled(False) # 初期状態は無効

        self.duplicate_row_action = QAction("複写", self)
        self.duplicate_row_action.setIcon(QIcon(os.path.join(icon_dir, "duplicate_row.png"))) # icon フォルダ内の画像を指定
        self.duplicate_row_action.setToolTip("選択した明細行を複製します")
        self.duplicate_row_action.triggered.connect(self._duplicate_detail_row)
        #self.redo_action.setToolTip("元に戻した操作をやり直します")
        self.duplicate_row_action.setEnabled(False) # 初期状態は無効

        # --- ページ切り替えアクション ---
        # ... (コメント部分は省略) ...
        self.go_to_detail_action = QAction("明細編集へ", self)
        self.go_to_detail_action.setToolTip("明細編集画面に移動します")
        self.go_to_detail_action.setIcon(QIcon(os.path.join(icon_dir, "go_to_detail.png"))) # icon フォルダ内の画像を指定
        self.go_to_detail_action.triggered.connect(self.show_detail_page)

        # self.go_to_cover_action.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowLeft)) # UNDO と被る
        self.go_to_cover_action = QAction("表紙へ戻る", self)
        self.go_to_cover_action.setToolTip("表紙画面に戻ります")
        self.go_to_cover_action.setIcon(QIcon(os.path.join(icon_dir, "go_to_cover.png"))) # icon フォルダ内の画像を指定
        self.go_to_cover_action.triggered.connect(self.show_cover_page)

    def _create_menus(self):
        """メニューバーを作成する"""
        menu_bar = self.menuBar()

        # --- 編集メニュー (ツールバーに移動したので削除) ---
        # edit_menu = menu_bar.addMenu("編集(&E)")
        # edit_menu.addAction(self.undo_action)
        # edit_menu.addAction(self.redo_action)

        # 他のメニュー (ファイルなど) も必要に応じて追加
        # file_menu = menu_bar.addMenu("ファイル(&F)")
        # ...

    def _create_toolbars(self):
        """ツールバーを作成する"""
        # ツールバーを一つ作成し、中身は _update_action_states で動的に変更する
        # アクションは最初に追加しておき、表示/非表示を切り替える
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
        # 初期状態のツールバーを設定 (例: 表紙画面用)
        self._update_action_states(0) # 初期ページ(表紙)のインデックスを渡す

    @Slot() # PySide6 では Slot デコレータを推奨
    def show_cover_page(self):
        """表紙ページを表示する"""
        # 明細ページから合計金額を取得して表紙に設定
        if self.stacked_widget.currentIndex() == 1: # 現在明細ページが表示されている場合
            subtotal = self.detail_widget.get_current_subtotal()
            tax = self.detail_widget.get_current_tax()
            total = self.detail_widget.get_current_total()
            self.cover_widget.set_totals(subtotal, tax, total)

        self.stacked_widget.setCurrentIndex(0)
        # 表紙に戻るときにウィンドウサイズを調整したい場合はここで行う
        # self.resize(self.cover_widget.sizeHint()) # 例

    @Slot()
    def show_detail_page(self):
        """明細ページを表示する"""
        # データを表紙ウィジェットから取得
        project_name = self.cover_widget.get_project_name()
        client_name = self.cover_widget.get_client_name()
        period_text = self.cover_widget.get_period_text() # 工期テキストを取得
        total = self.cover_widget.get_total()
        subtotal = self.cover_widget.get_subtotal()
        tax = self.cover_widget.get_tax()

        # 明細ウィジェットのヘッダーを更新 (工期テキストを渡す)
        self.detail_widget.update_header(
            project_name, client_name, period_text, total, subtotal, tax # period_text を追加
        )

        self.stacked_widget.setCurrentIndex(1)
        # 明細表示時にウィンドウサイズを調整したい場合はここで行う
        # self.resize(self.detail_widget.sizeHint()) # 例

    @Slot(int)
    def _update_action_states(self, index: int):
        """現在のページに応じてアクションの有効/無効を切り替える"""
        # ツールバーの内容はクリアせず、アクションの表示/非表示と有効/無効を切り替える
        is_detail_page = index == 1

        # UNDO/REDO は常に表示 (有効/無効は QUndoStack が制御)

        # 明細操作アクション
        self.add_row_action.setVisible(is_detail_page)
        self.remove_row_action.setVisible(is_detail_page)
        self.duplicate_row_action.setVisible(is_detail_page)
        # 有効/無効も設定 (明細ページ表示時のみ有効)
        self.add_row_action.setEnabled(is_detail_page)
        self.remove_row_action.setEnabled(is_detail_page)
        self.duplicate_row_action.setEnabled(is_detail_page)

        # ページ移動アクション
        self.go_to_detail_action.setVisible(not is_detail_page)
        self.go_to_cover_action.setVisible(is_detail_page)

    # --- アクションに対応するスロット ---
    @Slot()
    def _add_detail_row(self):
        """明細ページで行追加を実行"""
        if self.stacked_widget.currentWidget() == self.detail_widget:
            self.detail_widget.add_row()

    @Slot()
    def _remove_detail_row(self):
        """明細ページで行削除を実行"""
        if self.stacked_widget.currentWidget() == self.detail_widget:
            self.detail_widget.remove_row()

    @Slot()
    def _duplicate_detail_row(self):
        """明細ページで行複写を実行"""
        if self.stacked_widget.currentWidget() == self.detail_widget:
            self.detail_widget.duplicate_row()

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = 5000):
        """ステータスバーにメッセージを表示する (デフォルト5秒で消える)"""
        self.status_bar.showMessage(message, timeout)

    @Slot()
    def flash_screen(self):
        """画面を一瞬赤くフラッシュさせる"""
        original_style = self.styleSheet() # 現在のスタイルシートを保持
        flash_duration = 100 # フラッシュ（赤色表示）の時間 (ミリ秒)
        restore_delay = flash_duration + 50 # 元に戻すまでの時間 (ミリ秒)

        # 一瞬赤くするスタイル (ウィンドウ背景のみ変更)
        # QMainWindow に直接スタイルを適用すると他の要素に影響する場合があるので注意
        # 代わりに、セントラルウィジェット (QStackedWidget) の親 (MainWindow自身) の
        # 'window' ロールに対するパレットを変更する方が安全かもしれないが、
        # 今回はスタイルシートで試す
        flash_style = original_style + "\nQMainWindow { background-color: pink !important; }" # !important で優先度を上げる (念のため)

        self.setStyleSheet(flash_style)

        # 少し遅れて元のスタイルに戻す
        # QTimer.singleShot(restore_delay, lambda: self.setStyleSheet(original_style)) # 元のスタイルに戻すだけだと不十分な場合がある
        QTimer.singleShot(restore_delay, lambda: self.setStyleSheet(original_style.replace("\nQMainWindow { background-color: pink !important; }", ""))) # フラッシュ用スタイル定義を削除

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont(APP_FONT_FAMILY, APP_FONT_SIZE))
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())