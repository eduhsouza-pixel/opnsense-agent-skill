# Diagnostics and observability

Module `diagnostics` — 17 controllers, 92 endpoints. All read-only except the
capture and flush operations.

## Interfaces and neighbours

```bash
python scripts/opnsense.py get interfaces/overview/interfaces_info
python scripts/opnsense.py get diagnostics/interface/get_interface_statistics
python scripts/opnsense.py get diagnostics/interface/search_arp
python scripts/opnsense.py get diagnostics/interface/search_ndp
python scripts/opnsense.py get diagnostics/interface/get_routes
python scripts/opnsense.py get diagnostics/interface/get_vip_status
python scripts/opnsense.py get diagnostics/interface/get_pfsync_nodes
```

Shell equivalents: `ifconfig`, `arp -an`, `ndp -an`, `netstat -rn`.

`flush_arp` and `del_route` are the two write operations here — useful when a
stale ARP entry survives a device swap.

## Firewall state and counters

```bash
python scripts/opnsense.py get  diagnostics/firewall/pf_statistics
python scripts/opnsense.py post diagnostics/firewall/query_states --data \
  '{"current":1,"rowCount":50,"searchPhrase":"192.168.1.50"}'
python scripts/opnsense.py get  diagnostics/firewall/stats
python scripts/opnsense.py post diagnostics/firewall/kill_states --data '{"filter":"192.168.1.50"}'
```

`stats` is **per interface**, not per rule. To attribute traffic to a specific
rule, join on the UUID, which pf carries as the rule label:

```bash
ssh root@<host> 'pfctl -sr -vv' | grep -A2 <uuid>
ssh root@<host> 'pfctl -si'        # global counters
ssh root@<host> 'pfctl -ss'        # state table
```

After changing a rule that should stop an existing flow, kill the matching
states — pf keeps established connections alive under the old decision.

## Logs

Circular `clog` files are gone. Logs are plain text, rotated daily, under
`/var/log/<application>/<application>_YYYYMMDD.log`, with `latest.log`
symlinking the current one.

```bash
python scripts/opnsense.py get  diagnostics/firewall/log
python scripts/opnsense.py get  diagnostics/firewall/log_filters
ssh root@<host> 'tail -f /var/log/system/latest.log'
ssh root@<host> 'tail -f /var/log/filter/latest.log'
ssh root@<host> 'opnsense-log -f system'
```

`opnsense-log` is the native reader and has a man page. Plugin logs live under
their own directory (`/var/log/unbound/`, `/var/log/suricata/`, ...). PHP errors
from failing plugins collect in `/tmp/PHP_errors.log` — check there when a GUI
page or endpoint returns an empty result with no visible error.

Live pf logging:

```bash
ssh root@<host> 'tcpdump -n -e -ttt -i pflog0'
```

## Captures, ping, traceroute

These are job-based: `set` the parameters, `start`, poll, then `view` or
`download`.

```bash
python scripts/opnsense.py post diagnostics/packet_capture/set --data \
  '{"interface":"lan","host":"192.168.1.50","count":"100"}'
python scripts/opnsense.py post diagnostics/packet_capture/start
python scripts/opnsense.py get  diagnostics/packet_capture/search_jobs
python scripts/opnsense.py get  diagnostics/packet_capture/view <job>
```

`diagnostics/ping` and `diagnostics/traceroute` follow the same pattern.
`diagnostics/portprobe` tests reachability of a TCP port from the firewall
itself — the fastest way to prove whether a failure is the firewall or upstream.

## System resources

```bash
python scripts/opnsense.py get diagnostics/system/system_resources
python scripts/opnsense.py get diagnostics/system/memory
python scripts/opnsense.py get diagnostics/system/system_disk
python scripts/opnsense.py get diagnostics/system/system_temperature
python scripts/opnsense.py get diagnostics/systemhealth/get_system_health
```

Shell: `top -R`, `df -h`, `zpool status`, `vmstat 1`.

A full `/var` is a frequent and confusing failure — logging and blocklists both
grow — and it makes unrelated services fail in ways that look like configuration
problems. Check `df -h` early.

## DNS

```bash
python scripts/opnsense.py get diagnostics/dns/reverse_lookup <ip>
python scripts/opnsense.py get unbound/diagnostics/stats
python scripts/opnsense.py get unbound/diagnostics/dumpcache
ssh root@<host> 'drill @127.0.0.1 example.com'
```

## Traffic and flows

`diagnostics/traffic/_interface` and `_top` give live throughput; `stream` is a
server-sent-event feed. `diagnostics/networkinsight` exposes NetFlow data once
`diagnostics/netflow` is configured and enabled.

## A triage order that works

1. Is the interface up and addressed? `interfaces_info`
2. Is there a route to the destination? `get_routes`
3. Is a rule blocking it? `pf_statistics`, then the filter log
4. Does DNS resolve? `drill @<firewall>`
5. Can the firewall itself reach it? `portprobe`, `ping`
6. Is the box healthy? `system_resources`, `df -h`

Stop at the first answer that is wrong rather than collecting all six.
