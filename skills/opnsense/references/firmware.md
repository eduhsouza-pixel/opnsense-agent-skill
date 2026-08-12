# Firmware, plugins and patches

Controller `core/firmware` — 26 endpoints, the widest core controller.

## Status and updates

```bash
python scripts/opnsense.py get  core/firmware/status      # pending updates
python scripts/opnsense.py get  core/firmware/running     # current version
python scripts/opnsense.py get  core/firmware/info        # packages and repos
python scripts/opnsense.py get  core/firmware/health      # integrity check
python scripts/opnsense.py get  core/firmware/changelog <version>
python scripts/opnsense.py post core/firmware/update      # package updates
python scripts/opnsense.py post core/firmware/upgrade     # major upgrade
python scripts/opnsense.py get  core/firmware/upgradestatus
```

`status` is served from a cached poll with a ~25 minute skew, so it can lag a
just-published release. Force a refresh:

```bash
ssh root@<host> 'configctl firmware poll'
```

Watch progress with `upgradestatus` — an upgrade is a long-running job and the
POST returns before it finishes.

## Before upgrading

1. Take a config backup and, on ZFS, a boot environment snapshot
   (see [backup-recovery.md](backup-recovery.md)).
2. Read the changelog for the target version. Point releases have broken traffic
   shaping and IDS in the past.
3. Check `health` and free space — an upgrade that runs out of room on `/`
   leaves a half-installed system.
4. On an HA pair, upgrade the backup node first, fail over, verify, then upgrade
   the former primary.

## Plugins

```bash
python scripts/opnsense.py get  core/firmware/get           # available + installed
python scripts/opnsense.py post core/firmware/install <pkg>
python scripts/opnsense.py post core/firmware/remove <pkg>
python scripts/opnsense.py post core/firmware/reinstall <pkg>
python scripts/opnsense.py post core/firmware/lock <pkg>    # pin against updates
python scripts/opnsense.py post core/firmware/unlock <pkg>
python scripts/opnsense.py post core/firmware/resyncPlugins
```

Plugin names are prefixed `os-` (`os-wireguard`, `os-nextcloud-backup`,
`os-haproxy`). Installing a plugin adds its API module, so an endpoint that 404s
may simply mean the plugin is not installed — check `core/firmware/info` before
concluding the feature does not exist.

## Power

```bash
python scripts/opnsense.py post core/firmware/reboot
python scripts/opnsense.py post core/firmware/poweroff
python scripts/opnsense.py post core/system/reboot
```

Confirm with the user before either. On remote hardware without out-of-band
access, a reboot that does not come back is an on-site visit.

## Patches and reverts

```bash
opnsense-patch <commit-hash>          # apply an upstream commit
opnsense-patch <hash2> <hash1>        # reverse: reapply in reverse order
opnsense-revert -r 24.7.1 opnsense    # downgrade the core package
opnsense-update -kr 24.7              # matching kernel
opnsense-shell reboot
```

`opnsense-patch` is how the developers ship a fix before the next release, and
it is normal to be asked to run one on a forum thread or issue. It only works
against the current release's tree — a patch for a different branch will not
apply cleanly.

Reverting is genuinely risky across major releases because the FreeBSD ABI
moves; downgrade the kernel to match, and treat it as a lab operation unless a
maintainer has told you otherwise.

## Audit

```bash
python scripts/opnsense.py get core/firmware/audit
python scripts/opnsense.py get core/firmware/connection
python scripts/opnsense.py get core/firmware/license
```

`audit` runs the security and integrity checks; `connection` verifies the box
can reach its mirror, which is the first thing to check when updates stop
appearing.
