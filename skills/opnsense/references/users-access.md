# Users, privileges and API keys

Module `auth`. Changes to users and groups take effect immediately — there is no
separate apply step here.

| Controller | Commands |
| --- | --- |
| `user` | `search`, `get`, `add`, `set`, `del`, `add_api_key`, `del_api_key`, `search_api_key`, `new_otp_seed`, `download`, `upload` |
| `group` | `search`, `get`, `add`, `set`, `del` |
| `priv` | `search`, `get`, `get_item`, `set`, `set_item` |

## Creating an API key

```bash
python scripts/opnsense.py post auth/user/add_api_key <username>
```

The response contains the key **and the secret**. The secret is not stored on
the firewall and cannot be retrieved again — capture it at creation or generate
a new pair.

In the GUI the same thing lives at *System > Access > Users > API keys*, and
downloads as an INI file.

```bash
python scripts/opnsense.py get  auth/user/search_api_key
python scripts/opnsense.py post auth/user/del_api_key <key>
```

## Least privilege

An API key inherits **all** privileges of its owning user. Using root's key for
automation means any compromise of that key is a full firewall compromise.

Create a dedicated user instead, put it in a group, and grant that group only
the pages the automation touches:

```bash
python scripts/opnsense.py get auth/priv/search              # list available privileges
python scripts/opnsense.py post auth/group/add --data \
  '{"group":{"name":"automation","description":"API automation","member":[]}}'
```

Privileges are page-scoped (`page-firewall-rules`, `page-firewall-alias`,
`page-diagnostics-*`, and so on). A key whose user lacks the privilege gets
**401**, which reads identically to a bad credential — check privileges before
assuming the key is wrong.

## The read-only privilege is not a hard boundary

`user-config-readonly` is enforced by `throwReadOnly()` in the MVC write path,
and there has been a documented parsing flaw where privileges assigned
**directly to a user** as a single comma-separated value bypassed the check —
group privileges were split on commas, the direct-user path was not, so an exact
match failed and writes went through.

Two practical consequences:

- Assign privileges **through groups**, not directly on users.
- Do not rely on `user-config-readonly` as the only thing standing between an
  automation account and your configuration. Scope the account's privileges so
  it cannot reach what it should not change, and keep the API key out of shared
  storage.

## Authentication backends

Local users authenticate through PAM via `opnsense-auth`. LDAP, RADIUS and
TOTP are configured under *System > Access > Servers*. `new_otp_seed` provisions
a TOTP secret for a user.

Note that API key/secret authentication is **independent** of the user's
password and of any MFA on the account — enabling TOTP for a user does not
protect their API keys. Rotate keys on a schedule instead.

## Sessions

```bash
python scripts/opnsense.py get auth/user/search
ssh root@<host> 'tail -f /var/log/audit/latest.log'
```

The audit log records authentication attempts and configuration changes with the
originating user, which is the record to check when a change appears that nobody
claims.
