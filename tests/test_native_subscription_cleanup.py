from pathlib import Path

import yaml

from desktop.native.unified_ui_native import MihomoRuntime, NativeConfigManager


def test_delete_subscription_removes_owned_static_proxies_and_group_refs(tmp_path, monkeypatch):
    runtime = MihomoRuntime(runtime=tmp_path / "runtime", controller="http://127.0.0.1:19190")
    cfg = runtime.config_path
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        yaml.safe_dump(
            {
                "proxies": [
                    {"name": "owned-a", "type": "vless", "server": "example.com", "port": 443, "x-unified-ui-origin": {"kind": "subscription-mirror", "provider": "subscription_1"}},
                    {"name": "manual-a", "type": "direct"},
                ],
                "proxy-groups": [
                    {"name": "Ручной список", "type": "select", "use": ["subscription_1"], "proxies": ["owned-a", "manual-a"]},
                ],
                "proxy-providers": {
                    "subscription_1": {"type": "http", "url": "https://example.invalid/sub", "path": "./providers/subscription_1.yaml"},
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    mgr = NativeConfigManager(runtime)
    monkeypatch.setattr(mgr, "validate_text", lambda text: (True, "OK"))

    _, msg = mgr.delete_subscription_provider("subscription_1", restart=False)

    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert "subscription_1" not in data["proxy-providers"]
    assert [p["name"] for p in data["proxies"]] == ["manual-a"]
    assert data["proxy-groups"][0]["use"] == []
    assert data["proxy-groups"][0]["proxies"] == ["manual-a"]
    assert "зеркальные static proxies удалены: 1" in msg


def test_append_subscription_mirror_tags_static_proxy(tmp_path, monkeypatch):
    runtime = MihomoRuntime(runtime=tmp_path / "runtime", controller="http://127.0.0.1:19190")
    cfg = runtime.config_path
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        yaml.safe_dump(
            {
                "proxies": [],
                "proxy-groups": [{"name": "Ручной список", "type": "select", "proxies": []}],
                "proxy-providers": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    mgr = NativeConfigManager(runtime)
    monkeypatch.setattr(mgr, "validate_text", lambda text: (True, "OK"))
    monkeypatch.setattr(mgr, "fetch_subscription_imports", lambda url: [
        type("Import", (), {"name": "node-a", "yaml": "- name: node-a\n  type: direct\n", "kind": "yaml"})()
    ])

    mgr.add_subscription_provider("https://example.invalid/sub", name="subscription_1", groups=["Ручной список"], restart=False)

    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    proxy = data["proxies"][0]
    assert proxy["name"] == "node-a"
    assert proxy["x-unified-ui-origin"] == {"kind": "subscription-mirror", "provider": "subscription_1"}
    assert "node-a" in data["proxy-groups"][0]["proxies"]
