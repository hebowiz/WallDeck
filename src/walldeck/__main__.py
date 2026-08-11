"""WallDeck application entry point and platform diagnostics."""

from __future__ import annotations

import argparse
from datetime import datetime

from walldeck.virtual_desktops import (
    VirtualDesktopSnapshot,
    read_virtual_desktop_snapshot,
    watch_virtual_desktops,
)
from walldeck.wallpaper import read_wallpaper_snapshot


def _print_virtual_desktops(snapshot: VirtualDesktopSnapshot) -> None:
    print("Virtual desktops:")
    for desktop in snapshot.desktops:
        marker = "*" if desktop.desktop_id == snapshot.current_id else " "
        print(f"  {marker} {desktop.name}: {desktop.desktop_id}")
        print(f"      OS wallpaper: {desktop.wallpaper_path or '<not set>'}")


def _print_snapshot() -> None:
    desktops = read_virtual_desktop_snapshot()
    wallpaper = read_wallpaper_snapshot()
    _print_virtual_desktops(desktops)
    print(f"Wallpaper position: {wallpaper.position.name}")
    print("Monitors:")
    for monitor in wallpaper.monitors:
        state = "attached" if monitor.attached else "detached"
        print(f"  [{monitor.index}] {state}: {monitor.device_path}")
        if monitor.attached:
            print(f"      Name: {monitor.friendly_name or monitor.display_name}")
            print(
                f"      {monitor.width}x{monitor.height} "
                f"at ({monitor.left}, {monitor.top})"
            )
        print(f"      Wallpaper: {monitor.wallpaper_path or '<not set>'}")


def main() -> int:
    """Run the WallDeck read-only platform probe."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--probe",
        action="store_true",
        help="print a read-only platform snapshot and exit",
    )
    mode.add_argument(
        "--watch",
        action="store_true",
        help="watch virtual desktop registry changes until Ctrl+C",
    )
    args = parser.parse_args()

    if not args.probe and not args.watch:
        from walldeck.app import run_app

        return run_app()

    _print_snapshot()
    if args.probe:
        return 0

    print("Watching virtual desktop changes. Press Ctrl+C to stop.")
    try:
        for snapshot in watch_virtual_desktops():
            print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Desktop change")
            _print_virtual_desktops(snapshot)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
