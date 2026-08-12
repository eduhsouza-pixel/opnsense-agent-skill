# Firewall rules

Controller `firewall/filter`. Commit with `POST /api/firewall/filter/apply`
(inherited from `FilterBaseController`, so it is absent from the published
reference — it works).

## Endpoints

| Method | Command | Params |
| --- | --- | --- |
| GET | `search_rule` | grid query |
| GET | `get_rule` | `<uuid>` (blank returns a default model) |
| POST | `add_rule` | body `{"rule": {...}}` |
| POST | `set_rule` | `<uuid>` |
| POST | `del_rule` | `<uuid>` |
| POST | `toggle_rule` | `<uuid>[/<enabled>]` |
| GET | `toggle_rule_log` | `<uuid>/<log>` |
| POST | `move_rule_before` | `<selected_uuid>/<target_uuid>` |
| GET | `get_interface_list` | valid interface keys |
| GET | `download_rules` / POST `upload_rules` | bulk JSON export/import |
| POST | `flush_inspect_cache` | |
| POST | `apply` | commit (inherited) |

## Scope

These endpoints manage the **Automation** ruleset (*Firewall > Automation >
Filter*), which is evaluated alongside the classic per-interface rules from
*Firewall > Rules*. Rules you create by API appear under Automation, not on the
legacy pages — this surprises people who go looking for them in the GUI.

## Rule fields

Fetch a blank model to see everything the installed version accepts:

```bash
python scripts/opnsense.py get firewall/filter/get_rule
```

The fields that matter most:

| Field | Notes |
| --- | --- |
| `enabled` | `"0"` / `"1"` |
| `sequence` | Evaluation order within the ruleset |
| `action` | `pass`, `block`, `reject` |
| `quick` | `"1"` stops at first match — pf default for these rules |
| `interface` | Interface key (`lan`, `wan`, `opt1`), comma-separated for several |
| `direction` | `in`, `out` |
| `ipprotocol` | `inet`, `inet6` |
| `protocol` | `any`, `TCP`, `UDP`, `ICMP`, ... |
| `source_net` | `any`, CIDR, alias name, or `lan`/`lanip` style tokens |
| `source_port`, `destination_port` | Port, range, or alias |
| `source_not`, `destination_not` | Invert the match |
| `destination_net` | Same vocabulary as `source_net` |
| `gateway` | Force policy routing through a gateway |
| `log` | Log matches to `pflog0` |
| `categories` | UUIDs from `firewall/category` |
| `description` | Always set one — it is how a human finds this rule later |

`source_net` and `destination_net` are flat strings here. In the NAT controllers
the equivalents are nested objects; see [nat.md](nat.md).

## Creating a rule

```bash
cat > rule.json <<'JSON'
{"rule": {
  "enabled": "1",
  "action": "pass",
  "interface": "lan",
  "direction": "in",
  "ipprotocol": "inet",
  "protocol": "TCP",
  "source_net": "lan",
  "destination_net": "any",
  "destination_port": "443",
  "description": "allow LAN to HTTPS"
}}
JSON

python scripts/opnsense.py post firewall/filter/add_rule --data @rule.json
python scripts/opnsense.py post firewall/filter/apply
```

Verify it landed and is actually matching traffic:

```bash
python scripts/opnsense.py get firewall/filter/search_rule
ssh root@<host> 'pfctl -sr -vv' | grep -A2 <uuid>
```

## Ordering

Order is `sequence` plus `move_rule_before`. With `quick` set, the first match
wins, so a broad block placed above a narrow pass silently defeats it. After any
reordering, re-read `search_rule` and confirm the sequence you expect rather
than assuming the move landed.

## Categories and groups

`firewall/category` labels rules for filtering in the GUI and for bulk
operations; `firewall/group` builds interface groups so one rule can cover
several interfaces. Both commit through their own `reconfigure`
(`firewall/alias/reconfigure` for categories, `firewall/group/reconfigure` for
groups).

## Logging

`log: "1"` sends matches to `pflog0`. Read them with:

```bash
python scripts/opnsense.py get diagnostics/firewall/log
ssh root@<host> 'tcpdump -n -e -ttt -i pflog0'
```

Log everything while testing a new rule, then turn it off — a chatty rule on a
busy interface fills the log partition quickly.
