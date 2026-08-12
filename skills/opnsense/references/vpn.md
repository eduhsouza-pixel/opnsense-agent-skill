# VPN — WireGuard, IPsec, OpenVPN

## WireGuard

Module `wireguard`, commit with `POST /api/wireguard/service/reconfigure`.

| Controller | Commands |
| --- | --- |
| `server` | `search_server`, `get_server`, `add_server`, `set_server`, `del_server`, `toggle_server`, `key_pair` |
| `client` | `search_client`, `get_client`, `add_client`, `set_client`, `del_client`, `toggle_client`, `psk`, `add_client_builder`, `get_client_builder`, `get_server_info`, `list_servers` |
| `general` | `get`, `set` — global enable |
| `service` | `reconfigure`, `restart`, `start`, `stop`, `status`, `show` |

"Client" here means **peer**, not a client-mode tunnel.

```bash
python scripts/opnsense.py get  wireguard/server/key_pair      # generate a keypair
python scripts/opnsense.py post wireguard/server/add_server --data @wg.json
python scripts/opnsense.py post wireguard/service/reconfigure
python scripts/opnsense.py get  wireguard/service/show         # handshakes and transfer
```

Three things account for most broken WireGuard tunnels:

- **`allowedips` on the peer** must contain the addresses that peer is allowed to
  send from. Too narrow silently drops traffic; `0.0.0.0/0` on a site-to-site
  peer captures everything.
- A **firewall rule on the WireGuard interface** is still required — the tunnel
  coming up does not mean traffic is permitted.
- The **WAN rule** must allow the listen port (UDP, default 51820).

`service/show` is the fastest triage: a peer with no recent handshake is a
connectivity or key problem; a handshake with no transfer is a routing or
firewall problem.

## IPsec

Module `ipsec`, commit with `POST /api/ipsec/service/reconfigure`. It is the
largest VPN module (89 endpoints) because it spans both the modern
`connections` model (swanctl) and the legacy tunnel configuration.

```bash
python scripts/opnsense.py show ipsec/connections
python scripts/opnsense.py show ipsec/sessions
python scripts/opnsense.py get  ipsec/sessions/search_phase1
```

Prefer the `connections` controller for anything new — the legacy tunnel
endpoints map to the older GUI and the two do not merge cleanly.

Phase 1 up but no traffic almost always means the phase 2 selectors do not match
on both ends, or the traffic never reaches the tunnel because no rule sends it
there.

## OpenVPN

Module `openvpn`, commit with `POST /api/openvpn/service/reconfigure`.

| Controller | Purpose |
| --- | --- |
| `instances` | `search`, `get`, `add`, `set`, `del`, `toggle`, plus static-key management and `gen_key` |
| `service` | `search_sessions`, `kill_session`, `search_routes`, `restart_service`, `start_service`, `stop_service` |
| `client_overwrites` | Per-client overrides (CSC) |
| `export` | Client config bundles: `providers`, `templates`, `download`, `accounts` |

```bash
python scripts/opnsense.py get openvpn/instances/search
python scripts/opnsense.py get openvpn/service/search_sessions
python scripts/opnsense.py post openvpn/service/kill_session --data '{"session":"<id>"}'
```

Restart a single instance without touching the others:

```bash
ssh root@<host> 'configctl openvpn restart <uuid>'
```

`export/download` produces ready-to-hand-out client configuration — it needs a
matching provider and template, which is why it 404s or returns empty on an
instance that has no user-auth backend configured.

## Certificates

All three consume certificates from `trust` (`trust/ca`, `trust/cert`,
`trust/crl`), committed with `trust/settings/reconfigure`. Create or import the
CA and certificate there first; VPN instances only reference them by UUID.

## Choosing

WireGuard is the fastest and simplest, and the right default for
firewall-to-firewall and modern roaming clients. IPsec is the interoperability
choice when the far end is someone else's equipment. OpenVPN earns its place
when you need TCP transport, port 443 traversal, or per-user certificate
workflows that already exist.
