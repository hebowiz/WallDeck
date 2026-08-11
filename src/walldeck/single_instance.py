"""Windows named-kernel-object based single-instance coordination."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258


class SingleInstance:
    """Own a session-local mutex and receive activation requests."""

    def __init__(self, application_id: str = "WallDeck.v1") -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close_handle = kernel32.CloseHandle
        self._close_handle.argtypes = (wintypes.HANDLE,)
        self._close_handle.restype = wintypes.BOOL

        create_event = kernel32.CreateEventW
        create_event.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        create_event.restype = wintypes.HANDLE

        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        create_mutex.restype = wintypes.HANDLE

        self._set_event = kernel32.SetEvent
        self._set_event.argtypes = (wintypes.HANDLE,)
        self._set_event.restype = wintypes.BOOL

        self._wait_for_single_object = kernel32.WaitForSingleObject
        self._wait_for_single_object.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
        )
        self._wait_for_single_object.restype = wintypes.DWORD

        self._event = create_event(
            None, False, False, rf"Local\{application_id}.Activate"
        )
        if not self._event:
            raise ctypes.WinError(ctypes.get_last_error())

        ctypes.set_last_error(0)
        self._mutex = create_mutex(
            None, False, rf"Local\{application_id}.SingleInstance"
        )
        if not self._mutex:
            error = ctypes.get_last_error()
            self._close_handle(self._event)
            self._event = None
            raise ctypes.WinError(error)
        self.is_primary = ctypes.get_last_error() != _ERROR_ALREADY_EXISTS

    def notify_primary(self) -> None:
        if self._event and not self._set_event(self._event):
            raise ctypes.WinError(ctypes.get_last_error())

    def activation_requested(self) -> bool:
        if not self._event:
            return False
        result = self._wait_for_single_object(self._event, 0)
        if result == _WAIT_OBJECT_0:
            return True
        if result == _WAIT_TIMEOUT:
            return False
        raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._mutex:
            self._close_handle(self._mutex)
            self._mutex = None
        if self._event:
            self._close_handle(self._event)
            self._event = None

    def __enter__(self) -> SingleInstance:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
