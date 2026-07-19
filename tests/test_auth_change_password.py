import importlib
import json
import sys
from pathlib import Path

from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash


def _reload(name: str):
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


def test_authenticated_user_can_change_password(tmp_path: Path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("XKEEN_UI_STATE_DIR", str(state))
    monkeypatch.setenv("XKEEN_UI_SECRET_KEY", "test-secret-key")

    auth_setup = _reload("services.auth_setup")
    auth_routes = _reload("routes.auth")
    auth_setup._atomic_write(
        auth_setup.AUTH_FILE,
        json.dumps({
            "version": 1,
            "created_at": 1,
            "username": "pavel",
            "password_hash": generate_password_hash("old-password"),
        }) + "\n",
    )

    app = Flask(__name__)
    app.config.update(TESTING=True)
    auth_setup.init_auth(app)
    auth_routes.register_auth_routes(app)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["auth"] = True
        sess["user"] = "pavel"
        sess["csrf"] = "csrf-token"

    response = client.post(
        "/api/auth/password",
        json={
            "current_password": "old-password",
            "new_password": "new-password-123",
            "new_password2": "new-password-123",
        },
        headers={"X-CSRF-Token": "csrf-token"},
    )
    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    saved = json.loads(Path(auth_setup.AUTH_FILE).read_text(encoding="utf-8"))
    assert saved["username"] == "pavel"
    assert check_password_hash(saved["password_hash"], "new-password-123")
