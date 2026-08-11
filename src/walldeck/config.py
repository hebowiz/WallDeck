"""Persistent WallDeck configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from walldeck.wallpaper import WallpaperPosition


@dataclass(slots=True)
class WallDeckConfig:
    position: WallpaperPosition = WallpaperPosition.FILL
    profiles: dict[str, dict[str, str]] = field(default_factory=dict)

    def wallpaper_for(self, desktop_id: str, monitor_id: str) -> str | None:
        return self.profiles.get(desktop_id, {}).get(monitor_id)

    def set_wallpaper(
        self, desktop_id: str, monitor_id: str, wallpaper_path: str | None
    ) -> None:
        if wallpaper_path:
            self.profiles.setdefault(desktop_id, {})[monitor_id] = wallpaper_path
            return
        monitors = self.profiles.get(desktop_id)
        if monitors is None:
            return
        monitors.pop(monitor_id, None)
        if not monitors:
            self.profiles.pop(desktop_id, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "position": self.position.name.lower(),
            "profiles": self.profiles,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WallDeckConfig:
        raw_position = str(value.get("position", "fill")).upper()
        try:
            position = WallpaperPosition[raw_position]
        except KeyError:
            position = WallpaperPosition.FILL

        profiles: dict[str, dict[str, str]] = {}
        raw_profiles = value.get("profiles", {})
        if isinstance(raw_profiles, dict):
            for desktop_id, raw_monitors in raw_profiles.items():
                if not isinstance(raw_monitors, dict):
                    continue
                profiles[str(desktop_id)] = {
                    str(monitor_id): str(path)
                    for monitor_id, path in raw_monitors.items()
                    if isinstance(path, str) and path
                }
        return cls(position=position, profiles=profiles)


def default_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "WallDeck" / "config.json"
    return Path.home() / ".walldeck" / "config.json"


class ConfigRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()
        self._lock = RLock()
        self._config: WallDeckConfig | None = None

    def load(self) -> WallDeckConfig:
        with self._lock:
            if self._config is not None:
                return self._config
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                self._config = WallDeckConfig()
            except (OSError, json.JSONDecodeError, TypeError):
                self._config = WallDeckConfig()
            else:
                self._config = (
                    WallDeckConfig.from_dict(raw)
                    if isinstance(raw, dict)
                    else WallDeckConfig()
                )
            return self._config

    def save(self) -> None:
        with self._lock:
            config = self.load()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)

    def profile_for(
        self, desktop_id: str
    ) -> tuple[WallpaperPosition, dict[str, str]]:
        with self._lock:
            config = self.load()
            return config.position, dict(config.profiles.get(desktop_id, {}))

    def update_wallpaper(
        self, desktop_id: str, monitor_id: str, wallpaper_path: str | None
    ) -> None:
        with self._lock:
            self.load().set_wallpaper(desktop_id, monitor_id, wallpaper_path)
            self.save()

    def update_position(self, position: WallpaperPosition) -> None:
        with self._lock:
            self.load().position = position
            self.save()
