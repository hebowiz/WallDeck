"""Read and watch the current Windows virtual desktop registry state."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from threading import Event
import uuid
import winreg
from collections.abc import Iterator


_VIRTUAL_DESKTOPS_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops"
)
_DESKTOPS_SUBKEY = _VIRTUAL_DESKTOPS_KEY + r"\Desktops"


@dataclass(frozen=True, slots=True)
class VirtualDesktop:
    desktop_id: uuid.UUID
    name: str
    wallpaper_path: str | None


@dataclass(frozen=True, slots=True)
class VirtualDesktopSnapshot:
    current_id: uuid.UUID | None
    desktops: tuple[VirtualDesktop, ...]


def _parse_guid_array(value: bytes) -> tuple[uuid.UUID, ...]:
    if len(value) % 16:
        raise ValueError("VirtualDesktopIDs has an invalid byte length")
    return tuple(
        uuid.UUID(bytes_le=value[offset : offset + 16])
        for offset in range(0, len(value), 16)
    )


def _read_binary_value(path: str, name: str) -> bytes | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, value_type = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    if value_type != winreg.REG_BINARY:
        raise ValueError(f"{name} is not a REG_BINARY value")
    return bytes(value)


def _current_desktop_id() -> uuid.UUID | None:
    raw = _read_binary_value(_VIRTUAL_DESKTOPS_KEY, "CurrentVirtualDesktop")
    if raw is None:
        session_id = wintypes.DWORD()
        process_id_to_session_id = ctypes.windll.kernel32.ProcessIdToSessionId
        if process_id_to_session_id(os.getpid(), ctypes.byref(session_id)):
            session_path = (
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\SessionInfo"
                rf"\{session_id.value}\VirtualDesktops"
            )
            raw = _read_binary_value(session_path, "CurrentVirtualDesktop")
    if raw is None:
        return None
    if len(raw) != 16:
        raise ValueError("CurrentVirtualDesktop has an invalid byte length")
    return uuid.UUID(bytes_le=raw)


def _read_optional_string(path: str, name: str) -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, value_type = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return None
    return str(value) or None


def read_virtual_desktop_snapshot() -> VirtualDesktopSnapshot:
    """Read only desktops listed in the active VirtualDesktopIDs value."""
    raw_ids = _read_binary_value(_VIRTUAL_DESKTOPS_KEY, "VirtualDesktopIDs") or b""
    desktop_ids = _parse_guid_array(raw_ids)
    current_id = _current_desktop_id()
    if current_id is None and desktop_ids:
        current_id = desktop_ids[0]

    desktops: list[VirtualDesktop] = []
    for index, desktop_id in enumerate(desktop_ids, start=1):
        desktop_key = _DESKTOPS_SUBKEY + rf"\{{{str(desktop_id).upper()}}}"
        desktops.append(
            VirtualDesktop(
                desktop_id=desktop_id,
                name=_read_optional_string(desktop_key, "Name")
                or f"Desktop {index}",
                wallpaper_path=_read_optional_string(desktop_key, "Wallpaper"),
            )
        )
    return VirtualDesktopSnapshot(current_id=current_id, desktops=tuple(desktops))


def watch_virtual_desktops(
    *, timeout_ms: int = 500, stop_event: Event | None = None
) -> Iterator[VirtualDesktopSnapshot]:
    """Yield a snapshot whenever the virtual desktop registry state changes."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    reg_notify = advapi32.RegNotifyChangeKeyValue
    reg_notify.argtypes = (
        wintypes.HANDLE,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.HANDLE,
        wintypes.BOOL,
    )
    reg_notify.restype = wintypes.LONG

    create_event = kernel32.CreateEventW
    create_event.argtypes = (
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    create_event.restype = wintypes.HANDLE

    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait_for_single_object.restype = wintypes.DWORD

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    event = create_event(None, False, False, None)
    if not event:
        raise ctypes.WinError(ctypes.get_last_error())

    notify_filter = winreg.REG_NOTIFY_CHANGE_NAME | winreg.REG_NOTIFY_CHANGE_LAST_SET
    wait_object_0 = 0
    wait_timeout = 258
    previous = read_virtual_desktop_snapshot()

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _VIRTUAL_DESKTOPS_KEY
        ) as key:
            while True:
                result = reg_notify(key.handle, True, notify_filter, event, True)
                if result:
                    raise ctypes.WinError(result)

                while True:
                    wait_result = wait_for_single_object(event, timeout_ms)
                    if wait_result == wait_timeout:
                        if stop_event is not None and stop_event.is_set():
                            return
                        continue
                    if wait_result != wait_object_0:
                        raise ctypes.WinError(ctypes.get_last_error())
                    break

                current = read_virtual_desktop_snapshot()
                if current != previous:
                    previous = current
                    yield current
    finally:
        close_handle(event)
