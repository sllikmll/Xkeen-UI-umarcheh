#!/usr/bin/env python3
"""Unified UI Qt desktop launcher.

Native Qt shell + QWebEngineView that runs the same local Unified UI Flask backend
and Mihomo core. This keeps the UI/design identical to the web version while giving
users a real desktop application shell.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

MIHOMO_VERSION = "1.19.29"
APP_NAME = "Unified UI"
DEFAULT_UI_PORT = int(os.environ.get("UNIFIED_UI_PORT", "18188"))
DEFAULT_CONTROLLER_PORT = int(os.environ.get("MIHOMO_CONTROLLER_PORT", "19190"))
DEFAULT_MIXED_PORT = int(os.environ.get("MIHOMO_MIXED_PORT", "17990"))
DEFAULT_DNS_PORT = int(os.environ.get("MIHOMO_DNS_PORT", "15354"))


def log(msg: str) -> None:
    print(f"[unified-ui-qt] {msg}", flush=True)


def app_support_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Unified UI Qt"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Unified UI Qt"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "unified-ui-qt"


def repo_root() -> Path:
    # PyInstaller exposes bundled files in sys._MEIPASS. In source mode this file
    # lives at desktop/qt/unified_ui_qt.py, so repo root is two parents up.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return repo_root().joinpath(*parts)


def settings_path() -> Path:
    return app_support_dir() / "desktop-settings.json"


def read_settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_settings(data: dict) -> None:
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def mihomo_asset() -> tuple[str, str]:
    arch = platform.machine().lower()
    if arch in {"x86_64", "amd64"}:
        a = "amd64"
    elif arch in {"arm64", "aarch64"}:
        a = "arm64"
    else:
        raise RuntimeError(f"Unsupported arch: {arch}")
    if sys.platform == "darwin":
        return f"mihomo-darwin-{a}-v{MIHOMO_VERSION}.gz", "mihomo"
    if sys.platform == "win32":
        return f"mihomo-windows-{a}-v{MIHOMO_VERSION}.zip", "mihomo.exe"
    return f"mihomo-linux-{a}-v{MIHOMO_VERSION}.gz", "mihomo"



def find_system_python() -> str:
    candidates = [sys.executable]
    if sys.platform == "win32":
        candidates += ["python.exe", "py.exe"]
    else:
        candidates += ["python3", "python"]
    seen = set()
    for cmd in candidates:
        if not cmd or cmd in seen:
            continue
        seen.add(cmd)
        args = [cmd, "--version"] if not cmd.endswith("py.exe") else [cmd, "-3", "--version"]
        try:
            res = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return cmd
        except Exception:
            pass
    raise RuntimeError("Python 3 not found for Unified UI backend")


def venv_python(runtime: Path) -> Path:
    venv = runtime / "venv"
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def ensure_backend_python(runtime: Path) -> Path:
    py = venv_python(runtime)
    req = resource_path("unified-ui", "requirements.txt")
    if not py.exists():
        system_py = find_system_python()
        log(f"creating backend venv with {system_py}")
        subprocess.run([system_py, "-m", "venv", str(runtime / "venv")], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    probe = subprocess.run([str(py), "-c", "import flask, gevent, geventwebsocket"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode != 0:
        log("installing backend Python requirements")
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(req)], check=True)
    return py

def ensure_mihomo(runtime: Path) -> Path:
    bin_dir = runtime / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    asset, bin_name = mihomo_asset()
    binary = bin_dir / bin_name
    if binary.exists():
        return binary
    url = f"https://github.com/MetaCubeX/mihomo/releases/download/v{MIHOMO_VERSION}/{asset}"
    tmp = runtime / asset
    log(f"downloading {url}")
    urllib.request.urlretrieve(url, tmp)
    if asset.endswith(".gz"):
        with gzip.open(tmp, "rb") as src, binary.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    elif asset.endswith(".zip"):
        with zipfile.ZipFile(tmp) as z:
            member = next((n for n in z.namelist() if n.lower().endswith(".exe")), None)
            if not member:
                raise RuntimeError("mihomo.exe not found in archive")
            with z.open(member) as src, binary.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        raise RuntimeError(f"Unsupported asset format: {asset}")
    tmp.unlink(missing_ok=True)
    if sys.platform != "win32":
        binary.chmod(0o755)
    return binary


def ensure_runtime_files(runtime: Path, enable_tun: bool) -> Path:
    mihomo_dir = runtime / "mihomo"
    rules_dir = mihomo_dir / "rules"
    profiles_dir = mihomo_dir / "profiles"
    rules_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    manual = rules_dir / "manual-proxy.yaml"
    if not manual.exists():
        manual.write_text("payload: []\n", encoding="utf-8")
    cfg = mihomo_dir / "config.yaml"
    if cfg.exists():
        if enable_tun:
            inject_tun_if_missing(cfg)
        return cfg
    tun = ""
    if enable_tun:
        tun = """
tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  strict-route: false
  dns-hijack:
    - any:53
"""
    cfg.write_text(f"""mixed-port: {DEFAULT_MIXED_PORT}
allow-lan: true
bind-address: 127.0.0.1
mode: rule
log-level: info
ipv6: false
external-controller: 127.0.0.1:{DEFAULT_CONTROLLER_PORT}
secret: ''
find-process-mode: off
profile:
  store-selected: true
  store-fake-ip: false
unified-delay: true
tcp-concurrent: true
{tun}
dns:
  enable: true
  listen: 127.0.0.1:{DEFAULT_DNS_PORT}
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver: [1.1.1.1, 8.8.8.8]
  nameserver: [https://1.1.1.1/dns-query, https://8.8.8.8/dns-query]
proxy-providers: {{}}
rule-providers:
  manual-proxy:
    type: file
    behavior: classical
    format: yaml
    path: {manual.as_posix()}
proxy-groups:
  - name: Маршрутизация
    type: select
    proxies: [DIRECT]
  - name: Ручной список
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: YouTube
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Telegram
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Meta
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: GitHub
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: AI
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Остальное
    type: select
    proxies: [DIRECT, Маршрутизация]
rules:
  - RULE-SET,manual-proxy,Ручной список
  - DOMAIN-SUFFIX,ru,DIRECT
  - DOMAIN-SUFFIX,su,DIRECT
  - DOMAIN-SUFFIX,рф,DIRECT
  - DOMAIN-SUFFIX,youtube.com,YouTube
  - DOMAIN-SUFFIX,googlevideo.com,YouTube
  - DOMAIN-SUFFIX,ytimg.com,YouTube
  - DOMAIN-SUFFIX,telegram.org,Telegram
  - DOMAIN-SUFFIX,t.me,Telegram
  - DOMAIN-SUFFIX,facebook.com,Meta
  - DOMAIN-SUFFIX,instagram.com,Meta
  - DOMAIN-SUFFIX,github.com,GitHub
  - DOMAIN-SUFFIX,openai.com,AI
  - DOMAIN-SUFFIX,chatgpt.com,AI
  - MATCH,Остальное
""", encoding="utf-8")
    return cfg


def inject_tun_if_missing(cfg: Path) -> None:
    text = cfg.read_text(encoding="utf-8")
    if "\ntun:" in f"\n{text}":
        return
    backup = cfg.with_name(f"{cfg.name}.pre-tun-{int(time.time())}.bak")
    backup.write_text(text, encoding="utf-8")
    block = """tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  strict-route: false
  dns-hijack:
    - any:53

"""
    cfg.write_text(block + text, encoding="utf-8")
    log(f"TUN injected into existing config, backup={backup}")


def http_ready(url: str, timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if 200 <= r.status < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


class RuntimeStack:
    def __init__(self, enable_tun: bool = False):
        self.enable_tun = enable_tun
        self.runtime = app_support_dir() / "runtime"
        self.logs = self.runtime / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.backend_python: Optional[Path] = None
        self.mihomo_proc: Optional[subprocess.Popen] = None
        self.ui_proc: Optional[subprocess.Popen] = None
        self.elevated_pid_file = self.runtime / "mihomo-elevated.pid"

    def start(self) -> None:
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.backend_python = ensure_backend_python(self.runtime)
        mihomo = ensure_mihomo(self.runtime)
        cfg = ensure_runtime_files(self.runtime, self.enable_tun)
        self._run_checked([str(mihomo), "-t", "-d", str(cfg.parent), "-f", str(cfg)])
        self._start_mihomo(mihomo, cfg)
        if not http_ready(f"http://127.0.0.1:{DEFAULT_CONTROLLER_PORT}/version", 45):
            raise RuntimeError("Mihomo controller did not become ready")
        self._start_ui(cfg)
        if not http_ready(f"http://127.0.0.1:{DEFAULT_UI_PORT}/", 45):
            raise RuntimeError("Unified UI did not become ready")

    def _run_checked(self, args: list[str]) -> None:
        log("run " + " ".join(args))
        res = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(args)}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")

    def _start_mihomo(self, mihomo: Path, cfg: Path) -> None:
        log_file = (self.logs / "mihomo.log").open("ab")
        if self.enable_tun and sys.platform == "darwin" and os.geteuid() != 0:
            self.elevated_pid_file.unlink(missing_ok=True)
            cmd = f"{sh_quote(str(mihomo))} -d {sh_quote(str(cfg.parent))} -f {sh_quote(str(cfg))} >> {sh_quote(str(self.logs / 'mihomo.log'))} 2>&1 & echo $! > {sh_quote(str(self.elevated_pid_file))}"
            log("requesting macOS administrator privileges for Mihomo TUN mode")
            subprocess.run(["osascript", "-e", f"do shell script {json.dumps(cmd)} with administrator privileges"], check=True)
            self.mihomo_proc = None
            return
        self.mihomo_proc = subprocess.Popen([str(mihomo), "-d", str(cfg.parent), "-f", str(cfg)], stdout=log_file, stderr=log_file)

    def _start_ui(self, cfg: Path) -> None:
        ui_log = (self.logs / "ui.log").open("ab")
        env = os.environ.copy()
        state = self.runtime / "state"
        state.mkdir(parents=True, exist_ok=True)
        env.update({
            "UNIFIED_UI_PORT": str(DEFAULT_UI_PORT),
            "UNIFIED_UI_STATE_DIR": str(state),
            "UNIFIED_UI_DIR": str(state),
            "MIHOMO_CONFIG": str(cfg),
            "MIHOMO_CONFIG_FILE": str(cfg),
            "MIHOMO_ROOT": str(cfg.parent),
            "MIHOMO_CONTROLLER_URL": f"http://127.0.0.1:{DEFAULT_CONTROLLER_PORT}",
            "MIHOMO_CONTROLLER_HOST": "127.0.0.1",
            "MIHOMO_CONTROLLER_PORT": str(DEFAULT_CONTROLLER_PORT),
            "PYTHONUNBUFFERED": "1",
        })
        script = resource_path("unified-ui", "run_server.py")
        backend_py = str(self.backend_python or sys.executable)
        self.ui_proc = subprocess.Popen([backend_py, str(script)], cwd=str(script.parent), env=env, stdout=ui_log, stderr=ui_log)

    def stop(self) -> None:
        for proc in [self.ui_proc, self.mihomo_proc]:
            if proc and proc.poll() is None:
                proc.terminate()
        if sys.platform == "darwin" and self.elevated_pid_file.exists():
            pid = self.elevated_pid_file.read_text().strip()
            if pid.isdigit():
                cmd = f"kill {pid} 2>/dev/null || true"
                try:
                    subprocess.run(["osascript", "-e", f"do shell script {json.dumps(cmd)} with administrator privileges"], check=False)
                except Exception:
                    pass
        for proc in [self.ui_proc, self.mihomo_proc]:
            if proc:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def run_smoke(enable_tun: bool) -> int:
    stack = RuntimeStack(enable_tun=enable_tun)
    try:
        stack.start()
        with urllib.request.urlopen(f"http://127.0.0.1:{DEFAULT_CONTROLLER_PORT}/version", timeout=5) as r:
            version = r.read().decode("utf-8", "replace")
        with urllib.request.urlopen(f"http://127.0.0.1:{DEFAULT_UI_PORT}/", timeout=5) as r:
            ui_status = r.status
        print(json.dumps({"ok": True, "ui_status": ui_status, "mihomo_version": version, "tun": enable_tun}, ensure_ascii=False))
        return 0
    finally:
        stack.stop()


def run_gui(enable_tun: bool) -> int:
    from PySide6.QtCore import Qt, QUrl, QSize
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QToolBar, QLabel
    from PySide6.QtWebEngineWidgets import QWebEngineView

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setStyleSheet("""
        QMainWindow { background: #07111f; }
        QToolBar { background: #0b1628; border: 0; spacing: 8px; padding: 8px; }
        QToolButton { color: #e8f0ff; background: #132238; border: 1px solid #243a5a; border-radius: 8px; padding: 7px 11px; }
        QToolButton:hover { background: #1b3152; }
        QLabel { color: #9fb0ce; }
    """)

    stack = RuntimeStack(enable_tun=enable_tun)
    stack.start()

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.resize(1440, 980)
            self.web = QWebEngineView(self)
            self.web.setUrl(QUrl(f"http://127.0.0.1:{DEFAULT_UI_PORT}/"))
            self.setCentralWidget(self.web)
            tb = QToolBar("Unified UI")
            tb.setMovable(False)
            tb.setIconSize(QSize(18, 18))
            self.addToolBar(Qt.TopToolBarArea, tb)
            title = QLabel("  Unified UI  ")
            title.setStyleSheet("font-weight: 800; color: #e8f0ff; font-size: 15px;")
            tb.addWidget(title)
            reload_action = QAction("Обновить", self)
            reload_action.triggered.connect(self.web.reload)
            tb.addAction(reload_action)
            runtime_action = QAction("Runtime", self)
            runtime_action.triggered.connect(lambda: os.system(f"open {sh_quote(str(app_support_dir()))}" if sys.platform == "darwin" else ""))
            tb.addAction(runtime_action)
            tun_action = QAction("TUN: " + ("ON" if enable_tun else "OFF"), self)
            tun_action.setCheckable(True)
            tun_action.setChecked(enable_tun)
            tun_action.triggered.connect(self.toggle_tun)
            tb.addAction(tun_action)
            tb.addSeparator()
            tb.addWidget(QLabel(f"UI :{DEFAULT_UI_PORT} · Mihomo :{DEFAULT_CONTROLLER_PORT}"))

        def toggle_tun(self):
            settings = read_settings()
            settings["enableTun"] = not enable_tun
            write_settings(settings)
            QMessageBox.information(self, APP_NAME, "Режим TUN переключён. Приложение нужно перезапустить.")

        def closeEvent(self, event):
            stack.stop()
            event.accept()

    win = MainWindow()
    win.show()
    return qt_app.exec()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="start stack, verify endpoints, then exit")
    parser.add_argument("--tun", action="store_true", help="enable full-system TUN routing")
    args = parser.parse_args()
    settings = read_settings()
    enable_tun = args.tun or truthy(os.environ.get("UNIFIED_UI_ENABLE_TUN")) or bool(settings.get("enableTun"))
    if args.smoke:
        return run_smoke(enable_tun=enable_tun)
    return run_gui(enable_tun=enable_tun)


if __name__ == "__main__":
    raise SystemExit(main())
