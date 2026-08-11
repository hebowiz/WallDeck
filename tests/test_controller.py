from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from PySide6.QtCore import QCoreApplication

from walldeck.config import ConfigRepository
from walldeck.controller import RuntimeController
from walldeck.virtual_desktops import VirtualDesktopSnapshot
from walldeck.wallpaper import (
    MonitorWallpaper,
    WallpaperPosition,
    WallpaperSnapshot,
)


class RuntimeControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_applies_current_profile_to_attached_monitor(self) -> None:
        desktop_id = uuid.uuid4()
        monitor_id = "monitor-id"
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            wallpaper = directory_path / "wallpaper.jpg"
            wallpaper.touch()
            repository = ConfigRepository(directory_path / "config.json")
            repository.update_position(WallpaperPosition.FIT)
            repository.update_wallpaper(
                str(desktop_id), monitor_id, str(wallpaper)
            )
            controller = RuntimeController(repository)
            desktop_snapshot = VirtualDesktopSnapshot(
                current_id=desktop_id, desktops=()
            )
            wallpaper_snapshot = WallpaperSnapshot(
                position=WallpaperPosition.FILL,
                monitors=(
                    MonitorWallpaper(
                        index=0,
                        device_path=monitor_id,
                        wallpaper_path=None,
                        attached=True,
                    ),
                ),
            )

            with (
                patch(
                    "walldeck.controller.read_virtual_desktop_snapshot",
                    return_value=desktop_snapshot,
                ),
                patch(
                    "walldeck.controller.read_wallpaper_snapshot",
                    return_value=wallpaper_snapshot,
                ),
                patch(
                    "walldeck.controller.apply_wallpaper_profile",
                    return_value=1,
                ) as apply_profile,
            ):
                result = controller._apply_latest_profile()

            self.assertEqual((str(desktop_id), 1), result)
            apply_profile.assert_called_once_with(
                {monitor_id: str(wallpaper)}, WallpaperPosition.FIT
            )
            controller.stop()


if __name__ == "__main__":
    unittest.main()
