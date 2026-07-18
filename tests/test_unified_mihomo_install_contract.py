from pathlib import Path


def test_main_installer_runs_unified_mihomo_installer_by_default():
    text = Path("xkeen-ui/install.sh").read_text(encoding="utf-8")

    assert "Unified Mihomo core install" in text
    assert 'XKEEN_INSTALL_MIHOMO:-1' in text
    assert 'sh "$UI_DIR/scripts/install_mihomo_core.sh"' in text
    assert 'XKEEN_INSTALL_MIHOMO=0' in text


def test_mihomo_core_installer_uses_user_fork_with_upstream_release_fallback():
    text = Path("xkeen-ui/scripts/install_mihomo_core.sh").read_text(encoding="utf-8")

    assert 'MIHOMO_REPO="${XKEEN_MIHOMO_REPO:-sllikmll/mihomo}"' in text
    assert 'MIHOMO_FALLBACK_REPO="${XKEEN_MIHOMO_FALLBACK_REPO:-MetaCubeX/mihomo}"' in text
    assert 'for candidate in [repo, fallback_repo]' in text
    assert 'releases/latest' in text
    assert 'mihomo-linux-arm64-.*[.]gz$' in text
    assert 'mihomo-linux-mipsle-softfloat-.*[.]gz$' in text


def test_mihomo_core_installer_creates_runtime_layout_restart_and_ui_env():
    text = Path("xkeen-ui/scripts/install_mihomo_core.sh").read_text(encoding="utf-8")

    assert 'mkdir -p "$TMP_DIR" /opt/sbin "$MIHOMO_ROOT" "$MIHOMO_ROOT/profiles" "$MIHOMO_ROOT/rules"' in text
    assert 'ln -sf "profiles/default.yaml" "$MIHOMO_ROOT/config.yaml"' in text
    assert 'external-controller: $MIHOMO_CONTROLLER' in text
    assert 'restart-mihomo.sh' in text
    assert 'MIHOMO_VALIDATE_CMD' in text
    assert "http://127.0.0.1:9090/version" in text
