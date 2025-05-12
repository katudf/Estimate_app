# widgets.py

import os
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QLabel, QDateEdit, QVBoxLayout,
    QHBoxLayout, QCheckBox
)
from PySide6.QtCore import QDate, Qt, QPoint
from PySide6.QtGui import QPixmap, QMouseEvent, QPainter, QPen

# 定数を constants モジュールからインポート
from constants import COLOR_WHITE, COLOR_LIGHT_GRAY, HANKO_IMAGE_PATH # <- 定数名を修正
# -----------------------------------------------------------------------------
# Notion 風「工期」入力専用ウィジェット
# -----------------------------------------------------------------------------
class ConstructionPeriodWidget(QWidget):
    """Notion ライクに単日 / 期間を切り替えられる工期入力フィールド"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._toggle_end_date(False)  # 初期状態（単日モード）

    def _setup_ui(self):
        """UI要素の作成と配置"""
        self.start_edit = QDateEdit(QDate.currentDate())
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy/M/d")
        self.start_edit.setFixedHeight(22)

        self.arrow = QLabel("～")
        self.arrow.setAlignment(Qt.AlignCenter)

        self.end_edit = QDateEdit(self.start_edit.date().addDays(1))
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy/M/d")
        self.end_edit.setFixedHeight(22)

        self.end_toggle = QCheckBox()
        self.end_toggle.setFixedHeight(22)
        # チェックボックスインジケータのスタイルは親ウィジェットのスタイルシートで設定される想定

        self.end_label = QLabel("終了日")
        self.end_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.end_label.setFixedHeight(22)

        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        line.addWidget(self.start_edit)
        line.addWidget(self.arrow)
        line.addWidget(self.end_edit)
        line.addWidget(self.end_toggle)
        line.addWidget(self.end_label)
        line.addStretch(3)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(line)

    def _connect_signals(self):
        """シグナルとスロットの接続"""
        self.end_toggle.toggled.connect(self._toggle_end_date)

    def period_text(self) -> str:
        """現在入力されている期間を文字列で返す (表示用)"""
        if not self.start_edit.date().isValid():
            return ""
        start_txt = self.start_edit.date().toString("yyyy年M月d日")
        if self.end_toggle.isChecked() and self.end_edit.date().isValid():
            end_txt = self.end_edit.date().toString("yyyy年M月d日")
            return f"{start_txt} ～ {end_txt}"
        return start_txt

    def _toggle_end_date(self, show: bool):
        """終了日の表示/非表示と有効/無効を切り替える"""
        self.end_edit.setVisible(show)
        self.arrow.setVisible(show)
        self.end_edit.setEnabled(show)
        # チェックボックス自体のスタイル変更は、必要なら親ウィジェット側で行う

    # 必要に応じて値を取得/設定するメソッドを追加
    def get_start_date(self) -> QDate:
        return self.start_edit.date()

    def set_start_date(self, date: QDate):
        self.start_edit.setDate(date)

    def get_end_date(self) -> QDate | None:
        if self.end_toggle.isChecked():
            return self.end_edit.date()
        return None

    def set_end_date(self, date: QDate | None):
        if date:
            self.end_edit.setDate(date)
            self.end_toggle.setChecked(True)
        else:
            self.end_toggle.setChecked(False)


# -----------------------------------------------------------------------------
# ドラッグ可能な印影ラベル
# -----------------------------------------------------------------------------
class DraggableLabel(QLabel):
    """マウスドラッグで移動可能な QLabel"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # マウスイベントを受け取る
        self._dragging = False
        self._drag_start_pos = QPoint()
        self._load_pixmap() # 画像読み込み

    def _load_pixmap(self):
        """印影画像を読み込む"""
        hanko_path = HANKO_IMAGE_PATH
        if os.path.exists(hanko_path):
            try:
                pixmap = QPixmap(hanko_path)
                if not pixmap.isNull():
                    # print("印影画像が正常に読み込まれました") # デバッグ削除
                    self.setFixedSize(130, 70)  # 描画領域のサイズ
                    self.setPixmap(pixmap.scaled(
                        self.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    ))
                else:
                    print(f"警告: 画像 '{hanko_path}' の読み込みに失敗しました。無効な画像です。")
                    self.setText("[印]")
            except Exception as e:
                print(f"エラー: 画像 '{hanko_path}' の読み込み中にエラー発生: {e}")
                self.setText("[印]")
        else:
            print(f"警告: 画像ファイルが見つかりません: '{hanko_path}'.")
            self.setText("[印]")

    #印影欄確認用 枠描写 (デバッグ用、不要なら削除)
    def paintEvent(self, event):
        super().paintEvent(event) # 元の描画処理を呼ぶ
        # painter = QPainter(self) # デバッグ用の枠線描画は削除
        # pen = QPen(Qt.black, 1)
        # painter.setPen(pen)
        # painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            # グローバル座標ではなく、ラベルの親ウィジェットからの相対位置で計算
            self._drag_start_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and event.buttons() & Qt.LeftButton:
            # 現在のマウス位置(ラベルの親基準)から、ドラッグ開始時のマウス位置(ラベル内基準)を引く
            self.move(self.mapToParent(event.position().toPoint() - self._drag_start_pos))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # print(f"印影ラベルの最終位置: {self.pos()}") # デバッグ削除
            event.accept()