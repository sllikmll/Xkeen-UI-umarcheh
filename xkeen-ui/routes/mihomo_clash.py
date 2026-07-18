"""Mihomo Clash API integration for the Xkeen UI panel.

This blueprint exposes a small safe subset of Mihomo's external-controller API
through the authenticated Xkeen UI origin. It lets users manage runtime
selectors from :8088 without opening the standalone dashboard on :9090.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

try:
    from mihomo_server_core import CONFIG_PATH
except Exception:  # pragma: no cover - startup fallback
    CONFIG_PATH = Path(os.environ.get("MIHOMO_CONFIG", "/opt/etc/mihomo/config.yaml"))


_SELECTOR_TYPES = {"Selector", "Fallback", "URLTest", "LoadBalance"}
_NO_DELAY_TYPES = {"reject", "reject-drop", "dns", "pass", "relay"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(str(raw).strip()) if raw is not None else default
    except Exception:
        return default


def _controller_base() -> str:
    raw = (os.environ.get("MIHOMO_CONTROLLER_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    host = (os.environ.get("MIHOMO_CONTROLLER_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = _env_int("MIHOMO_CONTROLLER_PORT", 9090)
    return f"http://{host}:{port}"


def _controller_secret() -> str:
    return (os.environ.get("MIHOMO_CONTROLLER_SECRET") or os.environ.get("MIHOMO_SECRET") or "").strip()


def _request_mihomo(method: str, path: str, payload: Any | None = None, timeout: float = 8.0) -> tuple[int, Any]:
    url = _controller_base() + "/" + str(path or "").lstrip("/")
    data = None
    headers = {"Accept": "application/json"}
    secret = _controller_secret()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body}
            return int(getattr(resp, "status", 200) or 200), parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}
        return int(exc.code or 502), parsed


def _proxy_delay(proxy: dict[str, Any]) -> int | None:
    if str(proxy.get("type") or "").lower() in _NO_DELAY_TYPES:
        return None
    hist = proxy.get("history")
    if isinstance(hist, list) and hist:
        last = hist[-1]
        if isinstance(last, dict):
            try:
                delay = last.get("delay")
                if delay is None:
                    return None
                return int(delay)
            except Exception:
                return None
    return None


def _summarize_proxies(raw: dict[str, Any]) -> dict[str, Any]:
    proxies = raw.get("proxies") if isinstance(raw, dict) else None
    if not isinstance(proxies, dict):
        proxies = {}
    selectors = []
    nodes = []
    for name, value in proxies.items():
        if not isinstance(value, dict):
            continue
        item = {
            "name": str(name),
            "type": value.get("type"),
            "now": value.get("now"),
            "all": value.get("all") if isinstance(value.get("all"), list) else [],
            "alive": value.get("alive"),
            "udp": value.get("udp"),
            "delay": _proxy_delay(value),
            "provider": value.get("provider-name"),
            "hidden": value.get("hidden"),
        }
        if str(value.get("type") or "") in _SELECTOR_TYPES and item["all"]:
            selectors.append(item)
        else:
            nodes.append(item)
    selectors.sort(key=lambda x: str(x.get("name") or "").lower())
    nodes.sort(key=lambda x: str(x.get("name") or "").lower())
    return {
        "selectors": selectors,
        "nodes": nodes,
        "raw_count": len(proxies),
        "controller": _controller_base(),
    }


def _mihomo_root() -> Path:
    try:
        cfg = Path(CONFIG_PATH)
        # CONFIG_PATH is often /opt/etc/mihomo/config.yaml -> profiles/default.yaml.
        # The Mihomo root is the symlink location parent, not the resolved target parent.
        return cfg.expanduser().parent.resolve()
    except Exception:
        pass
    return Path(os.environ.get("MIHOMO_ROOT", "/opt/etc/mihomo")).expanduser().resolve()


def _manual_rule_file() -> Path:
    raw = (os.environ.get("MIHOMO_MANUAL_RULE_FILE") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_mihomo_root() / "rules" / "manual-proxy.yaml").resolve()


def _safe_manual_path() -> Path:
    path = _manual_rule_file()
    root = _mihomo_root().resolve()
    try:
        if not (str(path).startswith(str(root) + os.sep) or path == root):
            raise RuntimeError("manual rule file must be inside MIHOMO_ROOT")
    except Exception as exc:
        raise RuntimeError(f"unsafe manual rule path: {path}") from exc
    return path


def _normalize_manual_payload(text: str) -> str:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    stripped = raw.strip()
    if not stripped:
        return "payload:\n"
    if stripped.startswith("payload:"):
        return stripped + "\n"
    lines = []
    for line in raw.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-"):
            s = s[1:].strip()
        if s:
            lines.append(f"  - {s}")
    return "payload:\n" + "\n".join(lines) + ("\n" if lines else "")


def create_mihomo_clash_blueprint() -> Blueprint:
    bp = Blueprint("mihomo_clash", __name__)

    @bp.get("/api/mihomo/clash/status")
    def api_mihomo_clash_status():
        try:
            status, data = _request_mihomo("GET", "/version", timeout=4.0)
            return jsonify({"ok": 200 <= status < 300, "status": status, "data": data, "controller": _controller_base()})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc), "controller": _controller_base()}), 502

    @bp.get("/api/mihomo/clash/proxies")
    def api_mihomo_clash_proxies():
        try:
            status, data = _request_mihomo("GET", "/proxies", timeout=10.0)
            if not (200 <= status < 300):
                return jsonify({"ok": False, "status": status, "error": data}), 502
            summary = _summarize_proxies(data)
            summary["ok"] = True
            return jsonify(summary)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc), "controller": _controller_base()}), 502

    @bp.put("/api/mihomo/clash/proxies/<path:selector>")
    def api_mihomo_clash_select(selector: str):
        body = request.get_json(silent=True) or {}
        name = str(body.get("name") or body.get("proxy") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "missing proxy name"}), 400
        enc = urllib.parse.quote(str(selector), safe="")
        try:
            status, data = _request_mihomo("PUT", f"/proxies/{enc}", {"name": name}, timeout=8.0)
            ok = 200 <= status < 300
            return jsonify({"ok": ok, "status": status, "data": data, "selector": selector, "name": name}), (200 if ok else 502)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc), "selector": selector, "name": name}), 502

    @bp.get("/api/mihomo/manual-proxy")
    def api_mihomo_manual_proxy_get():
        try:
            path = _safe_manual_path()
            text = path.read_text(encoding="utf-8") if path.exists() else "payload:\n"
            return jsonify({"ok": True, "path": str(path), "content": text})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc)}), 500

    @bp.post("/api/mihomo/manual-proxy")
    def api_mihomo_manual_proxy_save():
        body = request.get_json(silent=True) or {}
        content = _normalize_manual_payload(str(body.get("content") or ""))
        try:
            path = _safe_manual_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if path.exists():
                backup = path.with_name(path.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
                shutil.copy2(path, backup)
            path.write_text(content, encoding="utf-8")
            return jsonify({"ok": True, "path": str(path), "backup": str(backup) if backup else None, "content": content})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc)}), 500

    return bp
