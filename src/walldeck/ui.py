"""PySide6 user interface for WallDeck."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from walldeck.config import ConfigRepository
from walldeck.controller import RuntimeController
from walldeck.startup import (
    is_startup_registered,
    set_startup_enabled,
    startup_command,
)
from walldeck.virtual_desktops import read_virtual_desktop_snapshot
from walldeck.wallpaper import (
    MonitorWallpaper,
    WallpaperPosition,
    read_wallpaper_snapshot,
)


_ROLE_KIND = int(Qt.ItemDataRole.UserRole)
_ROLE_DESKTOP = _ROLE_KIND + 1
_ROLE_MONITOR = _ROLE_KIND + 2


class MainWindow(QMainWindow):
    def __init__(
        self, controller: RuntimeController, repository: ConfigRepository
    ) -> None:
        super().__init__()
        self.controller = controller
        self.repository = repository
        self.allow_close = False
        self._monitors: dict[str, MonitorWallpaper] = {}
        self._monitor_fingerprint: tuple[tuple[object, ...], ...] = ()

        self.setWindowTitle("WallDeck")
        self.resize(980, 620)
        self.setMinimumSize(760, 480)
        self._build_ui()

        controller.desktop_state_changed.connect(lambda _state: self.refresh())
        controller.profile_changed.connect(self._update_editor)
        controller.status_changed.connect(self.statusBar().showMessage)
        controller.error_occurred.connect(self._show_error)
        self.refresh()
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(5_000)
        self._monitor_timer.timeout.connect(self._refresh_if_monitors_changed)
        self._monitor_timer.start()

    def _build_ui(self) -> None:
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["デスクトップ / モニター", "情報"])
        self.tree.setColumnWidth(0, 270)
        self.tree.currentItemChanged.connect(self._update_editor)

        self.title_label = QLabel("モニターを選択してください")
        title_font = self.title_label.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.preview = QLabel("プレビュー")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(320, 200)
        self.preview.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); background: palette(base); }"
        )

        self.info_label = QLabel("番号、名称、解像度")
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)

        self.choose_button = QPushButton("画像を選択…")
        self.choose_button.clicked.connect(self._choose_wallpaper)
        self.clear_button = QPushButton("設定解除")
        self.clear_button.clicked.connect(self._clear_wallpaper)

        buttons = QHBoxLayout()
        buttons.addWidget(self.choose_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch()

        self.position_combo = QComboBox()
        for position in WallpaperPosition:
            self.position_combo.addItem(position.name.title(), position)
        self.position_combo.currentIndexChanged.connect(self._position_changed)

        self.startup_checkbox = QCheckBox("Windowsログイン時にWallDeckを起動")
        self.startup_checkbox.setChecked(is_startup_registered())
        self.startup_checkbox.setToolTip(startup_command())
        self.startup_checkbox.toggled.connect(self._startup_changed)

        form = QFormLayout()
        form.addRow("モニター情報", self.info_label)
        form.addRow("壁紙", self.path_edit)

        self.refresh_button = QPushButton("再検出")
        self.refresh_button.clicked.connect(self.refresh)
        self.apply_button = QPushButton("現在のデスクトップ設定を再適用")
        self.apply_button.clicked.connect(self.controller.queue_apply)

        common_group = QGroupBox("共通設定・操作")
        common_layout = QHBoxLayout(common_group)
        common_layout.addWidget(QLabel("表示方法"))
        common_layout.addWidget(self.position_combo)
        common_layout.addSpacing(16)
        common_layout.addWidget(self.startup_checkbox)
        common_layout.addStretch()
        common_layout.addWidget(self.refresh_button)
        common_layout.addWidget(self.apply_button)

        editor = QGroupBox("モニター個別設定")
        editor_layout = QVBoxLayout(editor)
        editor_layout.addWidget(self.title_label)
        editor_layout.addWidget(self.preview, 1)
        editor_layout.addLayout(form)
        editor_layout.addLayout(buttons)

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(editor)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(common_group)
        container_layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

    def refresh(self) -> None:
        selection = self._selected_ids()
        try:
            desktops = read_virtual_desktop_snapshot()
            wallpaper = read_wallpaper_snapshot()
        except Exception as error:
            self._show_error(f"システム情報を取得できません: {error}")
            return

        attached = [monitor for monitor in wallpaper.monitors if monitor.attached]
        self._monitors = {monitor.device_path: monitor for monitor in attached}
        self._monitor_fingerprint = self._fingerprint(attached)
        self.tree.clear()
        default_item: QTreeWidgetItem | None = None

        for desktop in desktops.desktops:
            desktop_id = str(desktop.desktop_id)
            current = desktop.desktop_id == desktops.current_id
            label = desktop.name + ("  ● 使用中" if current else "")
            desktop_item = QTreeWidgetItem([label, str(desktop.desktop_id)])
            desktop_item.setData(0, _ROLE_KIND, "desktop")
            desktop_item.setData(0, _ROLE_DESKTOP, desktop_id)
            if current:
                font = desktop_item.font(0)
                font.setBold(True)
                desktop_item.setFont(0, font)
            self.tree.addTopLevelItem(desktop_item)

            for number, monitor in enumerate(attached, start=1):
                name = monitor.friendly_name or monitor.display_name or "Monitor"
                detail = f"{name} / {monitor.width}×{monitor.height}"
                monitor_item = QTreeWidgetItem([f"Monitor {number}", detail])
                monitor_item.setData(0, _ROLE_KIND, "monitor")
                monitor_item.setData(0, _ROLE_DESKTOP, desktop_id)
                monitor_item.setData(0, _ROLE_MONITOR, monitor.device_path)
                desktop_item.addChild(monitor_item)
                if current and number == 1:
                    default_item = monitor_item
                if selection == (desktop_id, monitor.device_path):
                    self.tree.setCurrentItem(monitor_item)
            desktop_item.setExpanded(True)

        config = self.repository.load()
        self.position_combo.blockSignals(True)
        index = self.position_combo.findData(config.position)
        self.position_combo.setCurrentIndex(max(index, 0))
        self.position_combo.blockSignals(False)

        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            if default_item is not None:
                self.tree.setCurrentItem(default_item)
            else:
                first = self.tree.topLevelItem(0)
                if first.childCount():
                    self.tree.setCurrentItem(first.child(0))
        self._update_editor()

    @staticmethod
    def _fingerprint(
        monitors: list[MonitorWallpaper],
    ) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                monitor.device_path,
                monitor.friendly_name,
                monitor.left,
                monitor.top,
                monitor.right,
                monitor.bottom,
            )
            for monitor in monitors
        )

    def _refresh_if_monitors_changed(self) -> None:
        try:
            attached = [
                monitor
                for monitor in read_wallpaper_snapshot().monitors
                if monitor.attached
            ]
        except Exception:
            return
        if self._fingerprint(attached) != self._monitor_fingerprint:
            self.refresh()
            self.controller.queue_apply()

    def _selected_ids(self) -> tuple[str, str] | None:
        item = self.tree.currentItem()
        if item is None or item.data(0, _ROLE_KIND) != "monitor":
            return None
        return (
            str(item.data(0, _ROLE_DESKTOP)),
            str(item.data(0, _ROLE_MONITOR)),
        )

    def _update_editor(self, *_args: object) -> None:
        selected = self._selected_ids()
        enabled = selected is not None
        self.choose_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        if selected is None:
            self.title_label.setText("モニターを選択してください")
            self.info_label.setText("—")
            self.path_edit.clear()
            self.preview.setPixmap(QPixmap())
            self.preview.setText("プレビュー")
            return

        desktop_id, monitor_id = selected
        monitor = self._monitors[monitor_id]
        item = self.tree.currentItem()
        monitor_number = item.text(0) if item else "Monitor"
        name = monitor.friendly_name or monitor.display_name or "Unknown monitor"
        self.title_label.setText(f"{monitor_number} — {name}")
        self.info_label.setText(
            f"{monitor_number} / {name} / {monitor.width}×{monitor.height}"
        )
        path = self.repository.load().wallpaper_for(desktop_id, monitor_id)
        self.path_edit.setText(path or "")
        self._set_preview(path)

    def _set_preview(self, path: str | None) -> None:
        self.preview.setPixmap(QPixmap())
        if not path or not Path(path).is_file():
            self.preview.setText("壁紙未設定")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText("プレビューできません")
            return
        self.preview.setText("")
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _choose_wallpaper(self) -> None:
        selected = self._selected_ids()
        if selected is None:
            return
        current_path = self.path_edit.text()
        start_directory = str(Path(current_path).parent) if current_path else ""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "壁紙を選択",
            start_directory,
            "画像 (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp);;すべてのファイル (*)",
        )
        if not path:
            return
        self.controller.set_wallpaper(*selected, path)
        self._update_editor()

    def _clear_wallpaper(self) -> None:
        selected = self._selected_ids()
        if selected is None:
            return
        self.controller.set_wallpaper(*selected, None)
        self._update_editor()

    def _position_changed(self, index: int) -> None:
        position = self.position_combo.itemData(index)
        if isinstance(position, WallpaperPosition):
            self.controller.set_position(position)

    def _startup_changed(self, enabled: bool) -> None:
        try:
            set_startup_enabled(enabled)
        except OSError as error:
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(is_startup_registered())
            self.startup_checkbox.blockSignals(False)
            self._show_error(f"スタートアップ設定を変更できません: {error}")
            return
        message = (
            "Windowsログイン時の自動起動を有効にしました"
            if enabled
            else "Windowsログイン時の自動起動を無効にしました"
        )
        self.statusBar().showMessage(message)

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "WallDeck", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self.allow_close:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.statusBar().showMessage("WallDeckはタスクトレイで実行中です")
