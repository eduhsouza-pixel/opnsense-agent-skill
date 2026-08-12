# High availability — CARP and pfsync

Three independent mechanisms have to all be right. Most broken HA pairs have one
of them missing.

| Mechanism | Purpose | Where |
| --- | --- | --- |
| CARP virtual IPs | Shared address that fails over | `interfaces/vip_settings` |
| pfsync | Replicates the pf state table | *Interfaces > Settings*, sync interface |
| XMLRPC sync | Copies configuration to the peer | `core/hasync` |

Without pfsync, failover drops every established connection. Without XMLRPC
sync, the backup runs a stale configuration and fails over into a broken state.

## Endpoints

```bash
python scripts/opnsense.py get  core/hasync/get
python scripts/opnsense.py post core/hasync/set --data @hasync.json
python scripts/opnsense.py post core/hasync/reconfigure
python scripts/opnsense.py get  core/hasync_status/services
python scripts/opnsense.py get  core/hasync_status/version
python scripts/opnsense.py get  diagnostics/interface/get_vip_status
python scripts/opnsense.py get  diagnostics/interface/get_pfsync_nodes
```

`core/hasync_status` can restart services on the **remote** node
(`remote_service`, `restart_all`), which is how you recover a peer whose
services did not come up after a sync.

## CARP virtual IPs

```bash
python scripts/opnsense.py get  interfaces/vip_settings/get_unused_vhid
python scripts/opnsense.py post interfaces/vip_settings/add_item --data \
  '{"vip":{"mode":"carp","interface":"lan","subnet":"192.168.1.1","subnet_bits":"24","vhid":"1","password":"<shared>","advbase":"1","advskew":"0"}}'
python scripts/opnsense.py post interfaces/vip_settings/reconfigure
```

Rules that hold across a working pair:

- The **VHID must be unique per broadcast domain**, and identical on both nodes
  for the same VIP. A duplicate VHID on the segment causes both nodes to think
  they are backup, or both master.
- The **password must match** on both nodes for that VHID.
- `advskew` decides who wins: lower is master. Give the primary `0` and the
  backup something like `100`.
- Each node keeps its own physical address on the interface; the CARP address is
  additional.

## What clients and rules must point at

- Client default gateway: the **CARP VIP**, never a node's physical address.
- Outbound NAT: translate to the **CARP VIP**, or return traffic arrives at the
  wrong node.
- DHCP, DNS and VPN endpoints advertised to clients: the **CARP VIP**.

## XMLRPC configuration sync

Configured on the **primary only**, pointing at the backup's physical address
with a username and password. Select the sections to replicate — normally all of
them: rules and NAT, aliases and schedules, VPNs, DHCP and DNS, IDS, certificates,
users.

Sync direction is one-way. Changes made directly on the backup are overwritten
and silently lost, which is why the backup should be treated as read-only.

Force a sync and service restart on the peer:

```bash
ssh root@<primary> 'configctl system ha_reconfigure_backup'
```

## Verifying

```bash
python scripts/opnsense.py get diagnostics/interface/get_vip_status
ssh root@<host> 'ifconfig | grep -A2 carp'
ssh root@<host> 'pfctl -si | grep -i pfsync'
ssh root@<host> 'tcpdump -ni <sync-if> proto carp'
```

A healthy pair shows exactly one MASTER and one BACKUP per VHID. **Both showing
MASTER** means CARP advertisements are not crossing — check that the firewall
rules on the sync interface permit the CARP protocol (IP protocol 112), and that
the switch is not filtering multicast.

## Upgrading a pair

Upgrade the backup, fail over to it, verify real traffic, then upgrade the
former primary. Never upgrade both at once — and check
`core/hasync_status/version` afterwards, because a version mismatch between
nodes can break XMLRPC sync while CARP keeps looking healthy.
