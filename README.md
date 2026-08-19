# opdev-cluster-bot

Slack bot for ACM/Hive OpenShift cluster lifecycle on AWS. Runs on the ACM hub cluster using **Socket Mode** (no public Route).

## Features

- Monitor Hive-provisioned managed clusters (`/opdev-cluster-bot list`, `status`)
- Provision AWS clusters via Hive (`spin <version> <SNO|multinode> <instance-type> [name]`)
- Hibernate / resume with Block Kit confirmation
- Destroy / deprovision bot-managed clusters (`destroy <name>`, double confirm)
- Weekday end-of-day hibernate reminders (17:00 America/New_York)
- Friday auto-hibernate and daily 08:00 resume (opt out of weekend hibernate with `keep-weekend`)
- Ready notification: DM owner console URL, kubeadmin password, and kubeconfig when install completes

## Commands

| Command | Description |
|---------|-------------|
| `/opdev-cluster-bot help` | Usage |
| `/opdev-cluster-bot list` | List clusters and power state |
| `/opdev-cluster-bot spin <ver> SNO\|multinode <itype> [name]` | Provision on AWS |
| `/opdev-cluster-bot hibernate <name>` | Confirm then hibernate |
| `/opdev-cluster-bot resume <name>` | Confirm then resume |
| `/opdev-cluster-bot destroy <name>` | Confirm then deprovision (AWS teardown) |
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

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/design.md](docs/design.md) | Architecture and design decisions |
| [docs/slack-app-setup.md](docs/slack-app-setup.md) | Slack Socket Mode app configuration |
| [docs/hub-smoke-checklist.md](docs/hub-smoke-checklist.md) | Hub deploy verification |

## Makefile

```bash
make help          # list targets
make install       # venv + editable install
make test          # pytest
make run           # Socket Mode bot
make docker-build  # IMAGE=... TAG=0.1.0  (buildx, linux/amd64, --load)
make docker-push   # buildx build --platform linux/amd64 --push
make deploy        # oc apply manifests (secrets separate)
```

## Deploy to the ACM hub

1. Build and push the image (`make docker-build docker-push`, then update image refs in `deploy/`).
2. Create Slack + AWS/pull/ssh secrets (see `deploy/*.example`).
3. Edit `deploy/configmap.yaml` (`BASE_DOMAIN`, `AWS_REGION`, optional `REMINDER_CHANNEL`).
4. Apply: `make deploy` (or `oc apply -k deploy/`).
5. Follow [docs/hub-smoke-checklist.md](docs/hub-smoke-checklist.md).

## Safety

- Never acts on `local-cluster`
- Weekend jobs only touch clusters labeled `opdev.io/managed-by=opdev-cluster-bot`
- Opt out of weekend hibernate with `/opdev-cluster-bot keep-weekend <name>`
