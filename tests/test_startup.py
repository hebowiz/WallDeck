from pathlib import Path
import unittest
from unittest.mock import patch

from walldeck import startup


class StartupTests(unittest.TestCase):
    def test_source_command_uses_pythonw_module_launch(self) -> None:
        executable = Path(r"C:\WallDeck\.venv\Scripts\python.exe")
        with (
            patch.object(startup.sys, "executable", str(executable)),
            patch.object(startup.sys, "frozen", False, create=True),
            patch.object(Path, "is_file", return_value=True),
        ):
            command = startup.startup_command()

        self.assertIn("pythonw.exe", command)
        self.assertTrue(command.endswith("-m walldeck"))

    def test_enabling_writes_current_command(self) -> None:
        with (
            patch.object(startup, "startup_command", return_value="WallDeck.exe"),
            patch.object(startup.winreg, "CreateKeyEx") as create_key,
            patch.object(startup.winreg, "SetValueEx") as set_value,
        ):
            startup.set_startup_enabled(True)

        key = create_key.return_value.__enter__.return_value
        set_value.assert_called_once_with(
            key,
            "WallDeck",
            0,
            startup.winreg.REG_SZ,
            "WallDeck.exe",
        )

    def test_disabling_deletes_wall_deck_value(self) -> None:
        with (
            patch.object(startup.winreg, "OpenKey") as open_key,
            patch.object(startup.winreg, "DeleteValue") as delete_value,
        ):
            startup.set_startup_enabled(False)

        key = open_key.return_value.__enter__.return_value
        delete_value.assert_called_once_with(key, "WallDeck")


if __name__ == "__main__":
    unittest.main()
