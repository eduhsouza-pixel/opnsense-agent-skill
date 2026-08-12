# Backup, restore and lockout recovery

## Backups on the box

Every configuration change writes a timestamped copy to `/conf/backup/`. How
many are kept is the **Backup Count** setting at *System > Configuration >
Backups*; the default history is short enough that a series of bad changes can
push the last good config out of the window.

## Via the API

```bash
python scripts/opnsense.py backup --out pre-change.xml     # GET core/backup/download/this
python scripts/opnsense.py get core/backup/backups this    # list stored revisions
python scripts/opnsense.py get core/backup/diff this <b1> <b2>
python scripts/opnsense.py post core/backup/revert_backup <backup>
```

`core/backup/revert_backup` is a genuine API rollback to a stored revision — it
is easy to miss because the *Backups* GUI page is legacy PHP, which leads a lot
of documentation to claim restore is impossible over the API. It is not.

There is still no API endpoint that **uploads** an arbitrary `config.xml`. For
that, copy the file in and reload:

```bash
scp config.xml root@<host>:/conf/config.xml
ssh root@<host> /usr/local/etc/rc.reload_all
```

## ZFS boot environments

On ZFS installs, `core/snapshots` manages boot environments — the cleanest
rollback available because it covers packages and kernel, not just config:

```bash
python scripts/opnsense.py get  core/snapshots/is_supported
python scripts/opnsense.py post core/snapshots/add --data '{"name":"pre-change"}'
python scripts/opnsense.py get  core/snapshots/search
python scripts/opnsense.py post core/snapshots/activate <uuid>   # takes effect on reboot
```

Take one before firmware upgrades and before any change you cannot easily undo.

## Recovering from a lockout

In escalating order of disruption.

**1. Dead-man switch (set this up *before* the change).**

```bash
echo "pfctl -d" | at now + 5 minutes
```

If the new ruleset cuts you off, wait five minutes and the packet filter
disables itself. Once you have confirmed access still works, cancel it:

```bash
atq          # find the job id
atrm <id>
```

**2. Console menu.** With serial, VGA or VM console access, log in and choose
**option 13, "Restore a backup"**. It lists the revisions in `/conf/backup/` by
timestamp.

**3. Boot-time shell.** If the system will not come up far enough for the menu:
power on, wait for the text to start scrolling, then hold `CTRL` and tap `C` to
break into a shell (no authentication required).

```bash
cd /conf/backup && ls -la
cp /conf/config.xml /conf/config.xml.broken
cp /conf/backup/config-<timestamp>.xml /conf/config.xml
reboot
```

**4. USB import.** Format a FAT32 stick, create `/conf/config.xml` on it with a
**decrypted** backup. Boot the installer and press a key at "Press any key to
start the configuration importer", then give the device name (`da0`, `da1`,
`nvd0`). On an already-installed system, run `opnsense-importer` from the shell.

## Reverting firmware

```bash
opnsense-revert -r 24.7.1 opnsense      # downgrade the core package
opnsense-revert -r 18.1.4 strongswan    # downgrade one service package
opnsense-update -kr 24.7                # matching kernel, if the kernel moved too
opnsense-shell reboot
```

Downgrading the core package across a major release without matching the kernel
produces ABI mismatches. Check whether the kernel changed before reverting, and
treat kernel reverts as a test-machine operation.

## Cloud backup

*System > Configuration > Backups* can push an encrypted copy to SFTP, Nextcloud
(needs the `os-nextcloud-backup` plugin) or Google Drive. It uploads once on
setup, then at most once per day, and only when the configuration actually
changed. Encryption is mandatory and uses the same scheme as a manual export, so
restoring onto a fresh install is straightforward — but keep the encryption
password somewhere other than the firewall.
