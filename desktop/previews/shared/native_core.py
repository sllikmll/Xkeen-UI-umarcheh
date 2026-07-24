#!/usr/bin/env python3
"""Non-Qt runtime/config core for Unified UI desktop user-test builds.

This module intentionally contains no PySide/Qt imports. It is extracted from
`desktop/native/unified_ui_native.py` so Avalonia/WPF/C++ candidates can reuse
runtime/config/import behavior without depending on the Qt application module.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
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
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

MIHOMO_VERSION = "1.19.29"
APP_NAME = "Unified UI Native"
APP_VERSION = "2.6.7"
APP_RELEASE_LABEL = f"v{APP_VERSION}-native"
DEFAULT_CONTROLLER_PORT = int(os.environ.get("MIHOMO_CONTROLLER_PORT", "19190"))
DEFAULT_MIXED_PORT = int(os.environ.get("MIHOMO_MIXED_PORT", "17990"))
DEFAULT_DNS_PORT = int(os.environ.get("MIHOMO_DNS_PORT", "15354"))

REPO_ROOT = Path(__file__).resolve().parents[3]
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
except Exception as exc:  # surfaced through bridge diagnostics/fallbacks
    ProxyParseResult = Any  # type: ignore
    _WEB_PARSER_IMPORT_ERROR = exc
else:
    _WEB_PARSER_IMPORT_ERROR = None

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
tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  dns-hijack:
    - any:53
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
            changed = self._normalize_runtime_config_data(data)
            changed = self.ensure_all_selectors_have_all_nodes(data) or changed
            if changed:
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

    @staticmethod
    def selectable_options_for_group(config: dict[str, Any], group_name: str, live_selector: dict[str, Any], providers: dict[str, Any] | None = None) -> list[str]:
        seen: set[str] = set()
        options: list[str] = []

        def add(value: Any) -> None:
            name = str(value or "").strip()
            if not name or name in seen:
                return
            seen.add(name)
            options.append(name)

        for item in live_selector.get("all") or []:
            add(item)

        group_cfg: dict[str, Any] = {}
        for group in (config or {}).get("proxy-groups") or []:
            if isinstance(group, dict) and str(group.get("name") or "") == group_name:
                group_cfg = group
                break

        for item in group_cfg.get("proxies") or []:
            add(item)

        configured_providers = {str(item) for item in (group_cfg.get("use") or [])}
        if configured_providers and isinstance(providers, dict):
            for provider_name, provider in providers.items():
                if str(provider_name) not in configured_providers or not isinstance(provider, dict):
                    continue
                for item in provider.get("proxies") or []:
                    add(item.get("name") if isinstance(item, dict) else item)

        return options

    def config_data(self) -> dict[str, Any]:
        return self._load_yaml_dict(self.read_config())

    def ensure_all_selectors_have_all_nodes(self, data: dict[str, Any]) -> bool:
        changed = False
        provider_names = [str(name) for name in (data.get("proxy-providers") or {}).keys()] if isinstance(data.get("proxy-providers"), dict) else []
        proxy_names = [str(item.get("name")) for item in (data.get("proxies") or []) if isinstance(item, dict) and str(item.get("name") or "").strip()]
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            if str(group.get("type") or "").lower() not in {"select", "url-test", "fallback", "load-balance"}:
                continue
            group_name = str(group.get("name") or "")
            proxies = group.get("proxies")
            if proxies is None:
                proxies = []
                group["proxies"] = proxies
                changed = True
            if isinstance(proxies, list):
                for proxy_name in proxy_names:
                    if proxy_name != group_name and proxy_name not in proxies:
                        proxies.append(proxy_name)
                        changed = True
            use = group.get("use")
            if use is None:
                use = []
                group["use"] = use
                changed = True
            if isinstance(use, list):
                for provider_name in provider_names:
                    if provider_name not in use:
                        use.append(provider_name)
                        changed = True
        return changed

    def save_config_data(self, data: dict[str, Any], *, restart: bool = True) -> tuple[Path | None, str]:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=140)
        backup, msg = self.save_text(text, validate=True)
        if restart:
            self.runtime.restart()
            msg += "; Mihomo перезапущен"
        return backup, msg

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

        tun = data.get("tun")
        if not isinstance(tun, dict):
            tun = {}
            data["tun"] = tun
            changed = True
        desired_tun = {
            "enable": True,
            "stack": "system",
            "auto-route": True,
            "auto-detect-interface": True,
            "dns-hijack": ["any:53"],
        }
        for key, value in desired_tun.items():
            if tun.get(key) != value:
                tun[key] = value
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
        changed = self.ensure_all_selectors_have_all_nodes(data) or changed
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

    def update_subscription_provider(self, old_name: str, *, new_name: str, url: str, interval: int, restart: bool = True) -> tuple[Path | None, str]:
        old_name = str(old_name or "").strip()
        new_name = str(new_name or "").strip() or old_name
        url = str(url or "").strip()
        if not old_name:
            raise ValueError("Не выбран provider")
        if not url.startswith(("http://", "https://")):
            raise ValueError("Subscription URL должен начинаться с http:// или https://")
        data = self._load_yaml_dict(self.read_config())
        providers = data.get("proxy-providers")
        if not isinstance(providers, dict) or old_name not in providers:
            raise ValueError(f"Provider `{old_name}` не найден")
        if new_name != old_name and new_name in providers:
            raise ValueError(f"Provider `{new_name}` уже существует")
        target_groups: list[str] = []
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("name") or "").strip()
            use = group.get("use")
            if gname and isinstance(use, list) and old_name in {str(item) for item in use}:
                target_groups.append(gname)
        provider_raw = providers.pop(old_name)
        provider: dict[str, Any] = dict(provider_raw) if isinstance(provider_raw, dict) else {"type": "http"}
        removed_static = self._remove_subscription_mirrors(data, old_name, provider)
        provider["type"] = "http"
        provider["url"] = url
        provider["interval"] = int(interval)
        provider.setdefault("path", f"./providers/{new_name}.yaml")
        old_path = str(provider.get("path") or "")
        if old_path.endswith(f"/{old_name}.yaml") or old_path == f"./providers/{old_name}.yaml":
            provider["path"] = f"./providers/{new_name}.yaml"
        provider.setdefault("health-check", {"enable": True, "url": "https://www.gstatic.com/generate_204", "interval": 300})
        providers[new_name] = provider
        if new_name != old_name:
            for group in data.get("proxy-groups") or []:
                if not isinstance(group, dict):
                    continue
                use = group.get("use")
                if isinstance(use, list):
                    group["use"] = [new_name if str(item) == old_name else item for item in use]
        added_static: list[str] = []
        mirror_error = ""
        try:
            imports = self.fetch_subscription_imports(url)
            added_static = self._append_imports_to_data(data, imports, target_groups, origin_provider=new_name)
        except Exception as exc:
            mirror_error = str(exc)
        backup, msg = self.save_config_data(data, restart=restart)
        suffix = f"; старые зеркальные static proxies удалены: {len(removed_static)}"
        if added_static:
            suffix += f"; новые добавлены: {len(added_static)}"
        elif mirror_error:
            suffix += f"; новые ноды не удалось зеркалировать: {mirror_error}"
        return backup, f"Provider `{old_name}` обновлён как `{new_name}`{suffix}; {msg}"

    def delete_subscription_provider(self, name: str, *, restart: bool = True) -> tuple[Path | None, str]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Не выбран provider")
        data = self._load_yaml_dict(self.read_config())
        providers = data.get("proxy-providers")
        if not isinstance(providers, dict) or name not in providers:
            raise ValueError(f"Provider `{name}` не найден")
        provider = providers.pop(name, None)
        removed_static = self._remove_subscription_mirrors(data, name, provider if isinstance(provider, dict) else None)
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            use = group.get("use")
            if isinstance(use, list):
                group["use"] = [item for item in use if str(item) != name]
        backup, msg = self.save_config_data(data, restart=restart)
        return backup, f"Provider `{name}` удалён; зеркальные static proxies удалены: {len(removed_static)}; {msg}"

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
        used_by: dict[str, list[str]] = {}
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("name") or "")
            for proxy_name in group.get("proxies") or []:
                used_by.setdefault(str(proxy_name), []).append(gname)
        for proxy in data.get("proxies") or []:
            if isinstance(proxy, dict):
                name = str(proxy.get("name") or "")
                extra = []
                for key in ("ip", "private-key", "public-key", "pre-shared-key", "dns", "allowed-ips", "remote-dns-resolve", "persistent-keepalive"):
                    if proxy.get(key) not in (None, "", []):
                        value = proxy.get(key)
                        if "key" in key:
                            value = "***"
                        extra.append(f"{key}={value}")
                items.append({
                    "name": name,
                    "type": str(proxy.get("type") or ""),
                    "server": str(proxy.get("server") or ""),
                    "port": str(proxy.get("port") or ""),
                    "used_by": ", ".join(used_by.get(name, [])),
                    "details": "; ".join(extra),
                })
        return items

    def static_proxy_config(self, name: str) -> dict[str, Any]:
        name = str(name or "").strip()
        data = self._load_yaml_dict(self.read_config())
        for proxy in data.get("proxies") or []:
            if isinstance(proxy, dict) and str(proxy.get("name") or "") == name:
                return dict(proxy)
        raise ValueError(f"Static proxy `{name}` не найден")

    def update_static_proxy(self, old_name: str, proxy: dict[str, Any], *, restart: bool = True) -> tuple[Path | None, str]:
        old_name = str(old_name or "").strip()
        if not old_name:
            raise ValueError("Не выбран static proxy")
        if not isinstance(proxy, dict) or not str(proxy.get("name") or "").strip():
            raise ValueError("Proxy YAML должен быть объектом с полем `name`")
        new_name = str(proxy.get("name") or "").strip()
        data = self._load_yaml_dict(self.read_config())
        proxies = data.get("proxies")
        if not isinstance(proxies, list):
            raise ValueError("proxies должен быть списком")
        found = False
        for idx, item in enumerate(proxies):
            if isinstance(item, dict) and str(item.get("name") or "") == old_name:
                proxies[idx] = proxy
                found = True
                break
        if not found:
            raise ValueError(f"Static proxy `{old_name}` не найден")
        if new_name != old_name:
            for item in proxies:
                if isinstance(item, dict) and item is not proxy and str(item.get("name") or "") == new_name:
                    raise ValueError(f"Static proxy `{new_name}` уже существует")
            for group in data.get("proxy-groups") or []:
                if not isinstance(group, dict):
                    continue
                group_proxies = group.get("proxies")
                if isinstance(group_proxies, list):
                    group["proxies"] = [new_name if str(item) == old_name else item for item in group_proxies]
        backup, msg = self.save_config_data(data, restart=restart)
        return backup, f"Static proxy `{old_name}` обновлён как `{new_name}`; {msg}"

    def delete_static_proxy(self, name: str, *, restart: bool = True) -> tuple[Path | None, str]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Не выбран static proxy")
        data = self._load_yaml_dict(self.read_config())
        proxies = data.get("proxies")
        if not isinstance(proxies, list):
            raise ValueError("proxies должен быть списком")
        before = len(proxies)
        data["proxies"] = [item for item in proxies if not (isinstance(item, dict) and str(item.get("name") or "") == name)]
        if len(data["proxies"]) == before:
            raise ValueError(f"Static proxy `{name}` не найден")
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            group_proxies = group.get("proxies")
            if isinstance(group_proxies, list):
                group["proxies"] = [item for item in group_proxies if str(item) != name]
        backup, msg = self.save_config_data(data, restart=restart)
        return backup, f"Static proxy `{name}` удалён; {msg}"

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
        uri_kinds = {"auto", "uri", "link", "vless", "vmess", "trojan", "hysteria2", "hy2", "wireguard", "amneziawg", "awg", "naiveproxy", "mieru", "ss", "shadowsocks"}
        if kind_l in uri_kinds and uri_lines and len(uri_lines) > 1:
            return [self._parse_single_uri(line, name if len(uri_lines) == 1 else "") for line in uri_lines]

        first_line = raw.splitlines()[0]
        if kind_l in uri_kinds and "://" in first_line:
            scheme = first_line.split(":", 1)[0].strip().lower()
            aliases = {"amneziawg": "wireguard", "awg": "wireguard", "hy2": "hysteria2"}
            expected = aliases.get(kind_l, kind_l)
            if kind_l in {"auto", "uri", "link"} or scheme == expected or (expected == "wireguard" and scheme == "wireguard"):
                return [self._parse_single_uri(raw, name)]
            raise ValueError(f"Ожидался URI протокола `{kind_l}`, а получен `{scheme}://`")

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

    def _provider_cache_path(self, provider: dict[str, Any] | None) -> Path | None:
        if not isinstance(provider, dict):
            return None
        raw_path = str(provider.get("path") or "").strip()
        if not raw_path:
            return None
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.config_path.parent / raw_path
        try:
            return path.resolve()
        except Exception:
            return path

    def _imports_from_provider_cache(self, provider: dict[str, Any] | None) -> list[ImportResult]:
        path = self._provider_cache_path(provider)
        if not path or not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            data = yaml.safe_load(raw)
            proxies = data.get("proxies") if isinstance(data, dict) else data
            if not isinstance(proxies, list):
                return []
            imports: list[ImportResult] = []
            for item in proxies:
                if isinstance(item, dict) and str(item.get("name") or "").strip():
                    imports.append(ImportResult(
                        name=str(item.get("name") or ""),
                        yaml=yaml.safe_dump([item], allow_unicode=True, sort_keys=False, width=140),
                        kind=str(item.get("type") or "yaml"),
                        source="provider-cache",
                    ))
            return imports
        except Exception:
            return []

    def _imports_from_provider_definition(self, provider: dict[str, Any] | None) -> list[ImportResult]:
        imports = self._imports_from_provider_cache(provider)
        if imports:
            return imports
        url = str((provider or {}).get("url") or "").strip() if isinstance(provider, dict) else ""
        if url.startswith(("http://", "https://")):
            try:
                return self.fetch_subscription_imports(url)
            except Exception:
                return []
        return []

    def _subscription_mirror_proxy_names(self, data: dict[str, Any], provider_name: str, provider: dict[str, Any] | None = None) -> list[str]:
        provider_name = str(provider_name or "").strip()
        names: set[str] = set()
        for proxy in data.get("proxies") or []:
            if not isinstance(proxy, dict):
                continue
            origin = proxy.get("x-unified-ui-origin")
            if isinstance(origin, dict) and origin.get("kind") == "subscription-mirror" and str(origin.get("provider") or "") == provider_name:
                name = str(proxy.get("name") or "").strip()
                if name:
                    names.add(name)
        # Backward compatibility for 2.6.5 configs: mirrored proxies did not carry origin metadata yet.
        # Infer only exact names from the provider cache/current subscription definition.
        for imp in self._imports_from_provider_definition(provider):
            if imp.name:
                names.add(str(imp.name))
        existing = {str(p.get("name") or "") for p in data.get("proxies") or [] if isinstance(p, dict)}
        return [name for name in names if name in existing]

    def _remove_static_proxies_by_names(self, data: dict[str, Any], names: list[str] | set[str]) -> list[str]:
        remove = {str(name) for name in names if str(name)}
        if not remove:
            return []
        proxies = data.get("proxies")
        if not isinstance(proxies, list):
            return []
        removed: list[str] = []
        kept = []
        for proxy in proxies:
            if isinstance(proxy, dict) and str(proxy.get("name") or "") in remove:
                removed.append(str(proxy.get("name") or ""))
                continue
            kept.append(proxy)
        data["proxies"] = kept
        removed_set = set(removed)
        for group in data.get("proxy-groups") or []:
            if not isinstance(group, dict):
                continue
            group_proxies = group.get("proxies")
            if isinstance(group_proxies, list):
                group["proxies"] = [item for item in group_proxies if str(item) not in removed_set]
        return removed

    def _remove_subscription_mirrors(self, data: dict[str, Any], provider_name: str, provider: dict[str, Any] | None = None) -> list[str]:
        names = self._subscription_mirror_proxy_names(data, provider_name, provider)
        return self._remove_static_proxies_by_names(data, names)

    def _append_imports_to_data(self, data: dict[str, Any], imports: list[ImportResult], target_groups: list[str], origin_provider: str = "") -> list[str]:
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
            if origin_provider:
                proxy["x-unified-ui-origin"] = {"kind": "subscription-mirror", "provider": origin_provider}
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
            target_groups = self._selected_or_all_selector_groups(data, [])
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
                added_static = self._append_imports_to_data(data, imports, list(target_groups), origin_provider=name)
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

    @property
    def dns_routes_path(self) -> Path:
        return self.runtime / "dns-routes.json"

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
        tail = ""
        log_path = logs / "mihomo-native.log"
        try:
            if log_path.exists():
                tail = "\n\nПоследние строки mihomo-native.log:\n" + "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
        except Exception:
            tail = ""
        self.force_cleanup_processes(delayed=False)
        raise RuntimeError(f"Mihomo controller did not become ready; see {log_path}{tail}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def force_cleanup_processes(self, *, delayed: bool = False) -> None:
        """Best-effort cleanup for the child Mihomo runtime.

        Do not globally taskkill `Unified UI Native.exe` or every `mihomo.exe` on
        normal close. A delayed global taskkill can race with a quick relaunch
        and leave a visible app window without the Mihomo child process.
        """
        pid = self.proc.pid if self.proc else None
        try:
            self.stop()
        except Exception:
            pass
        if platform.system().lower() != "windows" or pid is None:
            return
        try:
            if delayed:
                cmd = f'cmd /c "timeout /t 1 /nobreak >nul 2>nul & taskkill /F /PID {pid} >nul 2>nul"'
                subprocess.Popen(cmd, shell=True, **self._subprocess_window_kwargs())
            else:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **self._subprocess_window_kwargs())
        except Exception:
            pass

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

    def rule_providers(self) -> dict[str, Any]:
        data = self.get("/providers/rules")
        return data.get("providers", {}) if isinstance(data, dict) else {}

    def update_rule_providers(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            providers = self.rule_providers()
        except Exception as exc:
            return [{"ok": False, "provider": "<all>", "error": str(exc)}]
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            if str(provider.get("vehicleType") or provider.get("type") or "").upper() not in {"HTTP", "FILE"}:
                continue
            quoted = urllib.parse.quote(str(name), safe="")
            try:
                self._request("PUT", f"/providers/rules/{quoted}")
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

