#!/usr/bin/env python3
"""Prepare the repository's cookiecutter project for local source debugging."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PROJECT = REPOSITORY_ROOT / "template" / "builtin" / "{{cookiecutter.project_name}}"
SOURCE_LINKS = {
    "aidev_agent": REPOSITORY_ROOT / "src" / "agent" / "aidev_agent",
    "aidev_bkplugin": REPOSITORY_ROOT / "src" / "plugins" / "aidev_bkplugin" / "aidev_bkplugin",
}


def ensure_source_link(name: str, source: Path) -> None:
    destination = TEMPLATE_PROJECT / name
    if not source.is_dir():
        raise RuntimeError(f"source package does not exist: {source}")

    if os.path.lexists(destination):
        if not destination.is_symlink():
            raise RuntimeError(f"refusing to replace non-symlink path: {destination}")

        current_source = (destination.parent / os.readlink(destination)).resolve()
        if current_source != source.resolve():
            print(f"Replacing source link: {destination} -> {os.readlink(destination)}")
            destination.unlink()
        else:
            print(f"Source link already exists: {destination} -> {os.readlink(destination)}")
            return

    relative_source = os.path.relpath(source, start=destination.parent)
    destination.symlink_to(relative_source, target_is_directory=True)
    print(f"Created source link: {destination} -> {relative_source}")


def prepare_env_file(env_file: str) -> None:
    destination = TEMPLATE_PROJECT / ".env"
    if not env_file:
        if not destination.is_file():
            raise RuntimeError(f"environment file not found: {destination}; pass env_file=/path/to/.env")
        print(f"Using existing environment file: {destination}")
        return

    source = Path(env_file).expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"environment file does not exist: {source}")
    if destination.is_file() and destination.resolve() == source:
        print(f"Using existing environment file: {destination}")
        return

    shutil.copy2(source, destination)
    print(f"Copied environment file to: {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default="",
        help="optional .env file to copy into the template project; defaults to its existing .env",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        prepare_env_file(args.env_file)
        for name, source in SOURCE_LINKS.items():
            ensure_source_link(name, source)
    except (OSError, RuntimeError) as error:
        print(f"Template debug preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
