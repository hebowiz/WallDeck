"""Read-only access to the Windows desktop wallpaper COM API."""

from __future__ import annotations

import ctypes
from ctypes import (
    POINTER,
    Structure,
    Union,
    byref,
    c_byte,
    c_int,
    c_long,
    c_uint,
    c_ushort,
    c_void_p,
    c_wchar,
    c_wchar_p,
)
from dataclasses import dataclass
from enum import IntEnum

from comtypes import COMError, COMMETHOD, GUID, HRESULT, IUnknown
from comtypes.client import CreateObject


class _Rect(Structure):
    _fields_ = [
        ("left", c_int),
        ("top", c_int),
        ("right", c_int),
        ("bottom", c_int),
    ]


_LPWSTR = POINTER(c_wchar)


class _MonitorInfoEx(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("rcMonitor", _Rect),
        ("rcWork", _Rect),
        ("dwFlags", c_uint),
        ("szDevice", c_wchar * 32),
    ]


class _DisplayDevice(Structure):
    _fields_ = [
        ("cb", c_uint),
        ("DeviceName", c_wchar * 32),
        ("DeviceString", c_wchar * 128),
        ("StateFlags", c_uint),
        ("DeviceID", c_wchar * 128),
        ("DeviceKey", c_wchar * 128),
    ]


class _Luid(Structure):
    _fields_ = [("low_part", c_uint), ("high_part", c_long)]


class _Rational(Structure):
    _fields_ = [("numerator", c_uint), ("denominator", c_uint)]


class _PathSourceInfo(Structure):
    _fields_ = [
        ("adapter_id", _Luid),
        ("id", c_uint),
        ("mode_info_idx", c_uint),
        ("status_flags", c_uint),
    ]


class _PathTargetInfo(Structure):
    _fields_ = [
        ("adapter_id", _Luid),
        ("id", c_uint),
        ("mode_info_idx", c_uint),
        ("output_technology", c_uint),
        ("rotation", c_uint),
        ("scaling", c_uint),
        ("refresh_rate", _Rational),
        ("scanline_ordering", c_uint),
        ("target_available", c_int),
        ("status_flags", c_uint),
    ]


class _PathInfo(Structure):
    _fields_ = [
        ("source_info", _PathSourceInfo),
        ("target_info", _PathTargetInfo),
        ("flags", c_uint),
    ]


class _ModeInfoData(Union):
    _fields_ = [("raw", c_byte * 48)]


class _ModeInfo(Structure):
    _fields_ = [
        ("info_type", c_uint),
        ("id", c_uint),
        ("adapter_id", _Luid),
        ("data", _ModeInfoData),
    ]


class _DeviceInfoHeader(Structure):
    _fields_ = [
        ("info_type", c_uint),
        ("size", c_uint),
        ("adapter_id", _Luid),
        ("id", c_uint),
    ]


class _SourceDeviceName(Structure):
    _fields_ = [
        ("header", _DeviceInfoHeader),
        ("view_gdi_device_name", c_wchar * 32),
    ]


class _TargetDeviceName(Structure):
    _fields_ = [
        ("header", _DeviceInfoHeader),
        ("flags", c_uint),
        ("output_technology", c_uint),
        ("edid_manufacture_id", c_ushort),
        ("edid_product_code_id", c_ushort),
        ("connector_instance", c_uint),
        ("monitor_friendly_device_name", c_wchar * 64),
        ("monitor_device_path", c_wchar * 128),
    ]


class WallpaperPosition(IntEnum):
    CENTER = 0
    TILE = 1
    STRETCH = 2
    FIT = 3
    FILL = 4
    SPAN = 5


class _IDesktopWallpaper(IUnknown):
    _iid_ = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "SetWallpaper",
            (["in"], c_wchar_p, "monitor_id"),
            (["in"], c_wchar_p, "wallpaper"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetWallpaper",
            (["in"], c_wchar_p, "monitor_id"),
            (["out"], POINTER(_LPWSTR), "wallpaper"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorDevicePathAt",
            (["in"], c_uint, "monitor_index"),
            (["out"], POINTER(_LPWSTR), "monitor_id"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorDevicePathCount",
            (["out"], POINTER(c_uint), "count"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetMonitorRECT",
            (["in"], c_wchar_p, "monitor_id"),
            (["out"], POINTER(_Rect), "display_rect"),
        ),
        COMMETHOD(
            [], HRESULT, "SetBackgroundColor", (["in"], c_uint, "color")
        ),
        COMMETHOD(
            [],
            HRESULT,
            "GetBackgroundColor",
            (["out"], POINTER(c_uint), "color"),
        ),
        COMMETHOD([], HRESULT, "SetPosition", (["in"], c_int, "position")),
        COMMETHOD(
            [],
            HRESULT,
            "GetPosition",
            (["out"], POINTER(c_int), "position"),
        ),
    ]


_CLSID_DESKTOP_WALLPAPER = GUID("{C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD}")
_ole32 = ctypes.OleDLL("ole32")
_ole32.CoTaskMemFree.argtypes = (c_void_p,)
_ole32.CoTaskMemFree.restype = None


def _take_com_string(value: _LPWSTR) -> str:
    if not value:
        return ""
    try:
        return ctypes.wstring_at(value)
    finally:
        _ole32.CoTaskMemFree(value)


@dataclass(frozen=True, slots=True)
class MonitorWallpaper:
    index: int
    device_path: str
    wallpaper_path: str | None
    attached: bool
    friendly_name: str | None = None
    display_name: str | None = None
    left: int | None = None
    top: int | None = None
    right: int | None = None
    bottom: int | None = None

    @property
    def width(self) -> int | None:
        if self.left is None or self.right is None:
            return None
        return self.right - self.left

    @property
    def height(self) -> int | None:
        if self.top is None or self.bottom is None:
            return None
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class WallpaperSnapshot:
    position: WallpaperPosition
    monitors: tuple[MonitorWallpaper, ...]


def _display_names_by_rect() -> dict[tuple[int, int, int, int], tuple[str, str]]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_enum_proc = ctypes.WINFUNCTYPE(
        c_int, c_void_p, c_void_p, POINTER(_Rect), c_long
    )
    result: dict[tuple[int, int, int, int], tuple[str, str]] = {}
    names_by_display = _active_display_names(user32)

    get_monitor_info = user32.GetMonitorInfoW
    get_monitor_info.argtypes = (c_void_p, POINTER(_MonitorInfoEx))
    get_monitor_info.restype = c_int

    enum_display_devices = user32.EnumDisplayDevicesW
    enum_display_devices.argtypes = (
        c_wchar_p,
        c_uint,
        POINTER(_DisplayDevice),
        c_uint,
    )
    enum_display_devices.restype = c_int

    def callback(
        monitor: int, _device_context: int, _rect: POINTER(_Rect), _data: int
    ) -> int:
        info = _MonitorInfoEx()
        info.cbSize = ctypes.sizeof(info)
        if not get_monitor_info(monitor, byref(info)):
            return 1
        display = _DisplayDevice()
        display.cb = ctypes.sizeof(display)
        friendly_name = names_by_display.get(info.szDevice, info.szDevice)
        if enum_display_devices(info.szDevice, 0, byref(display), 1):
            if friendly_name == info.szDevice:
                friendly_name = display.DeviceString or friendly_name
        rect = info.rcMonitor
        result[(rect.left, rect.top, rect.right, rect.bottom)] = (
            friendly_name,
            info.szDevice,
        )
        return 1

    enum_display_monitors = user32.EnumDisplayMonitors
    enum_display_monitors.argtypes = (
        c_void_p,
        POINTER(_Rect),
        monitor_enum_proc,
        c_long,
    )
    enum_display_monitors.restype = c_int
    callback_reference = monitor_enum_proc(callback)
    enum_display_monitors(None, None, callback_reference, 0)
    return result


def _active_display_names(user32: ctypes.WinDLL) -> dict[str, str]:
    """Map GDI display names to EDID friendly names using DisplayConfig."""
    get_buffer_sizes = user32.GetDisplayConfigBufferSizes
    get_buffer_sizes.argtypes = (c_uint, POINTER(c_uint), POINTER(c_uint))
    get_buffer_sizes.restype = c_long

    query_display_config = user32.QueryDisplayConfig
    query_display_config.argtypes = (
        c_uint,
        POINTER(c_uint),
        POINTER(_PathInfo),
        POINTER(c_uint),
        POINTER(_ModeInfo),
        c_void_p,
    )
    query_display_config.restype = c_long

    get_device_info = user32.DisplayConfigGetDeviceInfo
    get_device_info.argtypes = (POINTER(_DeviceInfoHeader),)
    get_device_info.restype = c_long

    only_active_paths = 2
    source_name_type = 1
    target_name_type = 2
    path_count = c_uint()
    mode_count = c_uint()
    if get_buffer_sizes(only_active_paths, byref(path_count), byref(mode_count)):
        return {}

    paths = (_PathInfo * path_count.value)()
    modes = (_ModeInfo * mode_count.value)()
    if query_display_config(
        only_active_paths,
        byref(path_count),
        paths,
        byref(mode_count),
        modes,
        None,
    ):
        return {}

    result: dict[str, str] = {}
    for path in paths[: path_count.value]:
        source = _SourceDeviceName()
        source.header.info_type = source_name_type
        source.header.size = ctypes.sizeof(source)
        source.header.adapter_id = path.source_info.adapter_id
        source.header.id = path.source_info.id

        target = _TargetDeviceName()
        target.header.info_type = target_name_type
        target.header.size = ctypes.sizeof(target)
        target.header.adapter_id = path.target_info.adapter_id
        target.header.id = path.target_info.id

        if get_device_info(byref(source.header)):
            continue
        if get_device_info(byref(target.header)):
            continue
        if target.monitor_friendly_device_name:
            result[source.view_gdi_device_name] = target.monitor_friendly_device_name
    return result


def read_wallpaper_snapshot() -> WallpaperSnapshot:
    """Return the wallpaper state without changing any system settings."""
    api = CreateObject(_CLSID_DESKTOP_WALLPAPER, interface=_IDesktopWallpaper)
    position = WallpaperPosition(api.GetPosition())
    monitors: list[MonitorWallpaper] = []
    display_names = _display_names_by_rect()

    for index in range(api.GetMonitorDevicePathCount()):
        device_path = _take_com_string(api.GetMonitorDevicePathAt(index))
        wallpaper_path = _take_com_string(api.GetWallpaper(device_path)) or None
        try:
            rect = api.GetMonitorRECT(device_path)
        except COMError:
            monitors.append(
                MonitorWallpaper(
                    index=index,
                    device_path=device_path,
                    wallpaper_path=wallpaper_path,
                    attached=False,
                )
            )
            continue

        monitors.append(
            MonitorWallpaper(
                index=index,
                device_path=device_path,
                wallpaper_path=wallpaper_path,
                attached=True,
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
                friendly_name=display_names.get(
                    (rect.left, rect.top, rect.right, rect.bottom), (None, None)
                )[0],
                display_name=display_names.get(
                    (rect.left, rect.top, rect.right, rect.bottom), (None, None)
                )[1],
            )
        )

    return WallpaperSnapshot(position=position, monitors=tuple(monitors))


def apply_wallpaper_profile(
    wallpapers: dict[str, str], position: WallpaperPosition
) -> int:
    """Apply one virtual desktop profile and return the assignment count."""
    api = CreateObject(_CLSID_DESKTOP_WALLPAPER, interface=_IDesktopWallpaper)
    api.SetPosition(int(position))
    for monitor_id, wallpaper_path in wallpapers.items():
        api.SetWallpaper(monitor_id, wallpaper_path)
    return len(wallpapers)
