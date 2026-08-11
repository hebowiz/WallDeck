from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from walldeck.config import ConfigRepository
from walldeck.wallpaper import WallpaperPosition


class ConfigRepositoryTests(unittest.TestCase):
    def test_round_trip_profile_and_position(self) -> None:
        with TemporaryDirectory() as directory:
            repository = ConfigRepository(Path(directory) / "config.json")
            repository.update_position(WallpaperPosition.FIT)
            repository.update_wallpaper("desktop", "monitor", r"C:\wallpaper.jpg")

            restored = ConfigRepository(repository.path).load()

            self.assertEqual(WallpaperPosition.FIT, restored.position)
            self.assertEqual(
                r"C:\wallpaper.jpg",
                restored.wallpaper_for("desktop", "monitor"),
            )

    def test_removing_last_wallpaper_removes_empty_profile(self) -> None:
        with TemporaryDirectory() as directory:
            repository = ConfigRepository(Path(directory) / "config.json")
            repository.update_wallpaper("desktop", "monitor", "wallpaper.jpg")
            repository.update_wallpaper("desktop", "monitor", None)

            self.assertEqual({}, repository.load().profiles)


if __name__ == "__main__":
    unittest.main()
