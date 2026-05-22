from services import ui_settings


def test_ui_settings_default_active_outbound_display_is_disabled(tmp_path):
    loaded = ui_settings.load_settings(ui_state_dir=str(tmp_path))
    assert loaded["routing"]["showActiveOutbound"] is False


def test_ui_settings_persists_active_outbound_display_toggle(tmp_path):
    saved = ui_settings.save_settings(
        {"routing": {"showActiveOutbound": True}},
        ui_state_dir=str(tmp_path),
    )

    assert saved["routing"]["showActiveOutbound"] is True

    loaded = ui_settings.load_settings(ui_state_dir=str(tmp_path))
    assert loaded["routing"]["showActiveOutbound"] is True

    patched, report = ui_settings.patch_settings(
        {"routing": {"showActiveOutbound": False}},
        ui_state_dir=str(tmp_path),
    )

    assert report["errors"] == []
    assert patched["routing"]["showActiveOutbound"] is False


def test_ui_settings_rejects_invalid_active_outbound_display_toggle(tmp_path):
    saved = ui_settings.save_settings(
        {"routing": {"showActiveOutbound": True}},
        ui_state_dir=str(tmp_path),
    )
    assert saved["routing"]["showActiveOutbound"] is True

    try:
        ui_settings.patch_settings(
            {"routing": {"showActiveOutbound": "yes"}},
            ui_state_dir=str(tmp_path),
        )
    except ui_settings.UISettingsValidationError as exc:
        assert exc.errors == [{"path": "routing.showActiveOutbound", "error": "must be boolean"}]
    else:
        raise AssertionError("invalid showActiveOutbound patch should be rejected")

    loaded = ui_settings.load_settings(ui_state_dir=str(tmp_path))
    assert loaded["routing"]["showActiveOutbound"] is True
