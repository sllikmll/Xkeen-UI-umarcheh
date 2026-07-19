from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENWRT_DIR = REPO_ROOT / "openwrt"
INSTALLER_SRC = OPENWRT_DIR / "install-openwrt-prototype.sh"
README_SRC = OPENWRT_DIR / "README.md"
FETCH_COMPAT_SRC = OPENWRT_DIR / "openwrt-fetch-compat.js"
UNIFIED_UI_DIR = REPO_ROOT / "unified-ui"
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


def render_full_panel_snapshot(dst_index: Path, *, version: str) -> None:
    """Render the real Flask/Jinja panel.html into a static OpenWrt entrypoint."""
    import os as _os
    import sys as _sys
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory(prefix="openwrt-panel-render-") as td:
        state = Path(td) / "state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "auth.json").write_text('{"username":"openwrt","password_hash":"snapshot"}\n', encoding="utf-8")
        env_backup = dict(_os.environ)
        try:
            _os.environ.update({
                "UNIFIED_UI_STATE_DIR": str(state),
                "MIHOMO_CONFIG": "/etc/mihomo/config.yaml",
                "MIHOMO_ROOT": "/etc/mihomo",
                "MIHOMO_CONTROLLER_URL": "http://127.0.0.1:9090",
                "MIHOMO_CONTROLLER_HOST": "127.0.0.1",
                "MIHOMO_CONTROLLER_PORT": "9090",
                "UNIFIED_UI_PANEL_SECTIONS_WHITELIST": ",".join([
                    "mihomo-selectors", "mihomo", "mihomo-connections", "geodat",
                    "protocol-wireguard", "protocol-amnezia", "protocol-hysteria2", "protocol-vless",
                    "protocol-trojan", "protocol-mieru", "protocol-naiveproxy", "proxy-protocols",
                    "unified", "commands", "files", "ui-settings", "devtools", "settings", "mihomo-generator",
                ]),
                "UNIFIED_UI_VERSION": version,
            })
            old_cwd = Path.cwd()
            _os.chdir(UNIFIED_UI_DIR)
            _sys.path.insert(0, str(UNIFIED_UI_DIR))
            try:
                import services.cores as _openwrt_cores  # type: ignore
                _openwrt_cores.detect_available_cores = lambda: ["mihomo"]
                _openwrt_cores.detect_running_core = lambda: "mihomo"
                from app_factory import create_app  # type: ignore
                app = create_app(ws_runtime=False)
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["auth"] = True
                        sess["user"] = "openwrt"
                    resp = client.get("/")
                    if resp.status_code != 200:
                        raise RuntimeError(f"panel render failed: HTTP {resp.status_code}")
                    html = resp.data.decode("utf-8", errors="replace")
            finally:
                _os.chdir(old_cwd)
                try:
                    _sys.path.remove(str(UNIFIED_UI_DIR))
                except ValueError:
                    pass
        finally:
            _os.environ.clear()
            _os.environ.update(env_backup)

    html = re.sub(r'<div class="dt-rename-row">\s*<span class="dt-rename-label">Роутинг Xray</span>\s*<input[^>]*data-tab-key="view:routing"[^>]*>\s*</div>', '', html)
    html = html.replace('Роутинг Xray', 'Маршрутизация')
    html = html.replace('/private/etc/mihomo/config.yaml', '/etc/mihomo/config.yaml')
    html = html.replace('/opt/etc/mihomo/config.yaml', '/etc/mihomo/config.yaml')
    html = html.replace('js-yaml.mjs', 'js-yaml.js')
    html = html.replace('/vendor/npm/js-yaml/dist/js-yaml.js', '/vendor/npm/js-yaml/dist/js-yaml.js?v=' + version.replace('"', '').replace("'", ''))
    html = html.replace('"/static/', '"/unified-ui/static/')
    html = html.replace("'/static/", "'/unified-ui/static/")
    html = html.replace('href="/ui/terminal-theme.css', 'href="/unified-ui/static/css/terminal-theme-empty.css')
    marker = "</head>"
    inject = '<script src="/unified-ui/openwrt-fetch-compat.js?v=' + version.replace('"', '') + '"></script>\n'
    if marker in html:
        html = html.replace(marker, inject + marker, 1)
    else:
        html = inject + html
    dst_index.parent.mkdir(parents=True, exist_ok=True)
    dst_index.write_text(html, encoding="utf-8")


def copy_full_panel_assets(dst_ui_root: Path, *, version: str) -> None:
    dst_ui_root.mkdir(parents=True, exist_ok=True)
    render_full_panel_snapshot(dst_ui_root / "index.html", version=version)
    shutil.copy2(FETCH_COMPAT_SRC, dst_ui_root / "openwrt-fetch-compat.js")
    static_dst = dst_ui_root / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    ignore = shutil.ignore_patterns("*.map", "__pycache__", ".DS_Store", "monaco-editor", "xterm")
    shutil.copytree(UNIFIED_UI_DIR / "static", static_dst, ignore=ignore)
    yaml_mjs = static_dst / "vendor" / "npm" / "js-yaml" / "dist" / "js-yaml.mjs"
    yaml_js = static_dst / "vendor" / "npm" / "js-yaml" / "dist" / "js-yaml.js"
    if yaml_mjs.exists():
        # OpenWrt uhttpd serves .mjs as application/octet-stream, which Chrome
        # blocks for module scripts. Keep the ESM content but expose it as .js.
        shutil.copy2(yaml_mjs, yaml_js)
    xterm_dir = static_dst / "xterm"
    xterm_dir.mkdir(parents=True, exist_ok=True)
    (xterm_dir / "xterm.css").write_text("/* OpenWrt: terminal disabled */\n", encoding="utf-8")
    css_dir = static_dst / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "terminal-theme-empty.css").write_text("/* OpenWrt static fallback */\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not INSTALLER_SRC.is_file():
        print(f"[!] installer not found: {INSTALLER_SRC}", file=sys.stderr)
        return 1
    if not README_SRC.is_file():
        print(f"[!] readme not found: {README_SRC}", file=sys.stderr)
        return 1
    if not FETCH_COMPAT_SRC.is_file():
        print(f"[!] fetch compat not found: {FETCH_COMPAT_SRC}", file=sys.stderr)
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
        copy_full_panel_assets(tmp_root / "www" / "unified-ui", version=version)
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
