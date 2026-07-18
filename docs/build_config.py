#!/usr/bin/env python3
"""Converts a plaintext list of vless:// / trojan:// share-links into an
Xray-core client JSON config with an auto-balancer across all servers.

Usage:
    python3 build_config.py                  # fetches SOURCE_URL, writes both configs
    python3 build_config.py path/to/list.txt  # use a local file instead of the URL
"""
import json
import os
import re
import sys
import urllib.parse as up
import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt"
BALANCER_TAG = "Auto-Balancer-RU-White"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_LEASTLOAD = os.path.join(SCRIPT_DIR, "Auto-Balancer-RU-White.json")
OUT_LEASTPING = os.path.join(SCRIPT_DIR, "Auto-Balancer-RU-White-leastPing-backup.json")

FP_PRIORITY = {"chrome": 0, "edge": 1, "firefox": 2, "safari": 3, "ios": 4, "android": 5, "qq": 6, "random": 7, "": 8}


def slugify(s, maxlen=24):
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-')
    return s[:maxlen] or "srv"


def parse_vless(line):
    body = line[len("vless://"):]
    left, _, frag = body.partition('#')
    userinfo, _, hostpart = left.partition('@')
    hostport, _, query = hostpart.partition('?')
    if ':' in hostport:
        host, port = hostport.rsplit(':', 1)
    else:
        host, port = hostport, "443"
    q = dict(up.parse_qsl(query, keep_blank_values=True))
    uuid = userinfo
    remark = up.unquote(frag) if frag else host

    net = q.get('type', 'tcp') or 'tcp'
    if net == 'raw':
        net = 'tcp'
    security = q.get('security', 'none') or 'none'
    fp = q.get('fp', '')

    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": host,
                "port": int(port),
                "users": [{
                    "id": uuid,
                    "encryption": q.get('encryption', 'none') or 'none',
                    "flow": q.get('flow', '') or ''
                }]
            }]
        },
        "streamSettings": {"network": net}
    }
    if not outbound["settings"]["vnext"][0]["users"][0]["flow"]:
        del outbound["settings"]["vnext"][0]["users"][0]["flow"]

    ss = outbound["streamSettings"]

    if net == 'tcp':
        header_type = q.get('headerType', 'none')
        ss["tcpSettings"] = {"header": {"type": header_type}}
    elif net == 'ws':
        path = q.get('path', '/')
        host_hdr = q.get('host', '')
        ws = {"path": path}
        if host_hdr:
            ws["headers"] = {"Host": host_hdr}
        ss["wsSettings"] = ws
    elif net == 'grpc':
        grpc = {"serviceName": q.get('serviceName', '')}
        if q.get('mode') == 'multi':
            grpc["multiMode"] = True
        authority = q.get('authority', '')
        if authority:
            grpc["authority"] = authority
        ss["grpcSettings"] = grpc

    if security == 'reality':
        ss["security"] = "reality"
        reality = {
            "serverName": q.get('sni', ''),
            "fingerprint": fp or "chrome",
            "publicKey": q.get('pbk', ''),
        }
        if q.get('sid'):
            reality["shortId"] = q.get('sid')
        if q.get('spx'):
            reality["spiderX"] = q.get('spx')
        ss["realitySettings"] = reality
    elif security == 'tls':
        ss["security"] = "tls"
        tls = {"serverName": q.get('sni', host), "fingerprint": fp or "chrome"}
        ss["tlsSettings"] = tls
    else:
        ss["security"] = "none"

    key = (uuid, host, port, net, q.get('serviceName', ''), q.get('path', ''), security)
    return key, remark, outbound, FP_PRIORITY.get(fp, 9)


def parse_trojan(line):
    body = line[len("trojan://"):]
    left, _, frag = body.partition('#')
    password, _, hostpart = left.partition('@')
    hostport, _, query = hostpart.partition('?')
    if ':' in hostport:
        host, port = hostport.rsplit(':', 1)
    else:
        host, port = hostport, "443"
    q = dict(up.parse_qsl(query, keep_blank_values=True))
    remark = up.unquote(frag) if frag else host
    net = q.get('type', 'tcp') or 'tcp'
    security = q.get('security', 'tls') or 'tls'
    fp = q.get('fp', '')

    outbound = {
        "protocol": "trojan",
        "settings": {
            "servers": [{
                "address": host,
                "port": int(port),
                "password": password
            }]
        },
        "streamSettings": {"network": net}
    }
    ss = outbound["streamSettings"]
    if net == 'ws':
        path = q.get('path', '/')
        host_hdr = q.get('host', '')
        ws = {"path": path}
        if host_hdr:
            ws["headers"] = {"Host": host_hdr}
        ss["wsSettings"] = ws
    if security == 'tls':
        ss["security"] = "tls"
        ss["tlsSettings"] = {"serverName": q.get('sni', host), "fingerprint": fp or "chrome"}
    else:
        ss["security"] = "none"

    key = (password, host, port, net, q.get('path', ''), security)
    return key, remark, outbound, FP_PRIORITY.get(fp, 9)


def load_lines(source):
    if source.startswith('http://') or source.startswith('https://'):
        with urllib.request.urlopen(source, timeout=20) as resp:
            text = resp.read().decode('utf-8')
    else:
        with open(source, encoding='utf-8') as f:
            text = f.read()
    return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]


def build_outbounds(lines):
    best = {}
    for line in lines:
        try:
            if line.startswith('vless://'):
                key, remark, outbound, prio = parse_vless(line)
            elif line.startswith('trojan://'):
                key, remark, outbound, prio = parse_trojan(line)
            else:
                continue
        except Exception as e:
            print("skip:", line[:60], e)
            continue
        if 'russia' in remark.lower():
            continue
        if key not in best or prio < best[key][0]:
            best[key] = (prio, remark, outbound)

    outbounds = []
    for i, (key, (prio, remark, outbound)) in enumerate(sorted(best.items(), key=lambda kv: kv[1][1]), start=1):
        tag = f"vless-{i:02d}-{slugify(remark)}"
        outbound["tag"] = tag
        outbound["mux"] = {"enabled": False, "concurrency": 8}
        outbounds.append(outbound)
    return outbounds


def base_config(outbounds, config_name):
    return {
        "remarks": config_name,
        "ps": config_name,
        "log": {"loglevel": "warning"},
        "dns": {
            "servers": [
                "https://1.1.1.1/dns-query",
                "https://8.8.8.8/dns-query",
                "localhost"
            ]
        },
        "inbounds": [
            {
                "tag": "socks-in",
                "port": 10808,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]}
            },
            {
                "tag": "http-in",
                "port": 10809,
                "listen": "127.0.0.1",
                "protocol": "http",
                "settings": {}
            }
        ],
        "outbounds": outbounds + [
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {"response": {"type": "http"}}}
        ],
        "policy": {
            "levels": {"0": {"handshake": 4, "connIdle": 300, "uplinkOnly": 1, "downlinkOnly": 1, "bufferSize": 10240}}
        }
    }


def with_least_load(config, balancer_tags):
    """Faster convergence: ranks servers into RTT tiers and only actively uses
    the best `expected` of them, instead of needing a full round on all of them
    before leastPing's flat ranking becomes meaningful."""
    config = dict(config)
    config["routing"] = {
        "domainStrategy": "AsIs",
        "balancers": [
            {
                "tag": BALANCER_TAG,
                "selector": ["vless-"],
                "strategy": {
                    "type": "leastLoad",
                    "settings": {
                        "expected": 5,
                        "baselines": ["200ms", "500ms", "1000ms", "1500ms"],
                        "tolerance": 0.3
                    }
                },
                "fallbackTag": balancer_tags[0] if balancer_tags else "direct"
            }
        ],
        "rules": [
            {"type": "field", "network": "tcp,udp", "balancerTag": BALANCER_TAG}
        ]
    }
    config["burstObservatory"] = {
        "subjectSelector": ["vless-"],
        "pingConfig": {
            "destination": "https://www.gstatic.com/generate_204",
            "interval": "20s",
            "sampling": 2,
            "timeout": "5s"
        }
    }
    return config


def with_least_ping(config, balancer_tags):
    """Known-working baseline strategy (confirmed working in Happ). Kept as an
    instant-rollback fallback if leastLoad/burstObservatory isn't supported by
    the Xray-core build bundled in the client."""
    config = dict(config)
    config["routing"] = {
        "domainStrategy": "AsIs",
        "balancers": [
            {
                "tag": BALANCER_TAG,
                "selector": ["vless-"],
                "strategy": {"type": "leastPing"},
                "fallbackTag": balancer_tags[0] if balancer_tags else "direct"
            }
        ],
        "rules": [
            {"type": "field", "network": "tcp,udp", "balancerTag": BALANCER_TAG}
        ]
    }
    config["observatory"] = {
        "subjectSelector": ["vless-"],
        "probeUrl": "https://www.gstatic.com/generate_204",
        "probeInterval": "30s",
        "enableConcurrency": True
    }
    return config


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else SOURCE_URL
    lines = load_lines(source)
    outbounds = build_outbounds(lines)
    balancer_tags = [o["tag"] for o in outbounds]
    print(f"Unique servers: {len(outbounds)} (from {len(lines)} lines)")

    least_load_cfg = with_least_load(base_config(outbounds, "Auto-Balancer RU-White"), balancer_tags)
    with open(OUT_LEASTLOAD, 'w', encoding='utf-8') as f:
        json.dump(least_load_cfg, f, ensure_ascii=False, indent=2)
    print("Written (primary, leastLoad):", OUT_LEASTLOAD)

    least_ping_cfg = with_least_ping(base_config(outbounds, "Auto-Balancer RU-White (leastPing backup)"), balancer_tags)
    with open(OUT_LEASTPING, 'w', encoding='utf-8') as f:
        json.dump(least_ping_cfg, f, ensure_ascii=False, indent=2)
    print("Written (backup, leastPing):", OUT_LEASTPING)


if __name__ == '__main__':
    main()
