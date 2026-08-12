# Interfaces, VLANs and routing

## Interfaces

Module `interfaces`, one controller per interface type. Every `*_settings`
controller has its own `reconfigure` — that is the commit step for that type.

| Controller | Manages |
| --- | --- |
| `settings` | General interface options |
| `overview` | Live state: `interfaces_info`, `get_interface`, `export`, `reload_interface` |
| `vlan_settings` | VLANs (not `vlan`) |
| `lagg_settings` | Link aggregation |
| `bridge_settings` | Bridges |
| `vip_settings` | Virtual IPs, including CARP; `get_unused_vhid` |
| `gif_settings`, `gre_settings`, `vxlan_settings` | Tunnels |
| `loopback_settings`, `neighbor_settings` | Loopbacks, static ARP/NDP |

All of them use `search_item` / `get_item` / `add_item` / `set_item` /
`del_item`.

### Current state

```bash
python scripts/opnsense.py get interfaces/overview/interfaces_info
python scripts/opnsense.py get interfaces/overview/get_interface <if>
```

### Adding a VLAN

```json
{"vlan": {"if": "em1", "tag": "20", "pcp": "0", "descr": "guest"}}
```

```bash
python scripts/opnsense.py post interfaces/vlan_settings/add_item --data @vlan.json
python scripts/opnsense.py post interfaces/vlan_settings/reconfigure
```

Creating the VLAN device does not assign it. Assignment and addressing still
happen at *Interfaces > Assignments*, which is legacy PHP with no MVC endpoint —
this is one of the few places the API cannot finish the job alone.

### Resetting an interface

```bash
ssh root@<host> 'configctl interface reconfigure lan'
```

This tears connectivity down and brings it back cleanly. Do not run it against
the interface carrying your session without a dead-man switch armed.

## Gateways

Module `routing`, controller `settings`:

```
search_gateway, get_gateway, add_gateway, set_gateway, del_gateway,
toggle_gateway, reconfigure
```

```bash
python scripts/opnsense.py get routing/settings/search_gateway
python scripts/opnsense.py get routes/gateway/status      # live up/down + RTT/loss
```

Key fields: `interface`, `gateway` (next hop), `monitor` (address to probe —
set it to something that actually answers, not the gateway itself if it drops
ICMP), `priority`, `defaultgw`, `far_gw`.

Force a failover evaluation:

```bash
ssh root@<host> 'configctl interface routes alarm'
```

## Static routes

Module `routes`, controller `routes` — and the commands here are **all
lowercase with no separator**, unlike the rest of the API:

```
searchroute, getroute, addroute, setroute, delroute, toggleroute, reconfigure
```

```bash
python scripts/opnsense.py get routes/routes/searchroute
python scripts/opnsense.py post routes/routes/addroute --data \
  '{"route":{"network":"10.20.0.0/16","gateway":"WAN_GW","descr":"branch"}}'
python scripts/opnsense.py post routes/routes/reconfigure
```

Verify against the kernel, which is the only view that counts:

```bash
ssh root@<host> 'netstat -rn'
python scripts/opnsense.py get diagnostics/interface/get_routes
```

## Policy routing

To send selected traffic out a specific gateway, set `gateway` on a **filter
rule** rather than adding a static route. Static routes are destination-based
only; the rule-level gateway is what implements source- or service-based policy
routing.
