# IDS / IPS — Suricata

Module `ids`, commit with `POST /api/ids/service/reconfigure`.

## Endpoints

| Controller | Commands |
| --- | --- |
| `settings` | Global config, plus per-rule and per-policy management |
| `service` | `reconfigure`, `restart`, `start`, `stop`, `status`, `reload_rules`, `update_rules`, `query_alerts`, `get_alert_info`, `get_alert_logs`, `drop_alert_log` |

```bash
python scripts/opnsense.py show ids/settings
python scripts/opnsense.py get  ids/service/status
```

## Detection versus prevention

Enabling the service gives you **IDS** — it logs and alerts. Blocking requires
**IPS mode**, which routes traffic through the netmap-based inline path. Two
consequences:

- IPS mode needs a NIC whose driver supports netmap. On unsupported hardware it
  either refuses to start or silently passes traffic.
- Hardware offloading (LRO/TSO) must be disabled on the monitored interfaces, or
  Suricata sees reassembled segments that do not match reality.

Select interfaces deliberately. Monitoring WAN sees traffic after NAT, so
internal source addresses are hidden; monitoring LAN shows who did it but misses
anything blocked upstream.

## Rules

```bash
python scripts/opnsense.py post ids/service/update_rules    # fetch rulesets
python scripts/opnsense.py post ids/service/reload_rules    # reload without full restart
ssh root@<host> 'configctl ids update'
```

Rulesets are enabled per source (ET Open, Abuse.ch, Snort registered with an
oinkcode, and the OPNsense-provided lists). Enabling everything on a modest
appliance is the standard mistake: memory use and startup time climb sharply and
false positives bury the real alerts.

A workable sequence for a new deployment:

1. Enable one focused ruleset. Run in IDS mode only.
2. Watch alerts for a week; the noisy signatures reveal themselves quickly.
3. Disable or tune those specific SIDs.
4. Only then switch to IPS mode, and only for rule classes you have reviewed.

Per-rule overrides live under `ids/settings` — you can disable individual SIDs
or change their action to `drop` selectively rather than flipping whole
categories.

## Alerts

```bash
python scripts/opnsense.py post ids/service/query_alerts --data \
  '{"current":1,"rowCount":50,"searchPhrase":""}'
python scripts/opnsense.py get  ids/service/get_alert_info <alertId>
```

Logs are on disk at `/var/log/suricata/`. `drop_alert_log` clears them.

## Cost

Suricata is the heaviest thing on a small firewall. Before enabling it on
production hardware, check headroom:

```bash
python scripts/opnsense.py get diagnostics/system/system_resources
python scripts/opnsense.py get diagnostics/system/memory
```

If throughput matters more than inspection on that box, a DNS blocklist
(see [dns.md](dns.md)) buys a large share of the practical benefit at a fraction
of the cost.
