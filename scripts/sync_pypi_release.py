#!/usr/bin/env python3
"""Mirror an existing PyPI release into another package index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_SOURCE_INDEX = "https://pypi.org"
DEFAULT_PACKAGE = "aidev-ai-blueking"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the published files for a PyPI project version and upload "
            "them unchanged to another package index."
        )
    )
    parser.add_argument(
        "--package",
        default=os.environ.get("SYNC_PYPI_PACKAGE") or DEFAULT_PACKAGE,
        help="PyPI package name to mirror. Default: env SYNC_PYPI_PACKAGE or %(default)s",
    )
    parser.add_argument(
        "--version",
        help="Version to mirror. Defaults to the latest stable release from source PyPI.",
    )
    parser.add_argument(
        "--source-index",
        default=os.environ.get("SYNC_PYPI_SOURCE_INDEX") or DEFAULT_SOURCE_INDEX,
        help=(
            "Base URL of the source package index. Default: env "
            "SYNC_PYPI_SOURCE_INDEX or %(default)s"
        ),
    )
    parser.add_argument(
        "--repository-url",
        default=os.environ.get("SYNC_PYPI_REPOSITORY_URL")
        or os.environ.get("TARGET_PYPI_REPOSITORY_URL"),
        help=(
            "Upload URL for your package index. Can also be set with "
            "SYNC_PYPI_REPOSITORY_URL or TARGET_PYPI_REPOSITORY_URL."
        ),
    )
    parser.add_argument(
        "--download-dir",
        default=os.environ.get("SYNC_PYPI_DOWNLOAD_DIR"),
        help=(
            "Directory to store downloaded artifacts. Defaults to env "
            "SYNC_PYPI_DOWNLOAD_DIR or a temporary directory."
        ),
    )
    parser.add_argument(
        "--print-latest",
        action="store_true",
        default=env_flag("SYNC_PYPI_PRINT_LATEST", False),
        help="Print the resolved latest version and exit without downloading or uploading.",
    )
    parser.add_argument(
        "--latest-uploaded",
        action="store_true",
        default=env_flag("SYNC_PYPI_LATEST_UPLOADED", True),
        help=(
            "Resolve the latest uploaded release by file upload timestamp, including "
            "pre-releases. Default: enabled."
        ),
    )
    return parser.parse_args()


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "llm_e2e-pypi-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read()
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Failed to fetch {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to fetch {url}: {exc.reason}") from exc


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_json_url(base_url: str, package: str) -> str:
    quoted = urllib.parse.quote(package, safe="")
    return f"{normalize_base_url(base_url)}/pypi/{quoted}/json"


def parse_upload_time(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def resolve_latest_uploaded_version(metadata: dict) -> str:
    releases = metadata.get("releases", {})
    latest_version: str | None = None
    latest_time = datetime.min.replace(tzinfo=timezone.utc)

    for version, files in releases.items():
        usable_files = [item for item in files if not item.get("yanked")]
        if not usable_files:
            continue

        version_time = max(
            parse_upload_time(item.get("upload_time_iso_8601")) for item in usable_files
        )
        if version_time > latest_time:
            latest_time = version_time
            latest_version = version

    if not latest_version:
        raise SystemExit("Could not resolve the latest uploaded version from source metadata.")

    return latest_version


def resolve_version(
    metadata: dict, requested_version: str | None, latest_uploaded: bool
) -> str:
    if requested_version:
        return requested_version

    if latest_uploaded:
        return resolve_latest_uploaded_version(metadata)

    latest = metadata.get("info", {}).get("version")
    print(f"sdk version: {latest}")
    if not latest:
        raise SystemExit("Could not resolve the latest version from source metadata.")
    return latest


def ensure_release_files(metadata: dict, version: str) -> list[dict]:
    releases = metadata.get("releases", {})
    files = releases.get(version, [])
    if not files:
        raise SystemExit(f"No files found for version {version}.")

    usable_files = [item for item in files if not item.get("yanked")]
    if not usable_files:
        raise SystemExit(f"All files for version {version} are yanked.")
    return usable_files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "llm_e2e-pypi-sync/1.0"},
    )
    try:
        with urllib.request.urlopen(request) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Failed to download {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to download {url}: {exc.reason}") from exc


def download_release_files(files: list[dict], download_dir: Path) -> list[Path]:
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths: list[Path] = []

    for item in files:
        filename = item["filename"]
        url = item["url"]
        expected_sha256 = item.get("digests", {}).get("sha256")
        destination = download_dir / filename

        print(f"Downloading {filename}...")
        download_file(url, destination)

        if expected_sha256:
            actual_sha256 = sha256_file(destination)
            if actual_sha256 != expected_sha256:
                raise SystemExit(
                    f"SHA256 mismatch for {filename}: expected {expected_sha256}, got {actual_sha256}"
                )

        downloaded_paths.append(destination)

    return downloaded_paths


def run_twine_upload(repository_url: str, files: list[Path]) -> None:
    if not shutil.which("twine"):
        raise SystemExit(
            "twine is not installed or not on PATH. Install it first, for example: "
            "python -m pip install twine"
        )

    username = os.environ.get("TENCENT_PYPI_USER")
    password = os.environ.get("TENCENT_PYPI_TOKEN")
    if not username or not password:
        raise SystemExit(
            "Missing credentials. Set TENCENT_PYPI_USER and TENCENT_PYPI_TOKEN environment variables."
        )

    command = [
        "twine", "upload", "--non-interactive",
        "--repository-url", repository_url,
        "--username", username,
        "--password", password,
    ]
    command.extend(str(path) for path in files)

    env = os.environ.copy()
    env.setdefault("TWINE_NON_INTERACTIVE", "1")

    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"twine upload failed with exit code {exc.returncode}") from exc


def main() -> int:
    args = parse_args()

    metadata = fetch_json(build_json_url(args.source_index, args.package))
    version = resolve_version(metadata, args.version, args.latest_uploaded)

    if args.print_latest:
        print(version)
        return 0

    if not args.repository_url:
        raise SystemExit(
            "Missing upload destination. Set --repository-url or TARGET_PYPI_REPOSITORY_URL."
        )

    release_files = ensure_release_files(metadata, version)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.download_dir:
        download_dir = Path(args.download_dir).resolve()
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="sync_pypi_release_")
        download_dir = Path(temp_dir.name)

    try:
        downloaded = download_release_files(release_files, download_dir)
        print(
            f"Uploading {args.package} {version} to {args.repository_url} "
            f"from {download_dir}..."
        )
        run_twine_upload(args.repository_url, downloaded)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    print(f"Synced {args.package} {version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
