"""WallDeck GUI application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from walldeck.config import ConfigRepository
from walldeck.controller import RuntimeController
from walldeck.single_instance import SingleInstance
from walldeck.startup import update_registered_startup_command
from walldeck.ui import MainWindow


def run_app() -> int:
    instance = SingleInstance()
    if not instance.is_primary:
        instance.notify_primary()
        instance.close()
        return 0

    try:
        update_registered_startup_command()
    except OSError:
        pass

    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("WallDeck")
    application.setQuitOnLastWindowClosed(False)

    repository = ConfigRepository()
    controller = RuntimeController(repository)
    window = MainWindow(controller, repository)

    icon = application.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
    application.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon, application)
    tray.setToolTip("WallDeck")

    menu = QMenu()
    show_action = QAction("設定を開く", menu)
    show_action.triggered.connect(window.showNormal)
    apply_action = QAction("現在の壁紙を適用", menu)
    apply_action.triggered.connect(controller.queue_apply)
    pause_action = QAction("自動適用を一時停止", menu)
    pause_action.setCheckable(True)
    pause_action.toggled.connect(controller.set_paused)
    exit_action = QAction("終了", menu)

    menu.addAction(show_action)
    menu.addAction(apply_action)
    menu.addAction(pause_action)
    menu.addSeparator()
    menu.addAction(exit_action)
    tray.setContextMenu(menu)

    def show_window(*_args: object) -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def exit_application() -> None:
        window.allow_close = True
        tray.hide()
        application.quit()

    activation_timer = QTimer(application)
    activation_timer.setInterval(150)
    activation_timer.timeout.connect(
        lambda: show_window() if instance.activation_requested() else None
    )
    activation_timer.start()

    tray.activated.connect(
        lambda reason: show_window()
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick
        else None
    )
    exit_action.triggered.connect(exit_application)
    controller.error_occurred.connect(
        lambda message: tray.showMessage(
            "WallDeck", message, QSystemTrayIcon.MessageIcon.Warning
        )
    )
    application.aboutToQuit.connect(controller.stop)
    application.aboutToQuit.connect(instance.close)

    tray.show()
    window.show()
    controller.start()
    return application.exec()
