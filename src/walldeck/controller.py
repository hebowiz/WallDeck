"""Runtime coordination for desktop monitoring and wallpaper application."""

from __future__ import annotations

from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread

import comtypes
from PySide6.QtCore import QObject, QTimer, Signal

from walldeck.config import ConfigRepository
from walldeck.virtual_desktops import (
    VirtualDesktopSnapshot,
    read_virtual_desktop_snapshot,
    watch_virtual_desktops,
)
from walldeck.wallpaper import (
    WallpaperPosition,
    apply_wallpaper_profile,
    read_wallpaper_snapshot,
)


class RuntimeController(QObject):
    desktop_state_changed = Signal(object)
    profile_changed = Signal()
    status_changed = Signal(str)
    error_occurred = Signal(str)
    paused_changed = Signal(bool)

    def __init__(self, repository: ConfigRepository) -> None:
        super().__init__()
        self.repository = repository
        self._stop_event = Event()
        self._watch_thread: Thread | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="WallDeckWallpaper"
        )
        self._pending_apply: Future[tuple[str | None, int]] | None = None
        self._paused = False
        self._desktop_apply_timer = QTimer(self)
        self._desktop_apply_timer.setSingleShot(True)
        self._desktop_apply_timer.setInterval(200)
        self._desktop_apply_timer.timeout.connect(self.queue_apply)
        self.desktop_state_changed.connect(self._on_desktop_state_changed)

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        if self._watch_thread is not None:
            return
        self._watch_thread = Thread(
            target=self._watch_desktops,
            name="WallDeckDesktopWatcher",
            daemon=True,
        )
        self._watch_thread.start()
        self.queue_apply()

    def stop(self) -> None:
        self._stop_event.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=1.5)
        if self._pending_apply is not None:
            self._pending_apply.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def set_paused(self, paused: bool) -> None:
        if self._paused == paused:
            return
        self._paused = paused
        self.paused_changed.emit(paused)
        self.status_changed.emit("自動適用を一時停止しました" if paused else "自動適用を再開しました")
        if not paused:
            self.queue_apply()

    def set_wallpaper(
        self, desktop_id: str, monitor_id: str, wallpaper_path: str | None
    ) -> None:
        if wallpaper_path is not None and not Path(wallpaper_path).is_file():
            raise FileNotFoundError(wallpaper_path)
        self.repository.update_wallpaper(desktop_id, monitor_id, wallpaper_path)
        self.profile_changed.emit()
        current = read_virtual_desktop_snapshot().current_id
        if current is not None and str(current) == desktop_id:
            self.queue_apply()

    def set_position(self, position: WallpaperPosition) -> None:
        self.repository.update_position(position)
        self.profile_changed.emit()
        self.queue_apply()

    def queue_apply(self) -> None:
        if self._paused:
            return
        if self._pending_apply is not None and not self._pending_apply.running():
            self._pending_apply.cancel()
        future = self._executor.submit(self._apply_latest_profile)
        self._pending_apply = future
        future.add_done_callback(self._apply_finished)

    def _watch_desktops(self) -> None:
        try:
            for snapshot in watch_virtual_desktops(stop_event=self._stop_event):
                self.desktop_state_changed.emit(snapshot)
        except Exception as error:  # surfaced to the GUI, not silently swallowed
            self.error_occurred.emit(f"仮想デスクトップ監視エラー: {error}")

    def _on_desktop_state_changed(self, _snapshot: VirtualDesktopSnapshot) -> None:
        self._desktop_apply_timer.start()

    def _apply_latest_profile(self) -> tuple[str | None, int]:
        comtypes.CoInitialize()
        try:
            desktop_id = read_virtual_desktop_snapshot().current_id
            if desktop_id is None:
                return None, 0
            position, profile = self.repository.profile_for(str(desktop_id))
            attached_ids = {
                monitor.device_path
                for monitor in read_wallpaper_snapshot().monitors
                if monitor.attached
            }
            valid_profile = {
                monitor_id: path
                for monitor_id, path in profile.items()
                if monitor_id in attached_ids and Path(path).is_file()
            }
            if not valid_profile:
                return str(desktop_id), 0
            applied = apply_wallpaper_profile(valid_profile, position)
            return str(desktop_id), applied
        finally:
            comtypes.CoUninitialize()

    def _apply_finished(self, future: Future[tuple[str | None, int]]) -> None:
        try:
            desktop_id, applied = future.result()
        except CancelledError:
            return
        except Exception as error:
            self.error_occurred.emit(f"壁紙の適用に失敗しました: {error}")
            return
        if desktop_id is None:
            self.status_changed.emit("現在の仮想デスクトップを取得できません")
        elif applied == 0:
            self.status_changed.emit("現在のデスクトップに設定済みの壁紙はありません")
        else:
            self.status_changed.emit(f"壁紙を適用しました（{applied}画面）")
