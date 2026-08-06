# opdev-cluster-bot

Slack bot for ACM/Hive OpenShift cluster lifecycle on AWS. Runs on the ACM hub cluster using **Socket Mode** (no public Route).

## Features

- Monitor Hive-provisioned managed clusters (`/opdev-cluster-bot list`, `status`)
- Provision AWS clusters via Hive (`spin <version> <SNO|multinode> <instance-type> [name]`)
- Hibernate / resume with Block Kit confirmation
- Weekday end-of-day hibernate reminders (17:00 America/New_York)
- Friday auto-hibernate and Monday resume (opt out with `keep-weekend`)

## Commands

| Command | Description |
|---------|-------------|
| `/opdev-cluster-bot help` | Usage |
| `/opdev-cluster-bot list` | List clusters and power state |
| `/opdev-cluster-bot spin <ver> SNO\|multinode <itype> [name]` | Provision on AWS |
| `/opdev-cluster-bot hibernate <name>` | Confirm then hibernate |
| `/opdev-cluster-bot resume <name>` | Confirm then resume |
| `/opdev-cluster-bot status <name>` | Cluster details |
| `/opdev-cluster-bot keep-weekend <name>` | Skip weekend auto-hibernate |

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

cp .env.example .env
# set SLACK_BOT_TOKEN, SLACK_APP_TOKEN, BASE_DOMAIN, etc.

export $(grep -v '^#' .env | xargs)
opdev-cluster-bot
```

Requires kubeconfig (or in-cluster SA) with access to `ManagedCluster` and `ClusterDeployment`.

Set `DRY_RUN=true` to render provision manifests without creating resources.

### Tests

```bash
pip install -e ".[dev]"
pytest
```

## Slack app setup

See [docs/slack-app-setup.md](docs/slack-app-setup.md).

## Deploy to the ACM hub

1. Build and push the image (update `deploy/kustomization.yaml` / `deployment.yaml` image).
2. Create Slack + AWS/pull/ssh secrets (see `deploy/*.example`).
3. Edit `deploy/configmap.yaml` (`BASE_DOMAIN`, `AWS_REGION`, optional `REMINDER_CHANNEL`).
4. Apply:

```bash
oc apply -f deploy/namespace.yaml
oc apply -f deploy/rbac.yaml
oc apply -f deploy/configmap.yaml
# create secrets (do not commit real values)
oc apply -f deploy/deployment.yaml
oc apply -f deploy/cronjobs.yaml
# or: oc apply -k deploy/
```

5. Follow [docs/hub-smoke-checklist.md](docs/hub-smoke-checklist.md).

## Safety

- Never acts on `local-cluster`
- Weekend jobs only touch clusters labeled `opdev.io/managed-by=opdev-cluster-bot`
- Opt out of weekend hibernate with `/opdev-cluster-bot keep-weekend <name>`
