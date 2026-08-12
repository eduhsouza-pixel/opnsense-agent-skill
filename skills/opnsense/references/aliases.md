# Aliases

Controller `firewall/alias`. Commit with `POST /api/firewall/alias/reconfigure`.

An alias is a named set that firewall and NAT rules reference by name. Behind
the scenes each one becomes a pf table.

## Endpoints

| Method | Command | Params |
| --- | --- | --- |
| GET | `search_item` | grid query |
| GET | `get_item` | `<uuid>` |
| GET | `get_alias_u_u_i_d` / `getAliasUUID` | `<name>` — look up by name |
| POST | `add_item` / `set_item` / `del_item` / `toggle_item` | |
| POST | `reconfigure` | commit |
| GET | `export` / POST `import` | bulk JSON |
| GET | `get_table_size` | current pf table sizes |
| GET | `list_countries` / `get_geo_i_p` | GeoIP inputs |
| GET | `list_categories`, `list_network_aliases`, `list_user_groups` | |
| POST | `update` | refresh dynamic content |

## Types

| Type | Content |
| --- | --- |
| `host` | Individual IPs or hostnames |
| `network` | CIDR networks |
| `port` | Ports and ranges |
| `url` | Fetched once from a URL |
| `urltable` | Fetched and refreshed on an interval — use this for blocklists |
| `geoip` | Country codes; needs a configured MaxMind source |
| `networkgroup` | Combines other aliases |
| `mac` | MAC address prefixes |
| `external` | Populated by something outside OPNsense (`pfctl -t ... -T add`) |
| `dynipv6host` | Tracks a dynamic IPv6 prefix |

## Creating one

```json
{"alias": {
  "enabled": "1",
  "name": "blocked_hosts",
  "type": "host",
  "content": "203.0.113.10\n203.0.113.11",
  "description": "manually blocked"
}}
```

`content` is newline-separated. The `name` must be a valid pf table name —
letters, digits and underscore, no spaces or hyphens.

```bash
python scripts/opnsense.py post firewall/alias/add_item --data @alias.json
python scripts/opnsense.py post firewall/alias/reconfigure
```

## Refreshing dynamic aliases

`urltable` and hostname-based aliases resolve on a schedule, not on apply:

```bash
python scripts/opnsense.py post firewall/alias/update
ssh root@<host> 'configctl filter refresh_aliases'
```

## Orphaned tables

`firewall/filter/apply` runs `filter reload skip_alias`, which does not rebuild
pf tables. Deleting an alias therefore leaves its table loaded, still matching
traffic in any rule that has not been reloaded, and even a full
`configctl filter reload` will not clear it:

```bash
ssh root@<host> 'pfctl -sT'                    # list tables
ssh root@<host> 'pfctl -t blocked_hosts -T show'
ssh root@<host> 'pfctl -t blocked_hosts -T kill'   # the only way to remove it
```

Check `pfctl -sT` after deleting any alias.

## Size limits

Large blocklists can exceed the pf table entry limit, and the failure mode is a
partially loaded table rather than an error. Check with:

```bash
python scripts/opnsense.py get firewall/alias/get_table_size
```

Raise `net.pf.request_maxcount` via *System > Settings > Tunables*
(`core/tunables`) if a legitimate list is being truncated.
