# C:\Users\katuy\OneDrive\Estimate_app\icon_viewer.py
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QScrollArea, QFrame, QVBoxLayout
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QSize # QSize をインポート
from PySide6.QtWidgets import QStyle # QStyle をインポート

class IconViewer(QWidget):
    """Qt標準アイコンを一覧表示するウィジェット"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Standard Icons Viewer")
        self.resize(800, 600) # ウィンドウの初期サイズ

        # --- スクロール可能なエリアを作成 ---
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True) # 中のウィジェットがリサイズできるようにする
        scroll_area.setStyleSheet("background-color: white;") # スクロールエリアの背景を白に

        # --- アイコンを表示するコンテンツウィジェットとレイアウト ---
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: white;") # コンテンツの背景も白に
        grid_layout = QGridLayout(content_widget)
        grid_layout.setSpacing(15) # アイコン間のスペース
        grid_layout.setContentsMargins(10, 10, 10, 10) # 内側の余白

        # --- 表示する QStyle.StandardPixmap のリスト ---
        # Qt 6 のドキュメントを参考にリストアップ (一部抜粋・整理)
        # https://doc.qt.io/qt-6/qstyle.html#StandardPixmap-enum
        standard_pixmaps = [
            # TitleBar Icons
            QStyle.SP_TitleBarMinButton, QStyle.SP_TitleBarMenuButton, QStyle.SP_TitleBarMaxButton,
            QStyle.SP_TitleBarCloseButton, QStyle.SP_TitleBarNormalButton, QStyle.SP_TitleBarShadeButton,
            QStyle.SP_TitleBarUnshadeButton, QStyle.SP_TitleBarContextHelpButton,
            # Message Box Icons
            QStyle.SP_MessageBoxInformation, QStyle.SP_MessageBoxWarning, QStyle.SP_MessageBoxCritical,
            QStyle.SP_MessageBoxQuestion,
            # Standard Icons
            QStyle.SP_DesktopIcon, QStyle.SP_TrashIcon, QStyle.SP_ComputerIcon, QStyle.SP_DriveFDIcon,
            QStyle.SP_DriveHDIcon, QStyle.SP_DriveCDIcon, QStyle.SP_DriveDVDIcon, QStyle.SP_DriveNetIcon,
            # Directory Icons
            QStyle.SP_DirOpenIcon, QStyle.SP_DirClosedIcon, QStyle.SP_DirLinkIcon, QStyle.SP_DirLinkOpenIcon,
            QStyle.SP_DirIcon,
            # File Icons
            QStyle.SP_FileIcon, QStyle.SP_FileLinkIcon,
            # ToolBar Icons
            QStyle.SP_ToolBarHorizontalExtensionButton, QStyle.SP_ToolBarVerticalExtensionButton,
            # File Dialog Icons
            QStyle.SP_FileDialogStart, QStyle.SP_FileDialogEnd, QStyle.SP_FileDialogToParent,
            QStyle.SP_FileDialogNewFolder, QStyle.SP_FileDialogDetailedView, QStyle.SP_FileDialogInfoView,
            QStyle.SP_FileDialogContentsView, QStyle.SP_FileDialogListView, QStyle.SP_FileDialogBack,
            # Other Icons
            QStyle.SP_DockWidgetCloseButton, QStyle.SP_TabCloseButton,
            # Arrow Icons
            QStyle.SP_ArrowUp, QStyle.SP_ArrowDown, QStyle.SP_ArrowLeft, QStyle.SP_ArrowRight,
            QStyle.SP_ArrowBack, QStyle.SP_ArrowForward,
            # Dialog Button Icons
            QStyle.SP_DialogOkButton, QStyle.SP_DialogCancelButton, QStyle.SP_DialogHelpButton,
            QStyle.SP_DialogOpenButton, QStyle.SP_DialogSaveButton, QStyle.SP_DialogCloseButton,
            QStyle.SP_DialogApplyButton, QStyle.SP_DialogResetButton, QStyle.SP_DialogDiscardButton,
            QStyle.SP_DialogYesButton, QStyle.SP_DialogNoButton, QStyle.SP_DialogNoToAllButton,
            QStyle.SP_DialogSaveAllButton, QStyle.SP_DialogAbortButton, QStyle.SP_DialogRetryButton,
            QStyle.SP_DialogIgnoreButton, QStyle.SP_RestoreDefaultsButton,
            # Media Control Icons
            QStyle.SP_MediaPlay, QStyle.SP_MediaStop, QStyle.SP_MediaPause, QStyle.SP_MediaSkipForward,
            QStyle.SP_MediaSkipBackward, QStyle.SP_MediaSeekForward, QStyle.SP_MediaSeekBackward,
            QStyle.SP_MediaVolume, QStyle.SP_MediaVolumeMuted,
            # Other Input Icons
            QStyle.SP_LineEditClearButton,
        ]
        # 重複を除去 (リストの順序は保持)
        unique_pixmaps = list(dict.fromkeys(standard_pixmaps))

        # --- StandardPixmap の名前を取得するための辞書 ---
        # QStyle.StandardPixmap は enum ではないため、手動でマッピングします
        pixmap_names = {v: k for k, v in QStyle.__dict__.items() if isinstance(v, QStyle.StandardPixmap)}

        row, col = 0, 0
        cols_per_row = 5 # 1行あたりに表示するアイコンの数

        style = QApplication.style() # 現在のスタイルを取得

        for pixmap_enum in unique_pixmaps:
            icon = style.standardIcon(pixmap_enum)
            if not icon.isNull(): # 有効なアイコン（Noneでない）のみ表示
                # --- アイコン表示用ラベル ---
                icon_label = QLabel()
                icon_label.setPixmap(icon.pixmap(32, 32)) # 32x32ピクセルで表示
                icon_label.setAlignment(Qt.AlignCenter)
                icon_label.setToolTip(f"Size: {icon.actualSize(QSize(32, 32)).width()}x{icon.actualSize(QSize(32, 32)).height()}") # 実サイズをツールチップ表示

                # --- アイコン名表示用ラベル ---
                # pixmap_names 辞書から名前を取得、見つからなければ "Unknown"
                name_str = pixmap_names.get(pixmap_enum, "Unknown")
                name_label = QLabel(name_str)
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setWordWrap(True) # 長い名前は折り返す
                name_label.setStyleSheet("color: black;") # 文字色を黒に

                # --- アイコンと名前をまとめるウィジェット ---
                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.addWidget(icon_label)
                item_layout.addWidget(name_label)
                item_layout.setContentsMargins(5, 5, 5, 5) # 内側の余白
                item_layout.setSpacing(2) # アイコンとラベルの間隔

                # --- 見やすくするための枠線付きフレーム ---
                frame = QFrame()
                frame_layout = QVBoxLayout(frame)
                frame_layout.addWidget(item_widget)
                frame_layout.setContentsMargins(0, 0, 0, 0)
                frame.setFrameShape(QFrame.StyledPanel) # パネル風の枠線
                frame.setStyleSheet("background-color: #f0f0f0; border-radius: 3px;") # 背景色と角丸

                # --- グリッドレイアウトに追加 ---
                grid_layout.addWidget(frame, row, col)

                # --- 次の列へ ---
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1

        # --- レイアウトの設定 ---
        content_widget.setLayout(grid_layout) # コンテンツウィジェットにグリッドレイアウトを設定
        scroll_area.setWidget(content_widget) # スクロールエリアにコンテンツウィジェットを設定

        # --- メインウィンドウのレイアウト ---
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area) # メインレイアウトにスクロールエリアを追加
        main_layout.setContentsMargins(0, 0, 0, 0) # ウィンドウ自体の余白をなくす
        self.setLayout(main_layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # アプリケーション全体のフォントを設定（任意）
    # font = QFont("Meiryo UI", 9)
    # app.setFont(font)

    viewer = IconViewer()
    viewer.show()
    sys.exit(app.exec())
