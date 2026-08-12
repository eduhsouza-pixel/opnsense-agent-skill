# Integrations

Two ways to consume this skill, and they compose:

- **Instruction files** — the agent reads the guidance and calls
  `skills/opnsense/scripts/opnsense.py` through its normal terminal tool. No
  extra process, no dependencies.
- **MCP server** — `skills/opnsense/scripts/mcp_server.py` exposes the same
  capability as six typed tools for any MCP-speaking client.

Both need Python 3.8+ and nothing else. Credentials come from the environment or
a `.env` file; see [`.env.example`](../.env.example).

---

## Instruction files

`AGENTS.md` at the repository root is the cross-tool standard and is picked up
automatically by **Codex CLI, Gemini CLI, OpenCode, Cursor, Zed, Aider** and
others. If your tool reads `AGENTS.md`, you are already done.

For tools with their own format, copy the matching template out of
[`integrations/`](../integrations):

| Tool | Copy to | Template |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/opnsense/` (or install the plugin) | `skills/opnsense/` |
| Cursor | `.cursor/rules/opnsense.mdc` | `integrations/cursor/opnsense.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` | `integrations/copilot/copilot-instructions.md` |
| Windsurf | `.windsurf/rules/opnsense.md` | `integrations/windsurf/opnsense.md` |
| Cline / Roo Code | `.clinerules/opnsense.md` | `integrations/cline/opnsense.md` |
| Zed | `AGENTS.md` (native) | — |
| Codex CLI | `AGENTS.md` (native) | — |
| Gemini CLI | `GEMINI.md` (shipped) | — |
| OpenCode | `AGENTS.md` (native), or `~/.config/opencode/skills/opnsense/` | `skills/opnsense/` |

```bash
git clone https://github.com/eduhsouza-pixel/opnsense-agent-skill
cd opnsense-agent-skill

# Cursor, in your own project
mkdir -p .cursor/rules && cp integrations/cursor/opnsense.mdc .cursor/rules/

# GitHub Copilot
mkdir -p .github && cp integrations/copilot/copilot-instructions.md .github/

# Claude Code
cp -r skills/opnsense ~/.claude/skills/

# OpenCode
cp -r skills/opnsense ~/.config/opencode/skills/
```

The templates are pointers, not copies of the whole body of knowledge — they
carry the critical rules inline and reference `skills/opnsense/references/` for
depth. Keep that directory reachable from the project, or install the skill
form instead.

---

## MCP server

```bash
python skills/opnsense/scripts/mcp_server.py --selftest
```

Ten checks run without touching a firewall. It speaks JSON-RPC 2.0 over stdio
and implements the MCP protocol directly, so there is no SDK to install.

### Tools

| Tool | Credentials | Effect |
| --- | --- | --- |
| `opnsense_find_endpoint` | not needed | Search the offline index by keyword or concept |
| `opnsense_describe_controller` | not needed | List a controller's commands and its commit endpoint |
| `opnsense_get` | required | Read-only API call |
| `opnsense_post` | required | **Mutates the firewall**; supports `dry_run` |
| `opnsense_backup_config` | required | Download the running `config.xml` |
| `opnsense_probe` | required | Connectivity, auth, version |

Set `OPNSENSE_MCP_READONLY=1` to refuse every write while leaving the index and
all reads working — a good default for a shared or exploratory setup.

### Configuration

Replace `/abs/path` with the absolute path to your clone. On Windows use
`python` and a path like `D:\\repos\\opnsense-agent-skill\\...`.

**Claude Code**

```bash
claude mcp add opnsense --env OPNSENSE_URL=https://192.168.1.1 \
  --env OPNSENSE_KEY=... --env OPNSENSE_SECRET=... --env OPNSENSE_INSECURE=1 \
  -- python /abs/path/skills/opnsense/scripts/mcp_server.py
```

**Claude Desktop** — `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "opnsense": {
      "command": "python",
      "args": ["/abs/path/skills/opnsense/scripts/mcp_server.py"],
      "env": {
        "OPNSENSE_URL": "https://192.168.1.1",
        "OPNSENSE_KEY": "...",
        "OPNSENSE_SECRET": "...",
        "OPNSENSE_INSECURE": "1"
      }
    }
  }
}
```

**Cursor** — `.cursor/mcp.json` (or the global `~/.cursor/mcp.json`): same shape
as Claude Desktop.

**Windsurf** — `~/.codeium/windsurf/mcp_config.json`: same shape.

**Cline / Roo Code** — `cline_mcp_settings.json` via the MCP Servers pane: same
shape.

**VS Code** — `.vscode/mcp.json`

```json
{
  "servers": {
    "opnsense": {
      "type": "stdio",
      "command": "python",
      "args": ["/abs/path/skills/opnsense/scripts/mcp_server.py"]
    }
  }
}
```

**Codex CLI** — `~/.codex/config.toml`

```toml
[mcp_servers.opnsense]
command = "python"
args = ["/abs/path/skills/opnsense/scripts/mcp_server.py"]
env = { OPNSENSE_URL = "https://192.168.1.1", OPNSENSE_KEY = "...", OPNSENSE_SECRET = "...", OPNSENSE_INSECURE = "1" }
```

**Gemini CLI** — `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "opnsense": {
      "command": "python",
      "args": ["/abs/path/skills/opnsense/scripts/mcp_server.py"],
      "env": { "OPNSENSE_URL": "https://192.168.1.1", "OPNSENSE_KEY": "...", "OPNSENSE_SECRET": "..." }
    }
  }
}
```

**OpenCode** — `opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "opnsense": {
      "type": "local",
      "command": ["python", "/abs/path/skills/opnsense/scripts/mcp_server.py"],
      "enabled": true,
      "environment": { "OPNSENSE_URL": "https://192.168.1.1", "OPNSENSE_KEY": "...", "OPNSENSE_SECRET": "..." }
    }
  }
}
```

**Zed** — `settings.json`

```json
{
  "context_servers": {
    "opnsense": {
      "source": "custom",
      "command": "python",
      "args": ["/abs/path/skills/opnsense/scripts/mcp_server.py"],
      "env": {}
    }
  }
}
```

MCP configuration shapes move between releases. If a client rejects the block
above, check that client's current MCP documentation — the command and args are
always the same, only the wrapper key changes.

### Verifying

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 | python skills/opnsense/scripts/mcp_server.py
```

You should get a `serverInfo` block naming `opnsense`, then six tools.

---

## Which should you use

Instruction files keep the agent working the way it already does — shell calls,
visible output, nothing extra running. That is usually the better fit for an
agent that is already editing files in a repository.

The MCP server is the better fit when the client has no reliable terminal, when
you want typed tool schemas and per-tool approval prompts, or when you want
`OPNSENSE_MCP_READONLY=1` enforced centrally rather than by convention.

Running both is fine. They share the same index, the same commit-resolution
logic and the same safety behaviour.
