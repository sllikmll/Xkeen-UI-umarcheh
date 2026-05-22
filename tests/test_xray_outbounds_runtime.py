from __future__ import annotations

from services.xray_outbounds_runtime import infer_active_xray_outbound


def test_infer_active_xray_outbound_uses_latest_access_log_bracket_tag():
    nodes = [
        {"key": "a", "tag": "cdn.pecan.run--A", "name": "Node A"},
        {"key": "b", "tag": "cdn.pecan.run--B", "name": "Node B"},
    ]
    result = infer_active_xray_outbound(
        nodes,
        {
            "access": [
                "2026/05/22 20:10:01 tcp:10.0.0.2:50000 accepted tcp:example.com:443 [cdn.pecan.run--A]\n",
                "2026/05/22 20:10:05 tcp:10.0.0.2:50001 accepted tcp:example.org:443 [cdn.pecan.run--B]\n",
            ],
        },
    )

    assert result["available"] is True
    assert result["active"]["key"] == "b"
    assert result["active"]["tag"] == "cdn.pecan.run--B"
    assert result["active"]["last_seen"] == "2026/05/22 20:10:05"


def test_infer_active_xray_outbound_requires_runtime_context():
    nodes = [{"key": "a", "tag": "cdn.pecan.run--A", "name": "Node A"}]
    result = infer_active_xray_outbound(
        nodes,
        {"error": ["2026/05/22 20:10:01 config loaded selector cdn.pecan.run--A\n"]},
    )

    assert result["available"] is False
    assert result["reason"] == "no_match"
