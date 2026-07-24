from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_windows_previews_advertise_same_production_features():
    avalonia = read("desktop/previews/avalonia/Program.cs")
    wpf = read("desktop/previews/wpf/MainWindow.xaml.cs") + read("desktop/previews/wpf/MainWindow.xaml")
    cpp = read("desktop/previews/cpp-native/windows/main.cpp")

    for feature in PRODUCTION_FEATURES:
        assert feature in avalonia
        assert feature in wpf
        assert feature in cpp


def test_preview_release_version_bumped_for_production_candidates():
    manifest_script = read("scripts/build_desktop_previews_manifest.py")
    readme = read("README.md")

    assert "0.4.1" in manifest_script
    assert "v0.4.1-desktop-user-test" in manifest_script
    assert "v0.4.1-desktop-user-test" in readme
    assert "Unified-UI-Avalonia-UserTest-0.4.1-win-x64.zip" in manifest_script
    assert "Unified-UI-WPF-UserTest-0.4.1-win-x64.zip" in manifest_script
    assert "Unified-UI-Cpp-Win32-UserTest-0.4.1-win-x64.zip" in manifest_script


def test_apps_use_real_bridge_runtime_not_static_mock_only():
    avalonia = read("desktop/previews/avalonia/Program.cs")
    wpf = read("desktop/previews/wpf/MainWindow.xaml.cs") + read("desktop/previews/wpf/MainWindow.xaml")
    cpp = read("desktop/previews/cpp-native/windows/main.cpp")

    for source in (avalonia, wpf):
        assert "HttpClient" in source
        assert "BRIDGE_URL" in source
        assert "/api/proxies" in source
        assert "/api/connections" in source
        assert "/api/dns/resolve" in source
        assert "/api/config/save" in source
        assert "unified-ui-native-bridge.exe" in source

    assert "WinHttpOpen" in cpp
    assert "BRIDGE_URL" in cpp
    assert "/api/dns/resolve" in cpp
    assert "/api/config" in cpp
    assert "unified-ui-native-bridge.exe" in cpp
