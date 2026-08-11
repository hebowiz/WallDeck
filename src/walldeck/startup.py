"""Per-user Windows startup registration."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import winreg


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "WallDeck"


def startup_command() -> str:
    """Return the command that should be stored in the Windows Run key."""
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        arguments = [str(executable)]
    else:
        pythonw = executable.with_name("pythonw.exe")
        arguments = [str(pythonw if pythonw.is_file() else executable), "-m", "walldeck"]
    return subprocess.list2cmdline(arguments)


def registered_startup_command() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, value_type = winreg.QueryValueEx(key, _VALUE_NAME)
    except OSError:
        return None
    if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return None
    return str(value)


def is_startup_registered() -> bool:
    return registered_startup_command() is not None


def set_startup_enabled(enabled: bool) -> None:
    if enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            _RUN_KEY,
            access=winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key,
                _VALUE_NAME,
                0,
                winreg.REG_SZ,
                startup_command(),
            )
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _RUN_KEY,
            access=winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass


def update_registered_startup_command() -> None:
    """Repair a registered command after the executable has moved."""
    registered = registered_startup_command()
    if registered is not None and registered != startup_command():
        set_startup_enabled(True)
