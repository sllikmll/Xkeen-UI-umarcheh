from pathlib import Path


def test_happ_helper_env_keys_are_exposed_in_devtools():
    env_py = Path("xkeen-ui/services/devtools/env.py").read_text(encoding="utf-8")
    env_js = Path("xkeen-ui/static/js/features/devtools/env.js").read_text(encoding="utf-8")

    for key in (
        "XKEEN_HAPP_HELPER_CMD",
        "XKEEN_HAPP_DECRYPTOR_CMD",
        "XKEEN_HAPP_DECRYPTOR_REMOTE_URL",
        "XKEEN_HAPP_HELPER_TIMEOUT",
        "XKEEN_HAPP_DECRYPTOR_TIMEOUT",
        "XKEEN_HAPP_HELPER_HWID",
        "XKEEN_SUBSCRIPTION_HAPP_USER_AGENT",
    ):
        assert f'"{key}"' in env_py
        assert f"ENV_HELP.{key}" in env_js
        assert f"ENV_NO_RESTART_KEYS.add('{key}')" in env_js


def test_happ_helper_env_keys_are_grouped_under_mihomo_hwid():
    env_js = Path("xkeen-ui/static/js/features/devtools/env.js").read_text(encoding="utf-8")

    assert "title: 'Mihomo и HWID'" in env_js
    assert "'XKEEN_HAPP_HELPER_CMD'" in env_js
    assert "'XKEEN_HAPP_DECRYPTOR_CMD'" in env_js
    assert "'XKEEN_HAPP_DECRYPTOR_REMOTE_URL'" in env_js
    assert "'XKEEN_HAPP_HELPER_TIMEOUT'" in env_js
    assert "'XKEEN_HAPP_DECRYPTOR_TIMEOUT'" in env_js
    assert "'XKEEN_HAPP_HELPER_HWID'" in env_js
    assert "'XKEEN_SUBSCRIPTION_HAPP_USER_AGENT'" in env_js
