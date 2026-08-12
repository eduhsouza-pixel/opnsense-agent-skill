# configd and the backend

## Architecture

OPNsense splits cleanly in two. The **frontend** (PHP/Phalcon) owns
`config.xml`, validates input and never runs system commands. The **backend**
(`configd`, written in Python) is the only thing that touches FreeBSD — it
renders service config files from Jinja2 templates and starts, stops and reloads
daemons. They talk over a Unix domain socket.

This is why every API mutation needs a separate apply: the write lands in
`config.xml`, and only the apply asks configd to regenerate the real service
configuration and signal the daemon.

## configctl

`configctl` is the command-line door into that socket.

```bash
configctl configd actions                    # every registered action
configctl configd actions | grep -v "[ ]"    # just the command names
```

Actions are declared in `.conf` files under
`/usr/local/opnsense/service/conf/actions.d/`, in INI form:

```ini
[restart]
command:/usr/local/etc/rc.sshd
parameters:
type:script
message:starting sshd
description:Restart the SSH daemon
```

| Property | Meaning |
| --- | --- |
| `command` | Shell command to run |
| `parameters` | `%s` placeholders filled from the `configctl` arguments |
| `type` | `script` (exit code only), `script_output` (returns stdout, usually JSON), `stream_output` (streaming), `inline` (internal, e.g. template generation) |
| `errors` | `no` ignores the exit code |
| `allowed_groups` | Restrict execution to listed groups |
| `message` | Sent to syslog on execution |
| `description` | Makes the action selectable in the Cron GUI |

A file named `actions_filter.conf` with a `[diag.info]` section becomes
`configctl filter diag.info`. After adding or editing an action file:

```bash
service configd restart
```

## Commonly used commands

```bash
configctl filter reload                     # reload the pf ruleset
configctl filter refresh_aliases            # re-resolve DNS/MAC/URL-table aliases
configctl interface reconfigure lan         # cycle one interface cleanly
configctl interface routes alarm            # force a gateway failover evaluation
configctl unbound check                     # validate Unbound config before restarting
configctl unbound dnsbl                     # rebuild DNS blocklists and apply
configctl openvpn restart <uuid>            # restart one OpenVPN instance
configctl ids update                        # fetch IDS rules and reload
configctl template reload OPNsense/Unbound  # regenerate one service's files
configctl template cleanup OPNsense/Unbound
configctl firmware poll                     # refresh update status
configctl firmware auto-update
configctl system remote backup              # trigger the cloud backup now
configctl system ha_reconfigure_backup      # sync config to the HA peer
configctl system reboot
configctl system halt
configctl zfs scrub <pool>
configctl zfs trim <pool>
```

Anything `configctl` can do is a candidate for the Cron GUI, since actions with
a `description` show up there.

## pluginctl

`pluginctl` is the debug-oriented sibling. It needs root and digs into the PHP
plugin layer:

```bash
pluginctl -h
pluginctl -s                # list services and state
pluginctl -s haproxy restart
pluginctl -c                # list registered configure hooks
pluginctl -c dns:unbound    # fire one hook
pluginctl -c dns            # fire the whole group
```

It narrates what it is doing, which makes it the better tool when a reconfigure
appears to succeed but the daemon does not pick up the change.

## Extending the environment

Add variables for configd actions by dropping a file in
`/usr/local/opnsense/service/conf/configd.conf.d/`:

```ini
[environment]
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=http://proxy:8080
NO_PROXY=192.168.1.2
```

Vendor files are read first and later definitions win, so redefining an existing
key (like `PATH`) overrides the shipped value. Restart configd afterwards.
