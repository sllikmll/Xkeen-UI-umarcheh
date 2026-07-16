from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from flask import Flask, Response
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "xkeen-ui"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _reload(name: str):
    module = sys.modules.get(name)
    if module is not None:
        return importlib.reload(module)
    return importlib.import_module(name)


def _build_client(tmp_path: Path, monkeypatch, *, install_size_guard: bool = False):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XKEEN_UI_STATE_DIR", str(state_dir))
    monkeypatch.setenv("XKEEN_UI_SECRET_KEY", "test-secret-key")

    _reload("core.paths")
    auth_setup = _reload("services.auth_setup")
    _reload("services.auth_rate_limit")
    mobile_routes = _reload("routes.mobile")
    request_limits = _reload("services.request_limits")

    auth_setup._atomic_write(
        auth_setup.AUTH_FILE,
        json.dumps(
            {
                "version": 1,
                "created_at": 0,
                "username": "admin",
                "password_hash": generate_password_hash("secret123"),
            }
        ),
        mode=0o600,
    )

    app = Flask("mobile-routing-validate-test")
    app.config["TESTING"] = True

    @app.get("/ui/terminal-theme.css")
    def terminal_theme_css():
        return Response("", mimetype="text/css")

    if install_size_guard:
        request_limits.install_request_size_guards(app)
    auth_setup.init_auth(app)
    mobile_routes.register_mobile_routes(app)
    return app.test_client(), mobile_routes


def _login(client) -> str:
    response = client.post(
        "/api/mobile/v1/session",
        json={"username": "admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return response.get_json()["data"]["session"]["csrf_token"]


def _install_preflight_stub(mobile_routes, tmp_path: Path, monkeypatch, result: dict):
    calls: list[dict] = []

    def paths_for_routing(*_args):
        return (
            str(tmp_path / "configs" / "05_routing.json"),
            str(tmp_path / "jsonc" / "05_routing.jsonc"),
            "",
        )

    def run_preflight(**kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr(
        mobile_routes,
        "_mobile_xray_routing_validation_dependencies",
        lambda: {
            "run_preflight": run_preflight,
            "paths_for_routing": paths_for_routing,
            "routing_file": str(tmp_path / "configs" / "05_routing.json"),
            "routing_file_raw": str(tmp_path / "jsonc" / "05_routing.jsonc"),
            "xray_configs_dir": str(tmp_path / "configs"),
            "xray_configs_dir_real": str(tmp_path / "configs"),
        },
    )
    return calls


def test_mobile_routing_validate_requires_authenticated_csrf_session(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch)
    calls = _install_preflight_stub(mobile_routes, tmp_path, monkeypatch, {"ok": True})

    anonymous = client.post(
        "/api/mobile/v1/xray/routing/validate",
        json={"document": "05_routing.json", "content": "{}"},
    )
    assert anonymous.status_code == 401

    csrf_token = _login(client)
    missing_csrf = client.post(
        "/api/mobile/v1/xray/routing/validate",
        json={"document": "05_routing.json", "content": "{}"},
    )
    assert missing_csrf.status_code == 403

    accepted = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "05_routing.json", "content": "{}"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["data"]["valid"] is True
    assert len(calls) == 1


def test_mobile_routing_validate_uses_real_preflight_shape_and_does_not_persist(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch, install_size_guard=True)
    calls = _install_preflight_stub(
        mobile_routes,
        tmp_path,
        monkeypatch,
        {"ok": True, "phase": "xray_test", "stdout": "configuration ok"},
    )
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "document": "05_routing.jsonc",
            "content": "// kept only in the draft\n{\n  \"routing\": {\"rules\": []}\n}",
        },
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json() == {
        "ok": True,
        "data": {
            "valid": True,
            "message": "Серверная проверка конфигурации Xray пройдена.",
            "diagnostics": [],
        },
    }
    assert calls == [
        {
            "xray_configs_dir_real": str(tmp_path / "configs"),
            "sel_main": str(tmp_path / "configs" / "05_routing.json"),
            "obj": {"routing": {"rules": []}},
            "sync_dat_assets": False,
        }
    ]
    assert not (tmp_path / "configs" / "05_routing.json").exists()


def test_mobile_routing_validate_returns_json_syntax_diagnostic_without_preflight(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch)
    calls = _install_preflight_stub(mobile_routes, tmp_path, monkeypatch, {"ok": True})
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "05_routing.json", "content": "{\n  \"routing\":\n"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["valid"] is False
    assert payload["data"]["diagnostics"] == [
        {
            "source": "server",
            "severity": "error",
            "code": "invalid_json",
            "message": "Сервер не смог разобрать JSON/JSONC. Исправьте синтаксис и повторите проверку.",
            "path": "05_routing.json",
            "line": 3,
            "column": 1,
        }
    ]
    assert calls == []


def test_mobile_routing_validate_rejects_path_traversal_without_falling_back(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch)
    calls = _install_preflight_stub(mobile_routes, tmp_path, monkeypatch, {"ok": True})
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "../04_outbounds.json", "content": "{}"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": {
            "code": "invalid_document",
            "message": "Поле document должно содержать имя Xray JSON/JSONC-фрагмента.",
        },
    }
    assert calls == []


def test_mobile_routing_validate_returns_preflight_diagnostic_in_successful_envelope(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch)
    _install_preflight_stub(
        mobile_routes,
        tmp_path,
        monkeypatch,
        {
            "ok": False,
            "phase": "routing_semantic_validate",
            "summary": "Правило ссылается на отсутствующий outboundTag.",
            "hint": "Создайте outbound или исправьте правило.",
        },
    )
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "05_routing.json", "content": "{}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "data": {
            "valid": False,
            "message": "Правило ссылается на отсутствующий outboundTag.",
            "diagnostics": [
                {
                    "source": "server",
                    "severity": "error",
                    "code": "routing_semantic_validate",
                    "message": "Правило ссылается на отсутствующий outboundTag.",
                    "path": "05_routing.json",
                    "hint": "Создайте outbound или исправьте правило.",
                    "phase": "routing_semantic_validate",
                }
            ],
        },
    }


def test_mobile_routing_validate_keeps_preflight_timeout_as_server_diagnostic(tmp_path: Path, monkeypatch):
    client, mobile_routes = _build_client(tmp_path, monkeypatch)
    _install_preflight_stub(
        mobile_routes,
        tmp_path,
        monkeypatch,
        {
            "ok": False,
            "phase": "xray_test",
            "timed_out": True,
            "hint": "Таймаут проверки конфигурации Xray.",
        },
    )
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "05_routing.json", "content": "{}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["valid"] is False
    assert payload["data"]["diagnostics"][0]["code"] == "xray_test_timeout"
    assert payload["data"]["diagnostics"][0]["message"] == "Таймаут проверки конфигурации Xray."


def test_mobile_routing_validate_uses_routing_body_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XKEEN_ROUTING_SAVE_MAX_BYTES", str(64 * 1024))
    client, mobile_routes = _build_client(tmp_path, monkeypatch, install_size_guard=True)
    calls = _install_preflight_stub(mobile_routes, tmp_path, monkeypatch, {"ok": True})
    csrf_token = _login(client)

    response = client.post(
        "/api/mobile/v1/xray/routing/validate",
        headers={"X-CSRF-Token": csrf_token},
        json={"document": "05_routing.json", "content": "x" * (64 * 1024)},
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "ok": False,
        "error": "payload too large",
        "max_bytes": 64 * 1024,
    }
    assert calls == []
