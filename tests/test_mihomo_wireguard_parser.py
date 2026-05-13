from __future__ import annotations

import yaml
from flask import Flask

from routes.mihomo import create_mihomo_blueprint
from services.mihomo_generator_proxies import insert_proxies_from_state
from services.mihomo_proxy_parsers import parse_wireguard


AMNEZIA_WG_V2_CONF = """
[Interface]
PrivateKey = eCtXsJZ27+4PbhDkHnB923tkUn2Gj59wZw5wFA75MnU=
Address = 172.16.0.2/32, fd01:5ca1:ab1e:80fa:ab85:6eea:213f:f4a5/128
DNS = 1.1.1.1, 8.8.8.8
MTU = 1408
Jc = 5
Jmin = 500
Jmax = 501
S1 = 30
S2 = 40
S3 = 50
S4 = 5
H1 = 123456-123500
H2 = 67543-67550
H3 = 123123-123200
H4 = 32345-32350
I1 = <b 0xf6ab3267fa><c><b 0xf6ab><t><r 10><wt 10>
I2 = <b 0xf6ab3267fa><r 100>
I3 = ""
I4 = ""
I5 = ""

[Peer]
PublicKey = Cr8hWlKvtDt7nrvf+f0brNQQzabAqrjfBvas9pmowjo=
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 162.159.192.1:2480
PersistentKeepalive = 25
PresharedKey = 31aIhAPwktDGpH4JDhA8GNvjFXEf/a6+UaQRyOAiyfM=
Reserved = [209, 98, 59]
"""


def _parsed_proxy(yaml_text: str) -> dict:
    parsed = yaml.safe_load(yaml_text)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    return parsed[0]


def test_parse_wireguard_accepts_amnezia_wg_v2_options():
    result = parse_wireguard(AMNEZIA_WG_V2_CONF, custom_name="amnezia-v2")
    proxy = _parsed_proxy(result.yaml)
    amnezia = proxy["amnezia-wg-option"]

    assert proxy["name"] == "amnezia-v2"
    assert proxy["type"] == "wireguard"
    assert proxy["ip"] == "172.16.0.2"
    assert proxy["ipv6"] == "fd01:5ca1:ab1e:80fa:ab85:6eea:213f:f4a5"
    assert proxy["reserved"] == [209, 98, 59]
    assert proxy["allowed-ips"] == ["0.0.0.0/0", "::/0"]
    assert proxy["dns"] == ["1.1.1.1", "8.8.8.8"]
    assert proxy["remote-dns-resolve"] is True

    assert amnezia["jc"] == 5
    assert amnezia["jmin"] == 500
    assert amnezia["jmax"] == 501
    assert amnezia["s3"] == 50
    assert amnezia["s4"] == 5
    assert amnezia["h1"] == "123456-123500"
    assert amnezia["h4"] == "32345-32350"
    assert amnezia["i1"] == "<b 0xf6ab3267fa><c><b 0xf6ab><t><r 10><wt 10>"
    assert amnezia["i2"] == "<b 0xf6ab3267fa><r 100>"
    assert amnezia["i3"] == ""
    assert amnezia["i4"] == ""
    assert amnezia["i5"] == ""
    assert "j1" not in amnezia
    assert "j2" not in amnezia
    assert "j3" not in amnezia
    assert "itime" not in amnezia


def test_mihomo_parse_wireguard_route_returns_amnezia_wg_v2_yaml(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("proxies: []\n", encoding="utf-8")
    bp = create_mihomo_blueprint(
        MIHOMO_CONFIG_FILE=str(cfg),
        MIHOMO_TEMPLATES_DIR=str(tmp_path),
        MIHOMO_DEFAULT_TEMPLATE=str(tmp_path / "default.yaml"),
        restart_xkeen=lambda: None,
    )
    app = Flask(__name__)
    app.register_blueprint(bp)

    response = app.test_client().post(
        "/api/mihomo/parse/wireguard",
        json={"text": AMNEZIA_WG_V2_CONF, "name": "route-awg"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["proxy_name"] == "route-awg"
    proxy = _parsed_proxy(body["proxy_yaml"])
    assert proxy["amnezia-wg-option"]["h1"] == "123456-123500"
    assert proxy["amnezia-wg-option"]["i3"] == ""


def test_generator_wireguard_proxy_insert_preserves_amnezia_wg_v2_options():
    base_config = "\n".join(
        [
            "proxies: []",
            "proxy-groups:",
            "  - name: Auto",
            "    type: select",
            "    proxies: [DIRECT]",
            "",
        ]
    )
    state = {
        "defaultGroups": ["Auto"],
        "proxies": [
            {
                "kind": "wireguard",
                "name": "generator-awg",
                "config": AMNEZIA_WG_V2_CONF,
            }
        ],
    }

    result = insert_proxies_from_state(base_config, state)
    parsed = yaml.safe_load(result)

    proxy = parsed["proxies"][0]
    assert proxy["name"] == "generator-awg"
    assert proxy["amnezia-wg-option"]["s4"] == 5
    assert proxy["amnezia-wg-option"]["h4"] == "32345-32350"
    assert proxy["amnezia-wg-option"]["i5"] == ""
    assert "generator-awg" in parsed["proxy-groups"][0]["proxies"]
