import json
import threading
import urllib.request
from pathlib import Path

import pytest
import yaml

from desktop.native.unified_ui_native import MihomoRuntime, NativeConfigManager
from desktop.previews.shared.native_bridge import BridgeState, _parse_imports_with_fallback, make_server


def request_json(base: str, path: str, payload: dict | None = None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


@pytest.fixture()
def bridge(tmp_path, monkeypatch):
    runtime = MihomoRuntime(runtime=tmp_path / "runtime", controller="http://127.0.0.1:19190")
    cfg = runtime.config_path
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        """
proxies:
  - name: DIRECT
    type: direct
proxy-groups:
  - name: Маршрутизация
    type: select
    proxies: [DIRECT]
rule-providers: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    manager = NativeConfigManager(runtime)
    monkeypatch.setattr(manager, "validate_text", lambda text: (True, "OK"))
    monkeypatch.setattr(runtime, "version", lambda: "test-mihomo")
    monkeypatch.setattr(runtime, "proxies", lambda: {"DIRECT": {"type": "Direct", "alive": True}})
    monkeypatch.setattr(runtime, "proxy_providers", lambda: {})
    monkeypatch.setattr(runtime, "rule_providers", lambda: {})
    monkeypatch.setattr(runtime, "connections_data", lambda: {"connections": [], "uploadTotal": 0, "downloadTotal": 0})
    monkeypatch.setattr(runtime, "update_proxy_providers", lambda: [{"ok": True, "provider": "subscription_1"}])
    monkeypatch.setattr(runtime, "update_rule_providers", lambda: [])
    monkeypatch.setattr(runtime, "delay", lambda proxy: 12 if proxy == "DIRECT" else None)
    monkeypatch.setattr(runtime, "select_proxy", lambda group, proxy: None)
    monkeypatch.setattr(runtime, "close_connection", lambda conn_id: None)
    state = BridgeState(runtime=runtime, manager=manager)
    server = make_server(state, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base, runtime, manager
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bridge_status_and_smoke_features(bridge):
    base, runtime, _ = bridge

    data = request_json(base, "/api/status")

    assert data["ok"] is True
    assert data["bridge_version"] == "0.3.0"
    assert "runtime-start-stop-restart" in data["features"]
    assert "config-read-save-validate" in data["features"]
    assert data["config_path"] == str(runtime.config_path)


def test_bridge_config_inventory_save_and_provider_update(bridge):
    base, runtime, _ = bridge

    cfg = request_json(base, "/api/config")
    assert "proxy-groups" in cfg["text"]
    inv = request_json(base, "/api/inventory")
    assert inv["groups"] == ["Маршрутизация"]

    saved = request_json(base, "/api/config/save", {"text": cfg["text"], "validate": True})
    assert saved["ok"] is True
    assert "config.yaml сохранён" in saved["message"]
    assert yaml.safe_load(runtime.config_path.read_text(encoding="utf-8"))["proxy-groups"][0]["name"] == "Маршрутизация"

    upd = request_json(base, "/api/providers/proxies/update", {})
    assert upd["results"] == [{"ok": True, "provider": "subscription_1"}]


def test_bridge_subscription_and_static_import_mutate_config(bridge, monkeypatch):
    base, runtime, manager = bridge
    monkeypatch.setattr(
        manager,
        "fetch_subscription_imports",
        lambda url: [
            type("IR", (), {"name": "node-a", "yaml": "- name: node-a\n  type: http\n  server: example.com\n  port: 443\n", "kind": "uri"})()
        ],
    )

    sub = request_json(base, "/api/subscription/add", {"url": "https://example.invalid/sub", "name": "subscription_1", "restart": False})
    assert sub["ok"] is True
    assert sub["provider"] == "subscription_1"
    data = yaml.safe_load(runtime.config_path.read_text(encoding="utf-8"))
    assert "subscription_1" in data["proxy-providers"]

    imp = request_json(base, "/api/import/static", {"text": "- name: manual-node\n  type: http\n  server: 1.2.3.4\n  port: 8080\n", "restart": False})
    assert imp["ok"] is True
    data = yaml.safe_load(runtime.config_path.read_text(encoding="utf-8"))
    assert any(p.get("name") for p in data["proxies"] if isinstance(p, dict))


def test_bridge_dns_and_logs_endpoints(bridge):
    base, runtime, _ = bridge
    log_path = runtime.runtime / "logs" / "mihomo-native.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("hello log", encoding="utf-8")

    dns = request_json(base, "/api/dns/resolve", {"domains": "localhost"})
    assert dns["ok"] is True
    assert dns["results"][0]["domain"] == "localhost"

    logs = request_json(base, "/api/logs")
    assert logs["text"] == "hello log"


def test_bridge_import_fallback_supports_yaml_and_vless_when_web_services_absent(monkeypatch, tmp_path):
    runtime = MihomoRuntime(runtime=tmp_path / "runtime", controller="http://127.0.0.1:19190")
    runtime.config_path.parent.mkdir(parents=True)
    runtime.config_path.write_text("proxies: []\nproxy-groups: []\n", encoding="utf-8")
    manager = NativeConfigManager(runtime)
    monkeypatch.setattr(manager, "parse_import", lambda text: (_ for _ in ()).throw(RuntimeError("web-парсеры недоступны: No module named 'services'")))

    yaml_imports = _parse_imports_with_fallback(manager, "- name: yaml-node\n  type: http\n  server: 1.2.3.4\n  port: 8080\n")
    assert yaml_imports[0].name == "yaml-node"
    assert "type: http" in yaml_imports[0].yaml

    vless_imports = _parse_imports_with_fallback(manager, "vless://00000000-0000-0000-0000-000000000000@example.com:443?security=reality&type=tcp&sni=yandex.ru&pbk=PUB&sid=ac&fp=firefox#vless-node")
    assert vless_imports[0].name == "vless-node"
    assert "type: vless" in vless_imports[0].yaml
    assert "reality-opts" in vless_imports[0].yaml
