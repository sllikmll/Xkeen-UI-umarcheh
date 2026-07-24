from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PARITY_FEATURES = [
    "runtime-controls",
    "selector-list-and-tiles",
    "per-node-ping",
    "proxy-table",
    "connections-table",
    "config-editor",
    "subscription-manager",
    "static-proxy-import",
    "dns-routes-manual-resolver",
    "logs-viewer",
    "settings-runtime-paths",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_windows_previews_advertise_same_qt_parity_features():
    avalonia = read("desktop/previews/avalonia/Program.cs")
    wpf = read("desktop/previews/wpf/MainWindow.xaml.cs") + read("desktop/previews/wpf/MainWindow.xaml")
    cpp = read("desktop/previews/cpp-native/windows/main.cpp")

    for feature in PARITY_FEATURES:
        assert feature in avalonia
        assert feature in wpf
        assert feature in cpp


def test_preview_release_version_bumped_for_full_parity():
    manifest_script = read("scripts/build_desktop_previews_manifest.py")
    readme = read("README.md")

    assert "0.2.0" in manifest_script
    assert "v0.2.0-desktop-previews" in manifest_script
    assert "v0.2.0-desktop-previews" in readme
    assert "Unified-UI-Avalonia-Preview-0.2.0-win-x64.zip" in manifest_script
    assert "Unified-UI-WPF-Preview-0.2.0-win-x64.zip" in manifest_script
    assert "Unified-UI-Cpp-Win32-Preview-0.2.0-win-x64.zip" in manifest_script


def test_parity_apps_have_real_runtime_interaction_code_not_static_mock_only():
    avalonia = read("desktop/previews/avalonia/Program.cs")
    wpf = read("desktop/previews/wpf/MainWindow.xaml.cs") + read("desktop/previews/wpf/MainWindow.xaml")
    cpp = read("desktop/previews/cpp-native/windows/main.cpp")

    for source in (avalonia, wpf):
        assert "HttpClient" in source
        assert "/proxies" in source
        assert "/connections" in source
        assert "Dns.GetHostAddresses" in source
        assert "config.yaml" in source

    assert "WinHttpOpen" in cpp
    assert "getaddrinfo" in cpp
    assert "config.yaml" in cpp
    assert "Unified UI C++ Win32 Preview" in cpp
