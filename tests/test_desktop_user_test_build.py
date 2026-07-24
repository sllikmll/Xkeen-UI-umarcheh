from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QT_PAGES = [
    "Маршрутизация",
    "Mihomo",
    "Соединения",
    "VLESS",
    "WireGuard",
    "AmneziaWG",
    "Hysteria2",
    "Trojan",
    "Mieru",
    "NaiveProxy",
    "Логи",
    "Mihomo Генератор",
    "Конфиг",
    "Ручной список",
    "Маршруты DNS",
    "Интерфейс",
    "Настройки",
]

DESIGN_TOKENS = ["#050B1A", "#08142A", "#0A1730", "#67E8F9", "#20C878", "#EF4E5F"]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_windows_apps_expose_qt_native_page_map_and_design_tokens():
    sources = {
        "avalonia": read("desktop/previews/avalonia/Program.cs"),
        "wpf": read("desktop/previews/wpf/MainWindow.xaml") + read("desktop/previews/wpf/MainWindow.xaml.cs"),
        "cpp": read("desktop/previews/cpp-native/windows/main.cpp"),
    }
    for name, source in sources.items():
        assert "0.4.0" in source, name
        for page in QT_PAGES:
            assert page in source, f"{name} missing page {page}"
        for token in DESIGN_TOKENS:
            assert token in source, f"{name} missing token {token}"
        for phrase in ["Unified UI", "Mihomo runtime", "selector tiles", "proxy-providers", "rule-providers", "config.yaml", "manual-proxy.yaml"]:
            assert phrase in source, f"{name} missing UX phrase {phrase}"


def test_bridge_has_user_testing_endpoints_for_full_lifecycle():
    bridge = read("desktop/previews/shared/native_bridge.py")
    assert 'BRIDGE_VERSION = "0.4.0"' in bridge
    for endpoint in [
        "/api/subscription/update",
        "/api/subscription/delete",
        "/api/static/delete",
        "/api/providers/proxies/update",
        "/api/providers/rules/update",
        "/api/config/apply",
        "/api/connections/close",
    ]:
        assert endpoint in bridge


def test_040_manifest_and_readme_are_new_release_line():
    manifest = read("scripts/build_desktop_previews_manifest.py")
    readme = read("README.md")
    assert "0.4.0" in manifest
    assert "v0.4.0-desktop-user-test" in manifest
    assert "v0.4.0-desktop-user-test" in readme
    assert "готовый конечный вариант для ручного тестирования" in readme
