#!/usr/bin/env python3
"""Unified UI Native production bridge for Windows desktop candidates.

The bridge exposes the proven Qt Native runtime/config layer as a small local
JSON API. Avalonia, WPF, and C++ Win32 clients can share one implementation
instead of each reimplementing Mihomo/config/import logic differently.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import traceback
import urllib.parse
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import desktop.native.unified_ui_native as native_mod  # noqa: E402
from desktop.native.unified_ui_native import (  # noqa: E402
    APP_NAME,
    APP_RELEASE_LABEL,
    ImportResult,
    MihomoRuntime,
    NativeConfigManager,
)

if not hasattr(native_mod, "ensure_leading_dash_for_yaml_block"):
    def _ensure_leading_dash_for_yaml_block(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        if raw.startswith("-"):
            return raw
        return "- " + raw.replace("\n", "\n  ")

    native_mod.ensure_leading_dash_for_yaml_block = _ensure_leading_dash_for_yaml_block

BRIDGE_VERSION = "0.3.0"
DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 19191
PRODUCTION_FEATURES = [
    "runtime-start-stop-restart",
    "mihomo-version-health",
    "selector-list-and-tiles",
    "select-proxy",
    "per-node-ping",
    "proxy-table",
    "provider-update",
    "connections-table",
    "close-connection",
    "config-read-save-validate",
    "subscription-add-update-delete",
    "static-proxy-import-update-delete",
    "rule-providers",
    "dns-routes-manual-resolver",
    "logs-viewer",
    "settings-runtime-paths",
]


@dataclass
class BridgeState:
    runtime: MihomoRuntime
    manager: NativeConfigManager

    @classmethod
    def create(cls, runtime_dir: Path | None = None) -> "BridgeState":
        if runtime_dir is None:
            runtime = MihomoRuntime.create()
        else:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            runtime = MihomoRuntime(runtime=runtime_dir, controller="http://127.0.0.1:19190")
        return cls(runtime=runtime, manager=NativeConfigManager(runtime))

    def status(self) -> dict[str, Any]:
        running = bool(self.runtime.proc and self.runtime.proc.poll() is None)
        return {
            "ok": True,
            "app": APP_NAME,
            "app_release": APP_RELEASE_LABEL,
            "bridge_version": BRIDGE_VERSION,
            "features": PRODUCTION_FEATURES,
            "runtime_dir": str(self.runtime.runtime),
            "config_path": str(self.runtime.config_path),
            "manual_rules_path": str(self.runtime.manual_rules_path),
            "dns_routes_path": str(self.runtime.dns_routes_path),
            "controller": self.runtime.controller,
            "mihomo_running": running,
            "pid": self.runtime.proc.pid if running and self.runtime.proc else None,
        }


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def _resolve_domains(raw: str) -> list[dict[str, Any]]:
    domains = [x.strip() for x in raw.replace(",", "\n").replace(";", "\n").splitlines() if x.strip()]
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for domain in domains:
        if domain in seen:
            continue
        seen.add(domain)
        try:
            infos = socket.getaddrinfo(domain, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
            ips = sorted({item[4][0] for item in infos})
            results.append({"domain": domain, "ok": True, "ips": ips})
        except Exception as exc:
            results.append({"domain": domain, "ok": False, "error": str(exc), "ips": []})
    return results


def _fallback_parse_import(text: str, *, name: str = "") -> list[ImportResult]:
    """Small production bridge fallback when optional web parser modules are absent.

    The full Qt app uses richer web-service parsers when present. The packaged
    bridge must still support common user inputs instead of crashing: proxy YAML,
    full Mihomo YAML, and the most common URI schemes.
    """
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Пустой импорт")

    def from_proxy_dict(item: dict[str, Any], source: str) -> ImportResult:
        proxy_name = str(item.get("name") or name or item.get("server") or "Imported Proxy")
        item = dict(item)
        item["name"] = proxy_name
        return ImportResult(name=proxy_name, yaml=yaml.safe_dump([item], allow_unicode=True, sort_keys=False), kind=str(item.get("type") or "yaml"), source=source)

    try:
        data = yaml.safe_load(raw)
        if isinstance(data, dict) and isinstance(data.get("proxies"), list):
            imports = [from_proxy_dict(item, "mihomo-yaml") for item in data["proxies"] if isinstance(item, dict) and item.get("name")]
            if imports:
                return imports
        if isinstance(data, list):
            imports = [from_proxy_dict(item, "proxy-yaml") for item in data if isinstance(item, dict) and item.get("name")]
            if imports:
                return imports
        if isinstance(data, dict) and data.get("name"):
            return [from_proxy_dict(data, "proxy-yaml")]
    except Exception:
        pass

    line = next((x.strip() for x in raw.splitlines() if "://" in x and not x.strip().startswith("#")), raw)
    parsed = urllib.parse.urlparse(line)
    scheme = parsed.scheme.lower()
    qs = {k: urllib.parse.unquote(v[-1]) for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()}
    proxy_name = name or urllib.parse.unquote(parsed.fragment or "") or parsed.hostname or "Imported Proxy"
    host = parsed.hostname or ""
    port = int(parsed.port or (443 if scheme in {"vless", "trojan", "hysteria2", "hy2"} else 0))
    if scheme == "vless":
        proxy = {"name": proxy_name, "type": "vless", "server": host, "port": port, "uuid": urllib.parse.unquote(parsed.username or ""), "network": qs.get("type", "tcp"), "udp": True}
        if qs.get("security") in {"tls", "reality"}:
            proxy["tls"] = True
            if qs.get("sni"):
                proxy["servername"] = qs["sni"]
        if qs.get("security") == "reality":
            proxy["reality-opts"] = {"public-key": qs.get("pbk", ""), "short-id": qs.get("sid", "")}
            if qs.get("fp"):
                proxy["client-fingerprint"] = qs["fp"]
        return [from_proxy_dict(proxy, "vless-uri-fallback")]
    if scheme == "trojan":
        proxy = {"name": proxy_name, "type": "trojan", "server": host, "port": port, "password": urllib.parse.unquote(parsed.username or ""), "udp": True, "sni": qs.get("sni", host)}
        return [from_proxy_dict(proxy, "trojan-uri-fallback")]
    if scheme in {"hysteria2", "hy2"}:
        proxy = {"name": proxy_name, "type": "hysteria2", "server": host, "port": port, "password": urllib.parse.unquote(parsed.username or qs.get("password", "")), "sni": qs.get("sni", host)}
        return [from_proxy_dict(proxy, "hysteria2-uri-fallback")]
    if scheme == "ss":
        proxy = {"name": proxy_name, "type": "ss", "server": host, "port": port, "cipher": qs.get("method", "auto"), "password": urllib.parse.unquote(parsed.username or "")}
        return [from_proxy_dict(proxy, "ss-uri-fallback")]
    raise ValueError("Не понял формат. Поддерживаются URI VLESS/Trojan/Hysteria2/SS и proxy/full Mihomo YAML.")


def _parse_imports_with_fallback(manager: NativeConfigManager, text: str) -> list[ImportResult]:
    try:
        return manager.parse_import(text)
    except RuntimeError as exc:
        if "services" not in str(exc) and "web-парсеры" not in str(exc):
            raise
        return _fallback_parse_import(text)


class BridgeHandler(BaseHTTPRequestHandler):
    state: BridgeState

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
        if getattr(self.server, "verbose", False):  # type: ignore[attr-defined]
            super().log_message(fmt, *args)

    def _ok(self, payload: Any) -> None:
        _json_response(self, 200, payload)

    def _error(self, exc: Exception, status: int = 500) -> None:
        _json_response(self, status, {"ok": False, "error": str(exc), "traceback": traceback.format_exc(limit=8)})

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)
            s = self.state
            if path in {"/", "/api/status", "/api/smoke"}:
                self._ok(s.status())
            elif path == "/api/mihomo/version":
                self._ok({"ok": True, "version": s.runtime.version()})
            elif path == "/api/proxies":
                self._ok({"ok": True, "proxies": s.runtime.proxies()})
            elif path == "/api/providers/proxies":
                self._ok({"ok": True, "providers": s.runtime.proxy_providers(), "configured": s.manager.proxy_provider_items()})
            elif path == "/api/providers/rules":
                self._ok({"ok": True, "providers": s.runtime.rule_providers(), "configured": s.manager.rule_provider_items()})
            elif path == "/api/connections":
                data = s.runtime.connections_data()
                self._ok({"ok": True, "data": data, "history": s.runtime.connection_history_from_logs(limit=80) if not data.get("connections") else []})
            elif path == "/api/config":
                self._ok({"ok": True, "path": str(s.runtime.config_path), "text": s.manager.read_config(), "data": s.manager.config_data()})
            elif path == "/api/inventory":
                self._ok({
                    "ok": True,
                    "proxy_providers": s.manager.proxy_provider_items(),
                    "proxy_groups": s.manager.proxy_group_items(),
                    "static_proxies": s.manager.static_proxy_items(),
                    "rule_providers": s.manager.rule_provider_items(),
                    "groups": s.manager.group_names(),
                })
            elif path == "/api/logs":
                log_path = s.runtime.runtime / "logs" / "mihomo-native.log"
                text = log_path.read_text(encoding="utf-8", errors="replace")[-20000:] if log_path.exists() else ""
                self._ok({"ok": True, "path": str(log_path), "text": text})
            elif path == "/api/dns/resolve":
                raw = "\n".join(qs.get("domain", []) + qs.get("domains", []))
                self._ok({"ok": True, "results": _resolve_domains(raw)})
            else:
                self._error(ValueError(f"Unknown GET endpoint: {path}"), 404)
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            body = _read_json(self)
            s = self.state
            if path == "/api/runtime/start":
                s.runtime.start()
                self._ok({"ok": True, "status": s.status()})
            elif path == "/api/runtime/stop":
                s.runtime.stop()
                self._ok({"ok": True, "status": s.status()})
            elif path == "/api/runtime/restart":
                s.runtime.restart()
                self._ok({"ok": True, "status": s.status()})
            elif path == "/api/config/save":
                backup, msg = s.manager.save_text(str(body.get("text") or ""), validate=bool(body.get("validate", True)))
                self._ok({"ok": True, "message": msg, "backup": str(backup) if backup else None})
            elif path == "/api/config/apply":
                backup, msg = s.manager.save_and_restart(str(body.get("text") or ""))
                self._ok({"ok": True, "message": msg, "backup": str(backup) if backup else None})
            elif path == "/api/proxy/select":
                s.runtime.select_proxy(str(body.get("group") or ""), str(body.get("proxy") or ""))
                self._ok({"ok": True})
            elif path == "/api/proxy/delay":
                delay = s.runtime.delay(str(body.get("proxy") or ""))
                self._ok({"ok": True, "delay": delay})
            elif path == "/api/connections/close":
                s.runtime.close_connection(str(body.get("id") or ""))
                self._ok({"ok": True})
            elif path == "/api/providers/proxies/update":
                self._ok({"ok": True, "results": s.runtime.update_proxy_providers()})
            elif path == "/api/providers/rules/update":
                self._ok({"ok": True, "results": s.runtime.update_rule_providers()})
            elif path == "/api/subscription/add":
                name, added, backup, msg = s.manager.add_subscription_provider(
                    str(body.get("url") or ""),
                    name=str(body.get("name") or ""),
                    interval=int(body.get("interval") or 3600),
                    groups=body.get("groups") if isinstance(body.get("groups"), list) else None,
                    restart=bool(body.get("restart", False)),
                    mirror_static=bool(body.get("mirror_static", True)),
                    subscription_text=body.get("subscription_text") if isinstance(body.get("subscription_text"), str) else None,
                )
                self._ok({"ok": True, "provider": name, "added_static": added, "backup": str(backup) if backup else None, "message": msg})
            elif path == "/api/import/static":
                raw = str(body.get("text") or "")
                imports = _parse_imports_with_fallback(s.manager, raw)
                added, backup, msg = s.manager.apply_imports(imports, groups=body.get("groups") if isinstance(body.get("groups"), list) else None, restart=bool(body.get("restart", False)))
                self._ok({"ok": True, "added": added, "backup": str(backup) if backup else None, "message": msg})
            elif path == "/api/dns/resolve":
                self._ok({"ok": True, "results": _resolve_domains(str(body.get("domains") or body.get("text") or ""))})
            else:
                self._error(ValueError(f"Unknown POST endpoint: {path}"), 404)
        except Exception as exc:
            self._error(exc)


def make_server(state: BridgeState, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT, verbose: bool = False) -> ThreadingHTTPServer:
    class Handler(BridgeHandler):
        pass

    Handler.state = state
    server = ThreadingHTTPServer((host, port), Handler)
    server.verbose = verbose  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_BRIDGE_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    state = BridgeState.create(args.runtime_dir)
    if args.smoke:
        print(json.dumps(state.status(), ensure_ascii=False, indent=2))
        return 0
    server = make_server(state, args.host, args.port, args.verbose)
    print(json.dumps({"ok": True, "bridge": f"http://{args.host}:{args.port}", "status": state.status()}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            state.runtime.stop()
        except Exception:
            pass
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
