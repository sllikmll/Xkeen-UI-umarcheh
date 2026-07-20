#!/usr/bin/env python3
"""Unified UI Native desktop app.

A real Qt Widgets application for Mihomo/Unified UI desktop usage.
No QWebEngine, no embedded Flask panel, no local web UI server inside the window.
The app talks directly to Mihomo's external-controller API and manages local
runtime files itself.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import gzip
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

MIHOMO_VERSION = "1.19.29"
APP_NAME = "Unified UI Native"
DEFAULT_CONTROLLER_PORT = int(os.environ.get("MIHOMO_CONTROLLER_PORT", "19190"))
DEFAULT_MIXED_PORT = int(os.environ.get("MIHOMO_MIXED_PORT", "17990"))
DEFAULT_DNS_PORT = int(os.environ.get("MIHOMO_DNS_PORT", "15354"))

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_UI_DIR = REPO_ROOT / "unified-ui"
if WEB_UI_DIR.exists() and str(WEB_UI_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_UI_DIR))

try:
    from services.mihomo_generator_proxies import ensure_leading_dash_for_yaml_block
    from services.mihomo_proxy_parsers import (
        ProxyParseResult,
        parse_openvpn,
        parse_proxy_uri,
        parse_tailscale,
        parse_wireguard,
    )
except Exception as exc:  # pragma: no cover - surfaced in GUI diagnostics
    ProxyParseResult = Any  # type: ignore
    _WEB_PARSER_IMPORT_ERROR = exc
else:
    _WEB_PARSER_IMPORT_ERROR = None

DARK_QSS = """
QMainWindow, QWidget { background: #07111f; color: #e8f0ff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
QTabWidget::pane { border: 1px solid #1f3454; border-radius: 10px; top: -1px; }
QTabBar::tab { background: #101d31; color: #b9c7df; border: 1px solid #203857; padding: 9px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; }
QTabBar::tab:selected { background: #1d4ed8; color: white; border-color: #3b82f6; }
QPushButton { background: #132238; color: #e8f0ff; border: 1px solid #2b4264; border-radius: 8px; padding: 8px 12px; }
QPushButton:hover { background: #1b3152; }
QPushButton:pressed { background: #0f1d31; }
QPushButton#danger { border-color: #7f1d1d; background: #3b1116; color: #fecaca; }
QPushButton#primary { border-color: #2563eb; background: #1d4ed8; color: white; }
QPushButton#tile { padding: 5px 8px; min-height: 36px; border-radius: 7px; text-align: left; }
QPushButton#tileActive { padding: 5px 8px; min-height: 36px; border-radius: 7px; text-align: left; border-color: #2563eb; background: #1d4ed8; color: white; }
QLabel#title { font-size: 22px; font-weight: 800; color: #f8fbff; }
QLabel#muted { color: #93a4bf; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox { background: #0b1628; color: #e8f0ff; border: 1px solid #263d5e; border-radius: 8px; padding: 7px; selection-background-color: #2563eb; }
QTableWidget { background: #0b1628; alternate-background-color: #0f1d31; gridline-color: #203857; border: 1px solid #203857; border-radius: 10px; }
QHeaderView::section { background: #132238; color: #d8e4f8; border: 0; border-right: 1px solid #203857; padding: 8px; font-weight: 700; }
QGroupBox { border: 1px solid #203857; border-radius: 10px; margin-top: 12px; padding: 12px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #d8e4f8; }
QStatusBar { background: #0b1628; color: #93a4bf; }
"""


def app_support_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Unified UI Native"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Unified UI Native"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "unified-ui-native"


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


def ensure_mihomo(runtime: Path) -> Path:
    bin_dir = runtime / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    asset, bin_name = mihomo_asset()
    binary = bin_dir / bin_name
    if binary.exists():
        return binary
    url = f"https://github.com/MetaCubeX/mihomo/releases/download/v{MIHOMO_VERSION}/{asset}"
    tmp = runtime / asset
    print(f"[native] downloading {url}", flush=True)
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


def ensure_config(runtime: Path) -> Path:
    mihomo_dir = runtime / "mihomo"
    rules_dir = mihomo_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    manual = rules_dir / "manual-proxy.yaml"
    if not manual.exists():
        manual.write_text("payload: []\n", encoding="utf-8")
    cfg = mihomo_dir / "config.yaml"
    if cfg.exists():
        return cfg
    cfg.write_text(f"""mixed-port: {DEFAULT_MIXED_PORT}
allow-lan: true
bind-address: 127.0.0.1
mode: rule
log-level: info
ipv6: false
external-controller: 127.0.0.1:{DEFAULT_CONTROLLER_PORT}
secret: ''
profile:
  store-selected: true
  store-fake-ip: false
unified-delay: true
tcp-concurrent: true
dns:
  enable: true
  listen: 127.0.0.1:{DEFAULT_DNS_PORT}
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver: [1.1.1.1, 8.8.8.8]
  nameserver: [https://1.1.1.1/dns-query, https://8.8.8.8/dns-query]
proxies: []
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
  - name: GitHub
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: AI
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Остальное
    type: select
    proxies: [DIRECT, Маршрутизация]
rule-providers:
  manual-proxy:
    type: file
    behavior: classical
    format: yaml
    path: {manual.as_posix()}
rules:
  - RULE-SET,manual-proxy,Ручной список
  - DOMAIN-SUFFIX,ru,DIRECT
  - DOMAIN-SUFFIX,su,DIRECT
  - DOMAIN-SUFFIX,рф,DIRECT
  - DOMAIN-SUFFIX,youtube.com,YouTube
  - DOMAIN-SUFFIX,googlevideo.com,YouTube
  - DOMAIN-SUFFIX,telegram.org,Telegram
  - DOMAIN-SUFFIX,t.me,Telegram
  - DOMAIN-SUFFIX,github.com,GitHub
  - DOMAIN-SUFFIX,openai.com,AI
  - DOMAIN-SUFFIX,chatgpt.com,AI
  - MATCH,Остальное
""", encoding="utf-8")
    return cfg


@dataclass
class ImportResult:
    name: str
    yaml: str
    kind: str
    source: str = ""


class NativeConfigManager:
    """Local config/import/apply layer for the native desktop app."""

    def __init__(self, runtime: "MihomoRuntime") -> None:
        self.runtime = runtime

    @property
    def config_path(self) -> Path:
        return self.runtime.config_path

    @property
    def backups_dir(self) -> Path:
        return self.runtime.runtime / "backups"

    @property
    def subscriptions_path(self) -> Path:
        return self.runtime.runtime / "subscriptions.json"

    def read_config(self) -> str:
        ensure_config(self.runtime.runtime)
        return self.config_path.read_text(encoding="utf-8")

    def validate_text(self, text: str) -> tuple[bool, str]:
        try:
            parsed = yaml.safe_load(text) or {}
            if not isinstance(parsed, dict):
                return False, "config.yaml должен быть YAML-объектом"
            if "proxies" not in parsed:
                return False, "В config.yaml нет секции proxies"
            if "proxy-groups" not in parsed:
                return False, "В config.yaml нет секции proxy-groups"
        except Exception as exc:
            return False, f"YAML parse error: {exc}"
        try:
            mihomo = ensure_mihomo(self.runtime.runtime)
            cfg_dir = self.config_path.parent
            cfg_dir.mkdir(parents=True, exist_ok=True)
            test_cfg = cfg_dir / ".unified-ui-native-test-config.yaml"
            test_cfg.write_text(text, encoding="utf-8")
            try:
                result = subprocess.run(
                    [str(mihomo), "-t", "-d", str(cfg_dir), "-f", str(test_cfg)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    **self.runtime._subprocess_window_kwargs(),
                )
            finally:
                test_cfg.unlink(missing_ok=True)
            output = (result.stdout or "") + ("\n" if result.stdout and result.stderr else "") + (result.stderr or "")
            if result.returncode != 0:
                return False, output.strip() or f"mihomo -t failed: {result.returncode}"
            return True, output.strip() or "OK"
        except Exception as exc:
            return False, f"mihomo validation error: {exc}"

    def backup_current(self) -> Path:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        digest = hashlib.sha1(self.read_config().encode("utf-8", errors="ignore")).hexdigest()[:8]
        dst = self.backups_dir / f"config-{stamp}-{digest}.yaml"
        shutil.copy2(self.config_path, dst)
        return dst

    def save_text(self, text: str, *, validate: bool = True) -> tuple[Path | None, str]:
        normalized_note = ""
        try:
            data = self._load_yaml_dict(text)
            if self._normalize_runtime_config_data(data):
                text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=140)
                normalized_note = "; runtime-поля нормализованы"
        except Exception:
            # Let the normal validator return the precise YAML/config error.
            pass
        if validate:
            ok, msg = self.validate_text(text)
            if not ok:
                raise RuntimeError(msg)
        backup = self.backup_current() if self.config_path.exists() else None
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8")
        return backup, "config.yaml сохранён" + normalized_note

    def save_and_restart(self, text: str) -> tuple[Path | None, str]:
        backup, msg = self.save_text(text, validate=True)
        self.runtime.restart()
        return backup, msg + "; Mihomo перезапущен"

    def _load_yaml_dict(self, text: str) -> dict[str, Any]:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("config.yaml должен быть YAML-объектом")
        data.setdefault("proxies", [])
        data.setdefault("proxy-groups", [])
        if data.get("proxies") is None:
            data["proxies"] = []
        if not isinstance(data.get("proxies"), list):
            raise ValueError("proxies должен быть списком")
        if not isinstance(data.get("proxy-groups"), list):
            raise ValueError("proxy-groups должен быть списком")
        return data

    def group_names(self) -> list[str]:
        data = self._load_yaml_dict(self.read_config())
        names: list[str] = []
        for group in data.get("proxy-groups") or []:
            if isinstance(group, dict) and str(group.get("name") or "").strip():
                names.append(str(group.get("name")).strip())
        return names

    def config_data(self) -> dict[str, Any]:
        return self._load_yaml_dict(self.read_config())

    def _normalize_runtime_config_data(self, data: dict[str, Any]) -> bool:
        changed = False

        def set_if(key: str, value: Any) -> None:
            nonlocal changed
            if data.get(key) != value:
                data[key] = value
                changed = True

        set_if("external-controller", f"127.0.0.1:{DEFAULT_CONTROLLER_PORT}")
        set_if("mixed-port", DEFAULT_MIXED_PORT)
        set_if("allow-lan", True)
        set_if("bind-address", "127.0.0.1")
        set_if("ipv6", False)

        mode = str(data.get("find-process-mode") or "").strip().lower()
        if mode not in {"strict", "always"}:
            data["find-process-mode"] = "strict"
            changed = True

        dns = data.get("dns")
        if not isinstance(dns, dict):
            dns = {}
            data["dns"] = dns
            changed = True
        desired_dns_listen = f"127.0.0.1:{DEFAULT_DNS_PORT}"
        if dns.get("listen") != desired_dns_listen:
            dns["listen"] = desired_dns_listen
            changed = True
        if dns.get("ipv6") is not False:
            dns["ipv6"] = False
            changed = True

        def safe_rel_path(value: str, prefix: str, suffix: str = ".yaml") -> str:
            raw = str(value or "").strip()
            name = Path(raw).name if raw else ""
            if not name or name in {".", ".."}:
                name = "item" + suffix
            if not name.endswith(('.yaml', '.yml', '.mrs', '.txt')):
                name += suffix
            return str((self.config_path.parent / prefix / name).as_posix())

        providers = data.get("proxy-providers")
        if isinstance(providers, dict):
            for name, provider in providers.items():
                if not isinstance(provider, dict):
                    continue
                path_value = str(provider.get("path") or "").strip()
                if path_value and (Path(path_value).is_absolute() or path_value.startswith("..")):
                    provider["path"] = safe_rel_path(path_value, "providers")
                    changed = True

        rule_providers = data.get("rule-providers")
        if isinstance(rule_providers, dict):
            for name, provider in rule_providers.items():
                if not isinstance(provider, dict):
                    continue
                ptype = str(provider.get("type") or "").lower()
                path_value = str(provider.get("path") or "").strip()
                if ptype in {"file", "inline"} or path_value:
                    if not path_value or Path(path_value).is_absolute() or path_value.startswith(".."):
                        provider["path"] = safe_rel_path(path_value or f"{name}.yaml", "rules")
                        changed = True
        return changed

    def ensure_runtime_compatible_config(self) -> bool:
        """Normalize config fields owned by the native runtime.

        Imported router/Keenetic/OpenWrt configs often carry controller/DNS/proxy
        ports that belong to another environment. The native app always talks to
        DEFAULT_CONTROLLER_PORT, so letting an old `external-controller: :9090`
        survive makes Mihomo start successfully while the GUI waits forever on
        127.0.0.1:19190.
        """
        data = self._load_yaml_dict(self.read_config())
        changed = self._normalize_runtime_config_data(data)
        if changed:
            backup = self.backup_current() if self.config_path.exists() else None
            self.config_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=140), encoding="utf-8")
            if backup:
                (self.runtime.runtime / "logs").mkdir(parents=True, exist_ok=True)
                with (self.runtime.runtime / "logs" / "native-app.log").open("a", encoding="utf-8") as fh:
                    fh.write(f"\n=== Unified UI Native ===\nruntime config sanitized; backup={backup}\n")
        return changed


    def proxy_provider_items(self) -> list[dict[str, Any]]:
        data = self.config_data()
        providers = data.get("proxy-providers") or {}
        if not isinstance(providers, dict):
            return []
        items: list[dict[str, Any]] = []
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            used_by = []
            for group in data.get("proxy-groups") or []:
                if isinstance(group, dict) and name in (group.get("use") or []):
                    used_by.append(str(group.get("name") or ""))
            items.append({
                "name": str(name),
                "type": str(provider.get("type") or ""),
                "url": str(provider.get("url") or provider.get("path") or ""),
                "path": str(provider.get("path") or ""),
                "interval": str(provider.get("interval") or ""),
                "used_by": ", ".join(x for x in used_by if x),
            })
        return items

    def proxy_group_items(self) -> list[dict[str, Any]]:
        data = self.config_data()
        items: list[dict[str, Any]] = []
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            items.append({
                "name": str(group.get("name") or ""),
                "type": str(group.get("type") or ""),
                "proxies": ", ".join(map(str, group.get("proxies") or [])),
                "use": ", ".join(map(str, group.get("use") or [])),
                "now": "",
            })
        return items

    def static_proxy_items(self) -> list[dict[str, Any]]:
        data = self.config_data()
        items: list[dict[str, Any]] = []
        for proxy in data.get("proxies") or []:
            if isinstance(proxy, dict):
                items.append({
                    "name": str(proxy.get("name") or ""),
                    "type": str(proxy.get("type") or ""),
                    "server": str(proxy.get("server") or ""),
                    "port": str(proxy.get("port") or ""),
                })
        return items

    def rule_provider_items(self) -> list[dict[str, Any]]:
        data = self.config_data()
        providers = data.get("rule-providers") or {}
        if not isinstance(providers, dict):
            return []
        return [
            {
                "name": str(name),
                "type": str(provider.get("type") or "") if isinstance(provider, dict) else "",
                "behavior": str(provider.get("behavior") or "") if isinstance(provider, dict) else "",
                "path": str(provider.get("path") or provider.get("url") or "") if isinstance(provider, dict) else "",
            }
            for name, provider in providers.items()
        ]

    def _unique_provider_name(self, data: dict[str, Any], desired: str, url: str = "") -> str:
        providers = data.get("proxy-providers")
        if not isinstance(providers, dict):
            return desired.strip() or "subscription_1"
        base = desired.strip() or "subscription_1"
        existing = providers.get(base)
        if not isinstance(existing, dict):
            return base
        if url and str(existing.get("url") or "").strip() == url.strip():
            return base
        for i in range(2, 1000):
            candidate = f"subscription_{i}" if base == "subscription_1" else f"{base}_{i}"
            if candidate not in providers:
                return candidate
        raise RuntimeError("Не удалось подобрать уникальное имя provider")

    def _selected_or_all_selector_groups(self, data: dict[str, Any], groups: list[str] | None) -> list[str]:
        selected = [str(g).strip() for g in (groups or []) if str(g).strip()]
        if selected:
            return selected
        names: list[str] = []
        for group in data.get("proxy-groups") or []:
            if isinstance(group, dict) and str(group.get("type") or "").lower() in {"select", "url-test", "fallback", "load-balance"}:
                name = str(group.get("name") or "").strip()
                if name:
                    names.append(name)
        return names

    def _unique_proxy_name(self, data: dict[str, Any], desired: str) -> str:
        existing = {str(p.get("name") or "") for p in data.get("proxies") or [] if isinstance(p, dict)}
        base = desired.strip() or "Imported Proxy"
        if base not in existing:
            return base
        for i in range(2, 1000):
            candidate = f"{base} {i}"
            if candidate not in existing:
                return candidate
        raise RuntimeError("Не удалось подобрать уникальное имя прокси")

    def parse_import(self, text: str, *, name: str = "", kind: str = "auto") -> list[ImportResult]:
        raw = str(text or "").strip()
        if not raw:
            raise ValueError("Пустой импорт")
        kind_l = (kind or "auto").strip().lower()
        if _WEB_PARSER_IMPORT_ERROR is not None:
            raise RuntimeError(f"web-парсеры недоступны: {_WEB_PARSER_IMPORT_ERROR}")

        # Multi-line URI subscription pasted directly.
        uri_lines = [line.strip() for line in raw.splitlines() if "://" in line and not line.strip().startswith("#")]
        if kind_l in {"auto", "uri", "link"} and uri_lines and len(uri_lines) > 1:
            return [self._parse_single_uri(line, name if len(uri_lines) == 1 else "") for line in uri_lines]

        if kind_l in {"auto", "uri", "link"} and "://" in raw.splitlines()[0]:
            return [self._parse_single_uri(raw, name)]

        if kind_l in {"auto", "wireguard", "awg", "amneziawg"} and "[Interface]" in raw and "[Peer]" in raw:
            res = parse_wireguard(raw, custom_name=name or None)
            return [ImportResult(name=res.name, yaml=res.yaml, kind="wireguard", source="wireguard-conf")]

        if kind_l in {"auto", "openvpn"} and ("client" in raw.lower() and "remote " in raw.lower()):
            res = parse_openvpn(raw, custom_name=name or None)
            return [ImportResult(name=res.name, yaml=res.yaml, kind="openvpn", source="openvpn-conf")]

        if kind_l in {"auto", "tailscale"} and ("auth-key" in raw or "accept-routes" in raw):
            res = parse_tailscale(raw, custom_name=name or None)
            return [ImportResult(name=res.name, yaml=res.yaml, kind="tailscale", source="tailscale-settings")]

        # YAML proxy block or full Mihomo config.
        data = yaml.safe_load(raw)
        if isinstance(data, dict) and isinstance(data.get("proxies"), list):
            imports = []
            for item in data["proxies"]:
                if isinstance(item, dict) and item.get("name"):
                    imports.append(ImportResult(name=str(item["name"]), yaml=yaml.safe_dump([item], allow_unicode=True, sort_keys=False), kind=str(item.get("type") or "yaml"), source="mihomo-yaml"))
            if imports:
                return imports
        if isinstance(data, list):
            imports = []
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    imports.append(ImportResult(name=str(item["name"]), yaml=yaml.safe_dump([item], allow_unicode=True, sort_keys=False), kind=str(item.get("type") or "yaml"), source="proxy-yaml"))
            if imports:
                return imports
        if isinstance(data, dict) and data.get("name"):
            return [ImportResult(name=str(data["name"]), yaml=yaml.safe_dump([data], allow_unicode=True, sort_keys=False), kind=str(data.get("type") or "yaml"), source="proxy-yaml")]
        raise ValueError("Не понял формат. Поддерживаются URI, WG/AWG .conf, OpenVPN, Tailscale, proxy YAML и полный Mihomo YAML.")

    def _parse_wireguard_uri(self, line: str, name: str = "") -> ImportResult:
        parsed = urllib.parse.urlparse(line.strip())
        qs = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()}
        private_key = urllib.parse.unquote(parsed.username or "")
        host = parsed.hostname or ""
        port = parsed.port or 51820
        public_key = urllib.parse.unquote(qs.get("publickey") or qs.get("public-key") or "")
        address = urllib.parse.unquote(qs.get("address") or "10.0.0.2/32")
        mtu = urllib.parse.unquote(qs.get("mtu") or "")
        dns = urllib.parse.unquote(qs.get("dns") or "")
        allowed = urllib.parse.unquote(qs.get("allowedips") or qs.get("allowed-ips") or "0.0.0.0/0, ::/0")
        reserved = urllib.parse.unquote(qs.get("reserved") or qs.get("clientid") or qs.get("client-id") or "")
        if not private_key or not host or not public_key:
            raise ValueError("wireguard:// URI должен содержать private key, endpoint host и publickey")
        conf = ["[Interface]", f"PrivateKey = {private_key}", f"Address = {address}"]
        if dns:
            conf.append(f"DNS = {dns}")
        if mtu:
            conf.append(f"MTU = {mtu}")
        if reserved:
            conf.append(f"Reserved = {reserved}")
        conf += ["", "[Peer]", f"PublicKey = {public_key}", f"AllowedIPs = {allowed}", f"Endpoint = {host}:{port}"]
        res = parse_wireguard("\n".join(conf) + "\n", custom_name=name or urllib.parse.unquote(parsed.fragment or "") or None)
        return ImportResult(name=res.name, yaml=res.yaml, kind="wireguard", source="wireguard-uri")

    def _parse_single_uri(self, text: str, name: str = "") -> ImportResult:
        line = text.strip()
        # Some subscriptions are base64 with URI lines inside.
        if "://" not in line:
            try:
                decoded = base64.b64decode(line + "=" * (-len(line) % 4)).decode("utf-8", errors="ignore")
                line = next((x.strip() for x in decoded.splitlines() if "://" in x), line)
            except Exception:
                pass
        if line.lower().startswith("wireguard://"):
            return self._parse_wireguard_uri(line, name)
        res = parse_proxy_uri(line, custom_name=name or None)
        return ImportResult(name=res.name, yaml=res.yaml, kind=line.split(":", 1)[0].lower(), source="uri")

    def decode_subscription_text(self, raw: bytes | str) -> str:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
            raw_bytes = raw
        else:
            text = str(raw or "")
            raw_bytes = text.encode("utf-8", errors="ignore")
        if "://" in text:
            return text
        compact = b"".join(raw_bytes.split())
        try:
            decoded = base64.b64decode(compact + b"=" * (-len(compact) % 4)).decode("utf-8", errors="replace")
            if "://" in decoded:
                return decoded
        except Exception:
            pass
        return text

    def fetch_subscription_text(self, url: str) -> str:
        req = urllib.request.Request(str(url).strip(), headers={"User-Agent": f"ClashMeta/{MIHOMO_VERSION}; mihomo/{MIHOMO_VERSION}"})
        with urllib.request.urlopen(req, timeout=25) as response:
            return self.decode_subscription_text(response.read())

    def parse_subscription_text(self, text: str) -> list[ImportResult]:
        decoded = self.decode_subscription_text(text)
        uri_lines = [line.strip() for line in decoded.splitlines() if "://" in line and not line.strip().startswith("#")]
        imports: list[ImportResult] = []
        errors: list[str] = []
        for line in uri_lines:
            try:
                imports.append(self._parse_single_uri(line))
            except Exception as exc:
                errors.append(f"{line[:80]}: {exc}")
        if not imports:
            detail = "\n".join(errors[:5])
            raise ValueError("В подписке не найдено поддерживаемых прокси" + (f":\n{detail}" if detail else ""))
        return imports

    def fetch_subscription_imports(self, url: str) -> list[ImportResult]:
        return self.parse_subscription_text(self.fetch_subscription_text(url))

    def _append_imports_to_data(self, data: dict[str, Any], imports: list[ImportResult], target_groups: list[str]) -> list[str]:
        added: list[str] = []
        for imp in imports:
            block = ensure_leading_dash_for_yaml_block(imp.yaml)
            parsed = yaml.safe_load(block)
            if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
                raise ValueError(f"Импорт {imp.name}: парсер вернул невалидный YAML")
            proxy = parsed[0]
            desired_name = str(proxy.get("name") or imp.name)
            existing_names = {str(p.get("name") or "") for p in data.get("proxies") or [] if isinstance(p, dict)}
            if desired_name in existing_names:
                continue
            proxy["name"] = self._unique_proxy_name(data, desired_name)
            data["proxies"].append(proxy)
            added.append(str(proxy["name"]))
            for group in data.get("proxy-groups") or []:
                if not isinstance(group, dict):
                    continue
                gname = str(group.get("name") or "").strip()
                if target_groups and gname not in target_groups:
                    continue
                proxies = group.get("proxies")
                if proxies is None:
                    proxies = []
                    group["proxies"] = proxies
                if isinstance(proxies, list) and proxy["name"] not in proxies:
                    proxies.append(proxy["name"])
        return added

    def apply_imports(self, imports: list[ImportResult], groups: list[str] | None = None, *, restart: bool = True) -> tuple[list[str], Path | None, str]:
        if not imports:
            raise ValueError("Нет прокси для импорта")
        data = self._load_yaml_dict(self.read_config())
        group_names = self.group_names()
        target_groups = [g for g in (groups or []) if g]
        if not target_groups:
            target_groups = [group_names[0]] if group_names else []
        added = self._append_imports_to_data(data, imports, target_groups)
        new_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=140)
        backup, msg = self.save_text(new_text, validate=True)
        if restart:
            self.runtime.restart()
            msg += "; Mihomo перезапущен"
        return added, backup, msg

    def add_subscription_provider(self, url: str, name: str = "", interval: int = 3600, groups: list[str] | None = None, *, restart: bool = True, mirror_static: bool = True, subscription_text: str | None = None) -> tuple[str, list[str], Path | None, str]:
        url = str(url or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Subscription URL должен начинаться с http:// или https://")
        data = self._load_yaml_dict(self.read_config())
        providers = data.get("proxy-providers")
        if not isinstance(providers, dict):
            providers = {}
            data["proxy-providers"] = providers
        name = self._unique_provider_name(data, name or "subscription_1", url)
        providers[name] = {
            "type": "http",
            "url": url,
            "interval": int(interval),
            "path": f"./providers/{name}.yaml",
            "health-check": {"enable": True, "url": "https://www.gstatic.com/generate_204", "interval": 300},
        }
        target_groups = set(self._selected_or_all_selector_groups(data, groups))
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            if str(group.get("type") or "").lower() not in {"select", "url-test", "fallback", "load-balance"}:
                continue
            if target_groups and str(group.get("name") or "").strip() not in target_groups:
                continue
            use = group.get("use")
            if use is None:
                use = []
                group["use"] = use
            if isinstance(use, list) and name not in use:
                use.append(name)
        added_static: list[str] = []
        mirror_error = ""
        if mirror_static:
            try:
                imports = self.parse_subscription_text(subscription_text) if subscription_text is not None else self.fetch_subscription_imports(url)
                added_static = self._append_imports_to_data(data, imports, list(target_groups))
            except Exception as exc:
                mirror_error = str(exc)
        new_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=140)
        backup, msg = self.save_text(new_text, validate=True)
        if restart:
            self.runtime.restart()
            try:
                self.runtime.update_proxy_providers()
            except Exception:
                pass
            msg += "; Mihomo перезапущен"
        if added_static:
            msg += f"; ноды подписки добавлены в proxies: {len(added_static)}"
        elif mirror_error:
            msg += f"; provider добавлен, но ноды не удалось зеркалировать: {mirror_error}"
        return name, added_static, backup, f"provider {name} добавлен; {msg}"


@dataclass
class MihomoRuntime:
    runtime: Path
    controller: str
    proc: subprocess.Popen | None = None

    @classmethod
    def create(cls) -> "MihomoRuntime":
        runtime = app_support_dir() / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        return cls(runtime=runtime, controller=f"http://127.0.0.1:{DEFAULT_CONTROLLER_PORT}")

    @property
    def config_path(self) -> Path:
        return self.runtime / "mihomo" / "config.yaml"

    @property
    def manual_rules_path(self) -> Path:
        return self.runtime / "mihomo" / "rules" / "manual-proxy.yaml"

    def _subprocess_window_kwargs(self) -> dict[str, Any]:
        """Hide helper console windows on Windows builds.

        PyInstaller --windowed removes our app console, but child console
        programs can still spawn their own black window unless CREATE_NO_WINDOW
        is set. Mihomo is a console binary on Windows, so this is mandatory for
        a real desktop app.
        """
        if sys.platform != "win32":
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }

    def start(self) -> None:
        cfg = ensure_config(self.runtime)
        NativeConfigManager(self).ensure_runtime_compatible_config()
        mihomo = ensure_mihomo(self.runtime)
        logs = self.runtime / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        popen_kwargs = self._subprocess_window_kwargs()
        test = subprocess.run(
            [str(mihomo), "-t", "-d", str(cfg.parent), "-f", str(cfg)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_kwargs,
        )
        if test.returncode != 0:
            raise RuntimeError(f"Mihomo config invalid\nSTDOUT:\n{test.stdout}\nSTDERR:\n{test.stderr}")
        log_file = (logs / "mihomo-native.log").open("ab")
        self.proc = subprocess.Popen(
            [str(mihomo), "-d", str(cfg.parent), "-f", str(cfg)],
            stdout=log_file,
            stderr=log_file,
            **popen_kwargs,
        )
        deadline = time.time() + 35
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"Mihomo exited during startup with code {self.proc.returncode}; see {logs / 'mihomo-native.log'}")
            try:
                self.get("/version")
                return
            except Exception:
                time.sleep(0.35)
        raise RuntimeError(f"Mihomo controller did not become ready; see {logs / 'mihomo-native.log'}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def restart(self) -> None:
        self.stop()
        time.sleep(0.4)
        self.start()

    def _request(self, method: str, path: str, body: bytes | None = None) -> Any:
        url = self.controller + path
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if not data:
            return None
        return json.loads(data.decode("utf-8"))

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def put_json(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PUT", path, json.dumps(payload).encode("utf-8"))

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def version(self) -> str:
        data = self.get("/version")
        if isinstance(data, dict):
            return data.get("version") or data.get("meta") or json.dumps(data, ensure_ascii=False)
        return str(data)

    def proxies(self) -> dict[str, Any]:
        data = self.get("/proxies")
        return data.get("proxies", {}) if isinstance(data, dict) else {}

    def proxy_providers(self) -> dict[str, Any]:
        data = self.get("/providers/proxies")
        return data.get("providers", {}) if isinstance(data, dict) else {}

    def update_proxy_providers(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            providers = self.proxy_providers()
        except Exception as exc:
            return [{"ok": False, "provider": "<all>", "error": str(exc)}]
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            if str(provider.get("vehicleType") or "").upper() != "HTTP":
                continue
            quoted = urllib.parse.quote(str(name), safe="")
            try:
                self._request("PUT", f"/providers/proxies/{quoted}")
                results.append({"ok": True, "provider": str(name)})
            except Exception as exc:
                results.append({"ok": False, "provider": str(name), "error": str(exc)})
        return results

    def connections_data(self) -> dict[str, Any]:
        data = self.get("/connections")
        return data if isinstance(data, dict) else {}

    def connections(self) -> list[dict[str, Any]]:
        data = self.connections_data()
        connections = data.get("connections")
        return connections if isinstance(connections, list) else []

    def connection_history_from_logs(self, limit: int = 80) -> list[dict[str, Any]]:
        log_path = self.runtime / "logs" / "mihomo-native.log"
        if not log_path.exists():
            return []
        try:
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-2000:]
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        pattern = re.compile(r'msg="\[(TCP|UDP)\] ([^ ]+) --> ([^ ]+)(?: .*? using ([^" ]+))?')
        for line in reversed(lines):
            match = pattern.search(line)
            if not match:
                continue
            proto, source, destination, proxy = match.groups()
            host = destination.rsplit(":", 1)[0] if ":" in destination else destination
            rows.append({
                "id": "log",
                "metadata": {"network": proto, "source": source, "remoteDestination": destination, "host": host},
                "chains": [proxy or "—"],
                "upload": None,
                "download": None,
                "history": True,
            })
            if len(rows) >= limit:
                break
        return rows

    def traffic(self) -> dict[str, Any]:
        # Mihomo's /traffic endpoint is a streaming endpoint. Do not call it
        # through the normal blocking JSON request path or the GUI freezes
        # before the main window is shown. A future version should consume it
        # from a background worker.
        return {}

    def close_connection(self, conn_id: str) -> None:
        self.delete(f"/connections/{urllib.parse.quote(conn_id)}")

    def select_proxy(self, group: str, proxy: str) -> None:
        quoted = urllib.parse.quote(group, safe="")
        self.put_json(f"/proxies/{quoted}", {"name": proxy})

    def delay(self, proxy: str) -> int | None:
        quoted = urllib.parse.quote(proxy, safe="")
        try:
            data = self.get(f"/proxies/{quoted}/delay?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204")
            return int(data.get("delay")) if isinstance(data, dict) and data.get("delay") is not None else None
        except Exception:
            return None


def human_bytes(value: Any) -> str:
    try:
        n = float(value)
    except Exception:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}"


def run_gui(runtime: MihomoRuntime, gui_smoke_seconds: float | None = None) -> int:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    cfg_mgr = NativeConfigManager(runtime)

    class SelectorsTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.layout = QVBoxLayout(self)
            header = QHBoxLayout()
            self.mode = QComboBox()
            self.mode.addItems(["Списки", "Плитки"])
            self.mode.currentTextChanged.connect(self.refresh)
            refresh = QPushButton("Обновить селекторы")
            refresh.clicked.connect(self.refresh)
            ping = QPushButton("Обновить все пинги")
            ping.clicked.connect(self.ping_all)
            providers = QPushButton("Обновить подписки")
            providers.clicked.connect(self.update_providers)
            header.addWidget(QLabel("Вид:"))
            header.addWidget(self.mode)
            header.addStretch(1)
            header.addWidget(providers)
            header.addWidget(ping)
            header.addWidget(refresh)
            self.layout.addLayout(header)
            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.content = QWidget()
            self.groups_box = QVBoxLayout(self.content)
            self.groups_box.setContentsMargins(0, 0, 0, 0)
            self.scroll.setWidget(self.content)
            self.layout.addWidget(self.scroll, 1)
            self.status = QLabel("Готово")
            self.status.setObjectName("muted")
            self.layout.addWidget(self.status)

        def clear_groups(self) -> None:
            while self.groups_box.count():
                item = self.groups_box.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        def selector_items(self) -> list[tuple[str, dict[str, Any]]]:
            proxies = runtime.proxies()
            items: list[tuple[str, dict[str, Any]]] = []
            for name, data in proxies.items():
                if isinstance(data, dict) and data.get("type") in {"Selector", "URLTest", "Fallback", "LoadBalance"}:
                    items.append((str(name), data))
            return items

        def proxy_delay_label(self, proxy_name: str) -> str:
            try:
                proxy = runtime.proxies().get(proxy_name)
            except Exception:
                proxy = None
            if not isinstance(proxy, dict):
                return "—"
            history = proxy.get("history") or []
            if isinstance(history, list) and history:
                latest = history[-1] if isinstance(history[-1], dict) else {}
                delay = latest.get("delay")
                if delay is not None:
                    try:
                        return f"{int(delay)} ms"
                    except Exception:
                        return f"{delay} ms"
            alive = proxy.get("alive")
            if alive is False:
                return "offline"
            return "—"

        def proxy_display_label(self, proxy_name: str) -> str:
            delay = self.proxy_delay_label(proxy_name)
            return proxy_name if delay == "—" else f"{proxy_name} · {delay}"

        def selector_options(self, data: dict[str, Any]) -> list[str]:
            seen: set[str] = set()
            options: list[str] = []

            def add(value: Any) -> None:
                name = str(value or "").strip()
                if not name or name in seen:
                    return
                seen.add(name)
                options.append(name)

            for item in data.get("all") or []:
                add(item)

            try:
                providers = runtime.proxy_providers()
            except Exception:
                providers = {}
            if isinstance(providers, dict):
                for provider in providers.values():
                    if not isinstance(provider, dict):
                        continue
                    for item in provider.get("proxies") or []:
                        if isinstance(item, dict):
                            add(item.get("name"))
                        else:
                            add(item)

            try:
                proxies = runtime.proxies()
            except Exception:
                proxies = {}
            if isinstance(proxies, dict):
                for name, proxy in proxies.items():
                    if isinstance(proxy, dict) and proxy.get("type") not in {"Selector", "URLTest", "Fallback", "LoadBalance"}:
                        add(name)
            return options

        def refresh(self) -> None:
            self.clear_groups()
            try:
                items = self.selector_items()
            except Exception as e:
                self.status.setText(f"Не удалось загрузить селекторы: {e}")
                return
            if not items:
                self.status.setText("Селекторов нет в live Mihomo. Проверь config.yaml и restart Mihomo.")
                return
            if self.mode.currentText() == "Плитки":
                self.render_tiles(items)
            else:
                self.render_lists(items)
            self.status.setText(f"Селекторов: {len(items)}")

        def render_lists(self, items: list[tuple[str, dict[str, Any]]]) -> None:
            for name, data in items:
                group = QGroupBox(name)
                row = QHBoxLayout(group)
                current = QLabel(f"Сейчас: {data.get('now', '—')}")
                current.setObjectName("muted")
                combo = QComboBox()
                all_names = self.selector_options(data)
                combo.addItems([self.proxy_display_label(x) for x in all_names])
                combo.setProperty("proxy_names", all_names)
                now = str(data.get("now") or "")
                if now in all_names:
                    combo.setCurrentIndex(all_names.index(now))
                apply = QPushButton("Выбрать")
                apply.setObjectName("primary")
                apply.clicked.connect(lambda _=False, g=name, c=combo: self.select(g, (c.property("proxy_names") or [c.currentText()])[c.currentIndex()] if c.currentIndex() >= 0 else c.currentText()))
                row.addWidget(current)
                row.addWidget(combo, 1)
                row.addWidget(apply)
                self.groups_box.addWidget(group)
            self.groups_box.addStretch(1)

        def render_tiles(self, items: list[tuple[str, dict[str, Any]]]) -> None:
            for name, data in items:
                group = QGroupBox(f"{name} · сейчас: {data.get('now', '—')}")
                grid = QGridLayout(group)
                all_names = self.selector_options(data)
                now = str(data.get("now") or "")
                for idx, proxy in enumerate(all_names):
                    btn = QPushButton(self.proxy_display_label(proxy))
                    btn.setMinimumHeight(40)
                    btn.setMaximumHeight(48)
                    if proxy == now:
                        btn.setObjectName("tileActive")
                    else:
                        btn.setObjectName("tile")
                    btn.clicked.connect(lambda _=False, g=name, p=proxy: self.select(g, p))
                    grid.addWidget(btn, idx // 5, idx % 5)
                self.groups_box.addWidget(group)
            self.groups_box.addStretch(1)

        def select(self, group: str, proxy: str) -> None:
            try:
                runtime.select_proxy(group, proxy)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Не удалось выбрать proxy:\n{e}")

        def update_providers(self) -> None:
            results = runtime.update_proxy_providers()
            ok = sum(1 for x in results if x.get("ok"))
            failed = len(results) - ok
            self.status.setText(f"Подписки обновлены: {ok}/{len(results)}" + (f" · ошибок: {failed}" if failed else ""))
            self.refresh()

        def ping_all(self) -> None:
            proxies = runtime.proxies()
            checked = 0
            ok = 0
            for name, data in proxies.items():
                if isinstance(data, dict) and data.get("type") not in {"Direct", "Reject", "Selector", "URLTest", "Fallback", "LoadBalance"}:
                    checked += 1
                    delay = runtime.delay(name)
                    if delay is not None:
                        ok += 1
                        data["history"] = [{"delay": delay}]
            self.status.setText(f"Пинги: {ok}/{checked}")
            self.refresh()

    class ConnectionsTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            top = QHBoxLayout()
            self.filter = QLineEdit()
            self.filter.setPlaceholderText("Фильтр по host/source/destination/proxy")
            self.filter.textChanged.connect(self.refresh)
            refresh = QPushButton("Обновить")
            refresh.clicked.connect(self.refresh)
            close = QPushButton("Разорвать выбранное")
            close.setObjectName("danger")
            close.clicked.connect(self.close_selected)
            top.addWidget(self.filter, 1)
            top.addWidget(close)
            top.addWidget(refresh)
            layout.addLayout(top)
            self.table = QTableWidget(0, 7)
            self.table.setHorizontalHeaderLabels(["ID", "Источник", "Назначение", "Host", "Proxy", "Upload", "Download"])
            self.table.setAlternatingRowColors(True)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            layout.addWidget(self.table, 1)
            self.status = QLabel("Живые соединения Mihomo. Логи ниже — история, эта вкладка показывает только активные сейчас.")
            self.status.setObjectName("muted")
            layout.addWidget(self.status)
            self.timer = QTimer(self)
            self.timer.setInterval(2000)
            self.timer.timeout.connect(self.refresh)
            self.timer.start()
            self.refresh()

        def refresh(self) -> None:
            flt = self.filter.text().strip().lower()
            rows = []
            try:
                data = runtime.connections_data()
            except Exception as exc:
                self.status.setText(f"Не удалось прочитать /connections: {exc}")
                self.table.setRowCount(0)
                return
            connections = data.get("connections")
            if not isinstance(connections, list):
                connections = []
            live_count = len(connections)
            showing_history = False
            if not connections:
                connections = runtime.connection_history_from_logs(limit=80)
                showing_history = bool(connections)
            for c in connections:
                if not isinstance(c, dict):
                    continue
                meta = c.get("metadata") or {}
                chains = c.get("chains") or []
                destination = meta.get("destinationIP") or meta.get("dstIP") or meta.get("remoteDestination") or ""
                port = meta.get("destinationPort") or meta.get("dstPort") or ""
                if port:
                    destination = f"{destination}:{port}" if destination else str(port)
                source = meta.get("sourceIP") or meta.get("sourceIPAddr") or meta.get("source") or ""
                source_port = meta.get("sourcePort") or meta.get("srcPort") or ""
                if source_port:
                    source = f"{source}:{source_port}" if source else str(source_port)
                row = [
                    str(c.get("id", "")),
                    str(source),
                    str(destination),
                    str(meta.get("host") or meta.get("destinationHost") or meta.get("network") or ""),
                    " → ".join(map(str, chains)),
                    human_bytes(c.get("upload")),
                    human_bytes(c.get("download")),
                ]
                if flt and flt not in " ".join(row).lower():
                    continue
                rows.append(row)
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for col, value in enumerate(row):
                    self.table.setItem(r, col, QTableWidgetItem(value))
            self.table.resizeColumnsToContents()
            upload = human_bytes(data.get("uploadTotal"))
            download = human_bytes(data.get("downloadTotal"))
            suffix = "" if not flt else f" · после фильтра: {len(rows)}"
            if showing_history:
                self.status.setText(f"Активных соединений: 0 · показана история из mihomo-native.log: {len(rows)}{suffix} · всего ↑ {upload} ↓ {download} · автообновление 2с")
            else:
                self.status.setText(f"Активных соединений: {live_count}{suffix} · всего ↑ {upload} ↓ {download} · автообновление 2с")

        def close_selected(self) -> None:
            row = self.table.currentRow()
            if row < 0:
                return
            conn_id = self.table.item(row, 0).text()
            if conn_id == "log":
                QMessageBox.information(self, APP_NAME, "Это строка истории из лога, активного соединения для разрыва уже нет.")
                return
            try:
                runtime.close_connection(conn_id)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Не удалось разорвать соединение:\n{e}")

    class ManualTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            self.editor = QPlainTextEdit()
            buttons = QHBoxLayout()
            save = QPushButton("Сохранить")
            save.setObjectName("primary")
            save.clicked.connect(self.save)
            reload_btn = QPushButton("Перечитать")
            reload_btn.clicked.connect(self.load)
            buttons.addStretch(1)
            buttons.addWidget(reload_btn)
            buttons.addWidget(save)
            self.summary = QLabel("")
            self.summary.setObjectName("muted")
            layout.addWidget(QLabel(str(runtime.manual_rules_path)))
            layout.addWidget(self.summary)
            layout.addWidget(self.editor, 1)
            layout.addLayout(buttons)
            self.load()

        def load(self) -> None:
            runtime.manual_rules_path.parent.mkdir(parents=True, exist_ok=True)
            if not runtime.manual_rules_path.exists():
                runtime.manual_rules_path.write_text("payload: []\n", encoding="utf-8")
            self.editor.setPlainText(runtime.manual_rules_path.read_text(encoding="utf-8"))
            try:
                groups = ", ".join(cfg_mgr.group_names()) or "—"
                providers = ", ".join(x.get("name", "") for x in cfg_mgr.proxy_provider_items()) or "—"
                self.summary.setText(f"Группы: {groups} · Подписки/providers: {providers}")
            except Exception:
                self.summary.setText("Группы/providers: не удалось прочитать config.yaml")

        def save(self) -> None:
            runtime.manual_rules_path.write_text(self.editor.toPlainText(), encoding="utf-8")
            QMessageBox.information(self, APP_NAME, "Ручной список сохранён. Для правил обычно достаточно перезапуска Mihomo.")

    class ConfigTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            top = QHBoxLayout()
            open_btn = QPushButton("Открыть файл…")
            open_btn.clicked.connect(self.open_file)
            validate_btn = QPushButton("Проверить")
            validate_btn.clicked.connect(self.validate)
            save = QPushButton("Сохранить без restart")
            save.clicked.connect(self.save_only)
            apply = QPushButton("Применить + restart")
            apply.setObjectName("primary")
            apply.clicked.connect(self.apply_restart)
            reload_btn = QPushButton("Перечитать active")
            reload_btn.clicked.connect(self.load)
            top.addWidget(open_btn)
            top.addWidget(validate_btn)
            top.addStretch(1)
            top.addWidget(reload_btn)
            top.addWidget(save)
            top.addWidget(apply)
            self.path_label = QLabel(str(runtime.config_path))
            self.path_label.setObjectName("muted")
            self.editor = QPlainTextEdit()
            self.status = QLabel("Готово")
            self.status.setObjectName("muted")
            layout.addWidget(self.path_label)
            layout.addLayout(top)
            layout.addWidget(self.editor, 1)
            layout.addWidget(self.status)
            self.load()

        def load(self) -> None:
            self.editor.setPlainText(cfg_mgr.read_config())
            self.status.setText(f"Загружен active config: {runtime.config_path}")

        def open_file(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Открыть Mihomo config", str(Path.home()), "YAML (*.yaml *.yml);;All files (*)")
            if not path:
                return
            self.editor.setPlainText(Path(path).read_text(encoding="utf-8"))
            self.status.setText(f"Открыт файл: {path}")

        def validate(self) -> None:
            ok, msg = cfg_mgr.validate_text(self.editor.toPlainText())
            self.status.setText(("OK: " if ok else "Ошибка: ") + msg[:500])
            if ok:
                QMessageBox.information(self, APP_NAME, "Config валиден. Mihomo принял `-t`.")
            else:
                QMessageBox.critical(self, APP_NAME, f"Config невалиден:\n\n{msg[:4000]}")

        def save_only(self) -> None:
            try:
                backup, msg = cfg_mgr.save_text(self.editor.toPlainText(), validate=True)
                self.status.setText(f"{msg}. Backup: {backup or 'нет'}")
                QMessageBox.information(self, APP_NAME, f"{msg}\nBackup: {backup or 'нет'}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Не удалось сохранить config:\n{e}")

        def apply_restart(self) -> None:
            try:
                backup, msg = cfg_mgr.save_and_restart(self.editor.toPlainText())
                self.status.setText(f"{msg}. Backup: {backup or 'нет'}")
                QMessageBox.information(self, APP_NAME, f"{msg}\nBackup: {backup or 'нет'}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Не удалось применить config:\n{e}")

    class ImportTab(QWidget):
        def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
            super().__init__()
            self.on_changed = on_changed
            layout = QVBoxLayout(self)
            title = QLabel("Импорт прокси / подписок")
            title.setObjectName("title")
            form = QHBoxLayout()
            self.kind = QComboBox()
            self.kind.addItems(["auto", "uri", "wireguard", "openvpn", "tailscale", "yaml", "subscription"])
            self.name = QLineEdit()
            self.name.setPlaceholderText("Имя прокси/provider (опционально)")
            self.group = QComboBox()
            self.group.setEditable(True)
            self.restart = QCheckBox("Применить и restart Mihomo")
            self.restart.setChecked(True)
            self.mirror_static = QCheckBox("Сразу добавить ноды в селекторы")
            self.mirror_static.setChecked(True)
            form.addWidget(QLabel("Формат:"))
            form.addWidget(self.kind)
            form.addWidget(QLabel("Имя:"))
            form.addWidget(self.name, 1)
            form.addWidget(QLabel("Группа:"))
            form.addWidget(self.group, 1)
            form.addWidget(self.restart)
            form.addWidget(self.mirror_static)
            buttons = QHBoxLayout()
            file_btn = QPushButton("Загрузить из файла…")
            file_btn.clicked.connect(self.load_file)
            preview_btn = QPushButton("Распознать")
            preview_btn.clicked.connect(self.preview)
            apply_btn = QPushButton("Импортировать")
            apply_btn.setObjectName("primary")
            apply_btn.clicked.connect(self.apply)
            buttons.addWidget(file_btn)
            buttons.addStretch(1)
            buttons.addWidget(preview_btn)
            buttons.addWidget(apply_btn)
            self.input = QPlainTextEdit()
            self.input.setPlaceholderText("Вставь vless:// / vmess:// / trojan:// / hysteria2://, WireGuard/AmneziaWG .conf, OpenVPN .ovpn, YAML proxy block/full config или subscription URL")
            self.preview_box = QPlainTextEdit()
            self.preview_box.setReadOnly(True)
            self.preview_box.setPlaceholderText("Здесь появится распознанный proxy YAML")
            self.status = QLabel("Поддержка: VLESS, VMess, Trojan, SS, Hysteria2, WireGuard/AmneziaWG, OpenVPN, Tailscale, YAML, subscription provider")
            self.status.setObjectName("muted")
            layout.addWidget(title)
            layout.addLayout(form)
            layout.addWidget(QLabel("Ввод:"))
            layout.addWidget(self.input, 2)
            layout.addLayout(buttons)
            layout.addWidget(QLabel("Preview:"))
            layout.addWidget(self.preview_box, 1)
            layout.addWidget(self.status)
            self.refresh_groups()

        def refresh_groups(self) -> None:
            current = self.group.currentText()
            self.group.clear()
            names = cfg_mgr.group_names()
            self.group.addItems(names)
            if current:
                self.group.setCurrentText(current)
            elif names:
                self.group.setCurrentText(names[0])

        def load_file(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Импортировать файл", str(Path.home()), "Configs (*.conf *.ovpn *.yaml *.yml *.txt);;All files (*)")
            if not path:
                return
            self.input.setPlainText(Path(path).read_text(encoding="utf-8", errors="ignore"))
            if not self.name.text().strip():
                self.name.setText(Path(path).stem)
            self.status.setText(f"Загружен файл: {path}")

        def _parse(self) -> list[ImportResult]:
            kind = self.kind.currentText().strip().lower()
            if kind == "subscription":
                return []
            return cfg_mgr.parse_import(self.input.toPlainText(), name=self.name.text().strip(), kind=kind)

        def preview(self) -> None:
            try:
                if self.kind.currentText().strip().lower() == "subscription":
                    url = self.input.toPlainText().strip()
                    name = self.name.text().strip() or "subscription_1"
                    imports = cfg_mgr.fetch_subscription_imports(url)
                    sample = "\n".join(f"  - {imp.name} ({imp.kind})" for imp in imports[:80])
                    more = "" if len(imports) <= 80 else f"\n  ... ещё {len(imports)-80}"
                    self.preview_box.setPlainText(f"proxy-providers:\n  {name}:\n    type: http\n    url: {url}\n    interval: 3600\n\n# Ноды подписки ({len(imports)}):\n{sample}{more}\n")
                    self.status.setText(f"Распознано нод подписки: {len(imports)}. Provider + ноды будут добавлены в выбранную группу.")
                    return
                imports = self._parse()
                self.preview_box.setPlainText("\n---\n".join(imp.yaml.strip() for imp in imports))
                self.status.setText(f"Распознано прокси: {', '.join(imp.name for imp in imports)}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Не удалось распознать импорт:\n{e}")

        def apply(self) -> None:
            try:
                if self.kind.currentText().strip().lower() == "subscription":
                    provider = self.name.text().strip()
                    group_text = self.group.currentText().strip()
                    groups = [group_text] if group_text else []
                    actual_provider, added_static, backup, msg = cfg_mgr.add_subscription_provider(
                        self.input.toPlainText().strip(),
                        provider,
                        groups=groups,
                        restart=self.restart.isChecked(),
                        mirror_static=self.mirror_static.isChecked(),
                    )
                    self.name.setText(actual_provider)
                    if added_static:
                        self.preview_box.setPlainText("Добавлены ноды в selectors/proxies:\n" + "\n".join(f"- {x}" for x in added_static))
                    self.status.setText(f"{msg}. Backup: {backup or 'нет'}")
                    QMessageBox.information(self, APP_NAME, f"{msg}\nBackup: {backup or 'нет'}")
                    self.refresh_groups()
                    if self.on_changed:
                        self.on_changed()
                    return
                imports = self._parse()
                group_text = self.group.currentText().strip()
                groups = [group_text] if group_text else []
                added, backup, msg = cfg_mgr.apply_imports(imports, groups, restart=self.restart.isChecked())
                self.preview_box.setPlainText("\n---\n".join(imp.yaml.strip() for imp in imports))
                self.status.setText(f"Добавлено: {', '.join(added)}. {msg}. Backup: {backup or 'нет'}")
                QMessageBox.information(self, APP_NAME, f"Добавлено: {', '.join(added)}\n{msg}\nBackup: {backup or 'нет'}")
                self.refresh_groups()
                if self.on_changed:
                    self.on_changed()
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Импорт не выполнен:\n{e}")

    class InventoryTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            top = QHBoxLayout()
            refresh = QPushButton("Обновить")
            refresh.clicked.connect(self.refresh)
            update = QPushButton("Обновить HTTP-подписки")
            update.clicked.connect(self.update_providers)
            top.addWidget(QLabel("Текущие конфиги, подписки, группы и ручные списки"))
            top.addStretch(1)
            top.addWidget(update)
            top.addWidget(refresh)
            layout.addLayout(top)
            self.providers = QTableWidget(0, 6)
            self.providers.setHorizontalHeaderLabels(["Provider", "Type", "URL/Path", "Cache path", "Interval", "Используется группами"])
            self.groups = QTableWidget(0, 4)
            self.groups.setHorizontalHeaderLabels(["Группа", "Type", "Proxies", "Use providers"])
            self.proxies = QTableWidget(0, 4)
            self.proxies.setHorizontalHeaderLabels(["Static proxy", "Type", "Server", "Port"])
            self.rules = QTableWidget(0, 4)
            self.rules.setHorizontalHeaderLabels(["Rule provider", "Type", "Behavior", "Path/URL"])
            for title, table in [
                ("Подписки / proxy-providers", self.providers),
                ("Группы / proxy-groups", self.groups),
                ("Статические proxies", self.proxies),
                ("Rule-providers / ручные списки", self.rules),
            ]:
                box = QGroupBox(title)
                box_layout = QVBoxLayout(box)
                table.setAlternatingRowColors(True)
                table.setSelectionBehavior(QTableWidget.SelectRows)
                box_layout.addWidget(table)
                layout.addWidget(box, 1)
            self.status = QLabel("Готово")
            self.status.setObjectName("muted")
            layout.addWidget(self.status)
            self.refresh()

        def fill_table(self, table: QTableWidget, rows: list[dict[str, Any]], keys: list[str]) -> None:
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, key in enumerate(keys):
                    table.setItem(r, c, QTableWidgetItem(str(row.get(key) or "")))
            table.resizeColumnsToContents()

        def refresh(self) -> None:
            try:
                self.fill_table(self.providers, cfg_mgr.proxy_provider_items(), ["name", "type", "url", "path", "interval", "used_by"])
                self.fill_table(self.groups, cfg_mgr.proxy_group_items(), ["name", "type", "proxies", "use"])
                self.fill_table(self.proxies, cfg_mgr.static_proxy_items(), ["name", "type", "server", "port"])
                self.fill_table(self.rules, cfg_mgr.rule_provider_items(), ["name", "type", "behavior", "path"])
                self.status.setText(f"Config: {runtime.config_path} · Manual: {runtime.manual_rules_path}")
            except Exception as e:
                self.status.setText(f"Ошибка чтения config.yaml: {e}")

        def update_providers(self) -> None:
            results = runtime.update_proxy_providers()
            ok = sum(1 for x in results if x.get("ok"))
            failed = len(results) - ok
            self.status.setText(f"HTTP-подписки обновлены: {ok}/{len(results)}" + (f" · ошибок: {failed}" if failed else ""))
            self.refresh()

    class LogsTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            buttons = QHBoxLayout()
            reload_btn = QPushButton("Обновить логи")
            reload_btn.clicked.connect(self.load)
            buttons.addStretch(1)
            buttons.addWidget(reload_btn)
            self.logs = QPlainTextEdit()
            self.logs.setReadOnly(True)
            layout.addWidget(QLabel(str(runtime.runtime / "logs")))
            layout.addLayout(buttons)
            layout.addWidget(self.logs, 1)
            self.load()

        def load(self) -> None:
            parts = []
            for name in ("native-app.log", "mihomo-native.log"):
                path = runtime.runtime / "logs" / name
                parts.append(f"===== {path} =====")
                if path.exists():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    parts.append("\n".join(text.splitlines()[-250:]))
                else:
                    parts.append("<нет файла>")
            self.logs.setPlainText("\n".join(parts))

    class DashboardTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            title = QLabel("Unified UI Native")
            title.setObjectName("title")
            self.version = QLabel("Mihomo: —")
            self.version.setObjectName("muted")
            self.traffic = QLabel("Traffic: —")
            self.traffic.setObjectName("muted")
            layout.addWidget(title)
            layout.addWidget(QLabel("Нативное Qt-приложение: без WebView, без Flask UI, прямой Mihomo API."))
            layout.addWidget(self.version)
            layout.addWidget(self.traffic)
            layout.addStretch(1)

        def refresh(self) -> None:
            self.version.setText(f"Mihomo: {runtime.version()}")
            self.traffic.setText("Traffic: потоковый счётчик будет подключён отдельным фоновым worker'ом")

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.resize(1320, 860)
            tabs = QTabWidget()
            self.dashboard = DashboardTab()
            self.selectors = SelectorsTab()
            self.connections = ConnectionsTab()
            self.manual = ManualTab()
            self.config = ConfigTab()
            self.inventory = InventoryTab()
            self.imports = ImportTab(on_changed=self.refresh_all)
            self.logs = LogsTab()
            tabs.addTab(self.dashboard, "Обзор")
            tabs.addTab(self.selectors, "Селекторы")
            tabs.addTab(self.connections, "Соединения")
            tabs.addTab(self.imports, "Импорт")
            tabs.addTab(self.inventory, "Конфиги/Подписки")
            tabs.addTab(self.manual, "Ручной список")
            tabs.addTab(self.config, "Конфиг")
            tabs.addTab(self.logs, "Логи")
            self.setCentralWidget(tabs)
            self.statusBar().showMessage(f"Runtime: {runtime.runtime}")
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh_light)
            self.timer.start(4000)
            self.refresh_all()

        def refresh_light(self) -> None:
            try:
                self.dashboard.refresh()
                self.connections.refresh()
            except Exception as e:
                self.statusBar().showMessage(str(e))

        def refresh_all(self) -> None:
            self.dashboard.refresh()
            self.selectors.refresh()
            self.connections.refresh()
            self.inventory.refresh()
            self.manual.load()
            self.config.load()

        def closeEvent(self, event) -> None:  # type: ignore[override]
            log_native_event("main window closeEvent")
            runtime.stop()
            event.accept()

    import threading
    import traceback

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(DARK_QSS)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda: log_native_event("app aboutToQuit"))

    startup = QWidget()
    startup.setWindowTitle(APP_NAME)
    startup.resize(520, 180)
    startup_layout = QVBoxLayout(startup)
    startup_title = QLabel("Unified UI Native")
    startup_title.setObjectName("title")
    startup_status = QLabel("Запускаю Mihomo runtime…")
    startup_status.setObjectName("muted")
    startup_layout.addWidget(startup_title)
    startup_layout.addWidget(QLabel("Окно приложения уже живое. Если Mihomo тупит — теперь это будет видно, а не чёрная магия без окна."))
    startup_layout.addWidget(startup_status)
    startup_layout.addStretch(1)
    startup.show()

    result: dict[str, Any] = {}
    holder: dict[str, Any] = {"window": None}

    def log_native_event(text: str) -> Path:
        log_dir = runtime.runtime / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "native-app.log"
        with path.open("a", encoding="utf-8") as f:
            f.write("\n=== Unified UI Native ===\n")
            f.write(text)
            f.write("\n")
        return path

    def log_native_error(text: str) -> Path:
        return log_native_event("STARTUP ERROR\n" + text)

    startup_log_path = log_native_event(f"startup begin; runtime={runtime.runtime}; controller={runtime.controller}")

    def excepthook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log_native_error("UNHANDLED EXCEPTION\n" + text)
        try:
            QMessageBox.critical(startup, APP_NAME, f"Необработанная ошибка.\n\nЛог: {startup_log_path}\n\n{text[-2500:]}")
        except Exception:
            pass

    sys.excepthook = excepthook

    def start_runtime_in_background() -> None:
        try:
            log_native_event("mihomo runtime start requested")
            runtime.start()
            log_native_event("mihomo runtime started successfully")
            result["ok"] = True
        except Exception:
            tb = traceback.format_exc()
            log_path = log_native_error(tb)
            result["error"] = tb
            result["log_path"] = str(log_path)

    threading.Thread(target=start_runtime_in_background, daemon=True).start()

    def poll_startup() -> None:
        if not result:
            return
        startup.timer.stop()  # type: ignore[attr-defined]
        if result.get("ok"):
            try:
                startup_status.setText("Mihomo готов. Открываю главное окно…")
                log_native_event("creating main window")
                win = MainWindow()
                holder["window"] = win
                win.show()
                win.raise_()
                win.activateWindow()
                app.setQuitOnLastWindowClosed(True)
                log_native_event("main window shown")
                startup.close()
                if gui_smoke_seconds is not None:
                    QTimer.singleShot(int(gui_smoke_seconds * 1000), app.quit)
            except Exception:
                tb = traceback.format_exc()
                log_path = log_native_error("MAIN WINDOW ERROR\n" + tb)
                startup_status.setText(f"Ошибка главного окна. Лог: {log_path}")
                QMessageBox.critical(startup, APP_NAME, f"Mihomo запущен, но главное окно не открылось.\n\nЛог: {log_path}\n\n{tb[-2500:]}")
            return
        msg = result.get("error", "Unknown startup error")
        log_path = result.get("log_path", str(runtime.runtime / "logs" / "native-app.log"))
        startup_status.setText(f"Ошибка запуска. Лог: {log_path}")
        QMessageBox.critical(startup, APP_NAME, f"Не удалось запустить Mihomo runtime.\n\nЛог: {log_path}\n\n{msg[-2500:]}")

    startup.timer = QTimer(startup)  # type: ignore[attr-defined]
    startup.timer.timeout.connect(poll_startup)  # type: ignore[attr-defined]
    startup.timer.start(250)  # type: ignore[attr-defined]
    return app.exec()


def run_smoke(runtime: MihomoRuntime) -> int:
    runtime.start()
    try:
        result = {
            "ok": True,
            "controller": runtime.controller,
            "version": runtime.version(),
            "proxy_count": len(runtime.proxies()),
            "connection_count": len(runtime.connections()),
            "config": str(runtime.config_path),
            "manual_rules": str(runtime.manual_rules_path),
            "webview": False,
            "flask_ui": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--gui-smoke", type=float, default=None, metavar="SECONDS", help="Open the real GUI, keep it alive for N seconds, then exit")
    args = parser.parse_args()
    runtime = MihomoRuntime.create()
    if args.smoke:
        return run_smoke(runtime)
    return run_gui(runtime, gui_smoke_seconds=args.gui_smoke)


if __name__ == "__main__":
    # urllib.parse is only needed at runtime in methods above; import here keeps top-level audit simple.
    import urllib.parse

    raise SystemExit(main())
