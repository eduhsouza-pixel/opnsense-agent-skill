# DHCP

Three implementations coexist. Identify which one is actually serving a segment
before changing anything — running two on the same interface produces
intermittent, hard-to-trace lease failures.

| Server | Module | Status |
| --- | --- | --- |
| Kea | `kea` | Current default for new installs |
| Dnsmasq | `dnsmasq` | DNS + DHCP together, increasingly the recommended path |
| ISC DHCP | `dhcpv4` / `dhcpv6` plugins | Legacy, removed from newer releases |

## Kea

Commit with `POST /api/kea/service/reconfigure`.

| Controller | Purpose |
| --- | --- |
| `dhcpv4` / `dhcpv6` | `subnet`, `reservation`, `option`, `peer` (and `pd_pool` for v6) |
| `leases` | `search`, `del_lease` |
| `ctrl_agent` | Control agent — needed for API-driven management and HA |
| `ddns` | Dynamic DNS updates |
| `service` | `reconfigure`, `restart`, `start`, `stop`, `status` |

```bash
python scripts/opnsense.py get kea/dhcpv4/search_subnet
python scripts/opnsense.py get kea/leases/search
```

### A subnet

```json
{"subnet4": {
  "subnet": "192.168.1.0/24",
  "pools": "192.168.1.100-192.168.1.200",
  "option_data": {"routers": "192.168.1.1", "domain_name_servers": "192.168.1.1"},
  "description": "LAN"
}}
```

Fetch the blank model first — the wrapper key and the `option_data` shape differ
between releases:

```bash
python scripts/opnsense.py get kea/dhcpv4/get_subnet
```

### Reservations

```bash
python scripts/opnsense.py post kea/dhcpv4/add_reservation --data \
  '{"reservation":{"subnet":"<subnet-uuid>","hw_address":"00:11:22:33:44:55","ip_address":"192.168.1.50","hostname":"printer"}}'
python scripts/opnsense.py post kea/service/reconfigure
```

`download_reservations` / `upload_reservations` handle CSV bulk changes, which
is far less error-prone than looping `add_reservation` for a large migration.

Kea keeps leases in `/var/db/kea`. OPNsense reads them directly, so a reservation
change takes effect without restarting the service — but the *subnet* definition
still needs the reconfigure.

## Dnsmasq DHCP

Commit with `POST /api/dnsmasq/service/reconfigure`.

`dnsmasq/settings/add_range` defines a pool; `add_host` creates a static
mapping that is simultaneously a DNS record — the reason to prefer Dnsmasq when
you want leases and local name resolution to stay consistent automatically.

```bash
python scripts/opnsense.py get dnsmasq/leases/search
```

For IPv6, a range carries the Router Advertisement configuration with it rather
than needing a separate radvd entry.

## Migrating ISC to Kea

*Services > ISC DHCPv4* offers an export that seeds the Kea configuration.
Afterwards:

1. Verify every static mapping came across — reservations are the usual casualty.
2. Confirm only one server is enabled per interface.
3. Test a real lease from a client, not just the service status.
4. Enable the control agent only if you need API management or HA.

## Diagnosing

```bash
python scripts/opnsense.py get kea/leases/search
python scripts/opnsense.py get dnsmasq/leases/search
python scripts/opnsense.py get diagnostics/interface/search_arp
ssh root@<host> 'tail -f /var/log/dhcpd/latest.log'
```

If a client gets no address: confirm which server owns the interface, check that
the firewall rules allow UDP 67/68 on that interface, and look for a second DHCP
server on the segment with `tcpdump -ni <if> port 67 or port 68`.
