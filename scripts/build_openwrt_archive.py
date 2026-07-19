from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENWRT_DIR = REPO_ROOT / "openwrt"
INSTALLER_SRC = OPENWRT_DIR / "install-openwrt-prototype.sh"
README_SRC = OPENWRT_DIR / "README.md"
ARCHIVE_ROOT = "unified-ui-openwrt"
DEFAULT_ARCHIVE_PATH = REPO_ROOT / "unified-ui-openwrt.tar.gz"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build unified-ui-openwrt.tar.gz from the working tree.")
    p.add_argument("--output", default=str(DEFAULT_ARCHIVE_PATH), help="Path to output .tar.gz archive")
    p.add_argument("--sha256", default="", help="Optional path to .sha256 sidecar")
    p.add_argument("--version", default="", help="Optional version override (defaults to git short SHA)")
    p.add_argument("--update-url", default="", help="Optional BUILD.json update_url value")
    return p.parse_args()


def git_short_head(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo_root), text=True, stderr=subprocess.DEVNULL)
        return (out or "").strip() or "local"
    except Exception:
        return "local"


def write_build_json(dst: Path, *, version: str, update_url: str) -> None:
    payload = {
        "version": str(version or "").strip(),
        "release_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "update_url": str(update_url or "").strip(),
    }
    dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_installer_text(src_text: str, *, version: str, update_url: str) -> str:
    exports = (
        f"UNIFIED_OPENWRT_VERSION={shlex_quote(version)}\n"
        f"UNIFIED_OPENWRT_UPDATE_URL={shlex_quote(update_url)}\n"
        f"export UNIFIED_OPENWRT_VERSION UNIFIED_OPENWRT_UPDATE_URL\n"
    )
    return exports + src_text


def shlex_quote(s: str) -> str:
    return "'" + str(s).replace("'", "'\\''") + "'"


def build_archive(src_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        tar.add(src_dir, arcname=ARCHIVE_ROOT)


def write_sha256(archive_path: Path, sha_path: Path) -> str:
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest().lower()
    sha_path.write_text(f"{digest}  {archive_path.name}", encoding="utf-8")
    return digest


def replace_file_with_retries(src: Path, dst: Path, *, attempts: int = 12, delay_s: float = 0.25) -> None:
    last_error: Exception | None = None
    for _ in range(max(1, int(attempts))):
        try:
            if dst.exists():
                dst.unlink()
            os.replace(src, dst)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(max(0.05, float(delay_s)))
    if last_error is not None:
        raise last_error
    os.replace(src, dst)


def derive_fallback_archive_path(path: Path) -> Path:
    name = path.name
    if name.endswith(".tar.gz"):
        return path.with_name(name[:-7] + ".new.tar.gz")
    return path.with_name(path.stem + ".new" + path.suffix)


def main() -> int:
    args = parse_args()
    if not INSTALLER_SRC.is_file():
        print(f"[!] installer not found: {INSTALLER_SRC}", file=sys.stderr)
        return 1
    if not README_SRC.is_file():
        print(f"[!] readme not found: {README_SRC}", file=sys.stderr)
        return 1

    archive_path = Path(args.output).resolve()
    sha_path = Path(args.sha256).resolve() if str(args.sha256 or "").strip() else Path(str(archive_path) + ".sha256")
    version = str(args.version or "").strip() or git_short_head(REPO_ROOT)
    update_url = str(args.update_url or "").strip()

    installer_text = build_installer_text(INSTALLER_SRC.read_text(encoding="utf-8"), version=version, update_url=update_url)

    with tempfile.TemporaryDirectory(prefix="openwrt-package-", dir=str(REPO_ROOT)) as tmp_dir:
        tmp_root = Path(tmp_dir) / ARCHIVE_ROOT
        tmp_root.mkdir(parents=True, exist_ok=True)

        (tmp_root / "install.sh").write_text(installer_text, encoding="utf-8")
        os.chmod(tmp_root / "install.sh", 0o755)
        shutil.copy2(README_SRC, tmp_root / "README.md")
        write_build_json(tmp_root / "BUILD.json", version=version, update_url=update_url)

        fd, temp_archive_raw = tempfile.mkstemp(prefix="unified-ui-openwrt-", suffix=".tar.gz", dir=str(archive_path.parent))
        os.close(fd)
        temp_archive = Path(temp_archive_raw)
        try:
            build_archive(tmp_root, temp_archive)
            try:
                replace_file_with_retries(temp_archive, archive_path)
            except PermissionError:
                fallback = derive_fallback_archive_path(archive_path)
                replace_file_with_retries(temp_archive, fallback)
                archive_path = fallback
                sha_path = Path(str(archive_path) + ".sha256")
                print(f"[!] target archive busy, wrote fallback archive instead: {archive_path}")
        finally:
            try:
                if temp_archive.exists():
                    temp_archive.unlink()
            except Exception:
                pass

    digest = write_sha256(archive_path, sha_path)
    print(f"[*] archive: {archive_path}")
    print(f"[*] sha256: {digest}")
    print(f"[*] sha file: {sha_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
