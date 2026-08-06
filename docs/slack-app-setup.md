# Slack app setup (Socket Mode)

Create a Slack app for `opdev-cluster-bot` that talks to Slack over **Socket Mode** (outbound WebSocket). No public OpenShift Route is required.

## 1. Create the app

1. Open [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Name it `opdev-cluster-bot` and pick your workspace.

## 2. Enable Socket Mode

1. **Socket Mode** → toggle **Enable Socket Mode**.
2. Create an App-Level Token with scope `connections:write`.
3. Copy the `xapp-...` token → store as `SLACK_APP_TOKEN`.

## 3. OAuth scopes (Bot Token)

Under **OAuth & Permissions** → **Bot Token Scopes**, add:

| Scope | Why |
|-------|-----|
| `commands` | Slash command `/opdev-cluster-bot` |
| `chat:write` | Channel posts and updates |
| `users:read` | Resolve display names |
| `users:read.email` | Owner email annotations |
| `im:write` | DM hibernate reminders when no channel is set |
| `usergroups:read` | Optional admin group authorization |

Install the app to the workspace and copy the Bot User OAuth Token (`xoxb-...`) → `SLACK_BOT_TOKEN`.

## 4. Slash command

**Slash Commands** → **Create New Command**:

| Field | Value |
|-------|-------|
| Command | `/opdev-cluster-bot` |
| Request URL | _(leave blank / unused in Socket Mode)_ |
| Short Description | ACM/Hive cluster lifecycle helper |
| Usage Hint | `list \| spin \| hibernate \| resume \| status \| keep-weekend \| help` |

## 5. Interactivity

**Interactivity & Shortcuts** → enable Interactivity. In Socket Mode, button/modal payloads arrive on the same socket; no Request URL is required on the hub.

## 6. Hub Secret

```bash
oc -n opdev-cluster-bot create secret generic opdev-cluster-bot-slack \
  --from-literal=SLACK_BOT_TOKEN='xoxb-...' \
  --from-literal=SLACK_APP_TOKEN='xapp-...'
```

Or copy `deploy/secret.yaml.example` to a local file (do not commit) and apply it.

## 7. Invite the bot

Invite `@opdev-cluster-bot` to the reminder channel (if `REMINDER_CHANNEL` is set).
