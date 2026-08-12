# NAT

Four controllers, all committing through `POST /api/firewall/filter/apply`:

| Purpose | Controller |
| --- | --- |
| Port forward (destination NAT) | `firewall/d_nat` |
| Outbound NAT (source NAT) | `firewall/source_nat` |
| 1:1 NAT | `firewall/one_to_one` |
| IPv6 prefix translation | `firewall/npt` |

`firewall/dnat` and `firewall/nat` do not exist and return 404. The router
derives `d_nat` from `DNatController`.

Each exposes the same command set: `search_rule`, `get_rule`, `add_rule`,
`set_rule`, `del_rule`, `toggle_rule`, `toggle_rule_log`, `move_rule_before`.

## Port forward payload

Unlike filter rules, source and destination are **nested objects**:

```json
{"rule": {
  "enabled": "1",
  "interface": "wan",
  "protocol": "TCP",
  "source": {"network": "any", "port": "", "not": "0"},
  "destination": {"network": "wanip", "port": "8443", "not": "0"},
  "target": "192.168.1.50",
  "local-port": "443",
  "log": "1",
  "description": "publish internal HTTPS"
}}
```

Note `local-port` uses a hyphen, not an underscore.

Useful address tokens: `lanip` / `wanip` (the interface's own address), `lan` /
`wan` (the interface network), `any`, a CIDR, or an alias name.

```bash
python scripts/opnsense.py post firewall/d_nat/add_rule --data @pf.json
python scripts/opnsense.py post firewall/filter/apply
```

## Associated filter rules

A port forward does not by itself permit traffic. Either create the matching
`pass` rule on the WAN interface, or set the rule's automatic-filter option if
the installed version exposes it in the blank model. Check with:

```bash
python scripts/opnsense.py get firewall/d_nat/get_rule
```

If you create the pass rule yourself, its destination must be the **internal**
address and port (post-translation), not the published one.

## Outbound NAT

`firewall/source_nat` is the MVC implementation of *Firewall > NAT > Outbound*.
It has two limits worth knowing before you use it:

- Rules created here are **not visible** on the legacy Outbound page, and vice
  versa. The two views do not merge.
- The outbound NAT **mode** (automatic / hybrid / manual) cannot be changed
  through this controller. Set it in the GUI first; if the mode is still
  "automatic", manual rules are ignored.

On an HA pair, outbound NAT should translate to the CARP VIP rather than a
node's physical address, or return traffic lands on the wrong firewall.

## Verifying

```bash
python scripts/opnsense.py get firewall/d_nat/search_rule
ssh root@<host> 'pfctl -sn'                       # active NAT ruleset
ssh root@<host> 'pfctl -ss | grep 192.168.1.50'   # states through the forward
```

Remember `pfctl` prints service names rather than port numbers — 443 shows as
`https`. Match on the rule UUID instead.
