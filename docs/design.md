# opdev-cluster-bot design

## Goals

Provide a Slack-first operator for the team ACM hub that:

1. Monitors Hive-provisioned AWS OpenShift clusters
2. Provisions new clusters via slash commands
3. Sends end-of-day hibernate reminders
4. Auto-hibernates on weekends unless a cluster opts out

## Locked decisions

| Decision | Choice |
|----------|--------|
| Cloud | AWS (Hive IPI); power via `ClusterDeployment.spec.powerState` |
| Runtime | Python 3.12 + Slack Bolt |
| Slack transport | Socket Mode (outbound WSS; no public Route) |
| Timezone | `America/New_York` |
| Deploy target | Team hub with ACM/MCE + Hive |

## Architecture

```text
Slack  <-->  Socket Mode Deployment (replicas: 1)
                |-- slash commands / Block Kit actions
                |-- ACM/Hive APIs (ManagedCluster, ClusterDeployment)

CronJobs (same image, same SA)
  remind-hibernate     Mon-Fri 17:00 ET
  weekend-hibernate    Fri 18:00 ET
  monday-resume        Mon 08:00 ET
```

### Components

| Path | Role |
|------|------|
| `src/opdev_cluster_bot/app.py` | Bolt Socket Mode entry |
| `src/opdev_cluster_bot/commands/` | Slash command router |
| `src/opdev_cluster_bot/actions/` | Button handlers (hibernate/resume confirm) |
| `src/opdev_cluster_bot/acm/` | Inventory, power, provision against hub APIs |
| `jobs/` | CronJob entrypoints |
| `deploy/` | Namespace, RBAC, ConfigMap, Deployment, CronJobs |

### Data flow — spin

1. User: `/opdev-cluster-bot spin 4.16.0 SNO m5.2xlarge mycluster`
2. Bot acks Slack within 3s, resolves owner email
3. Looks up `ClusterImageSet` for version
4. Creates namespace, copies creds secrets, install-config Secret, `ClusterDeployment`, `ManagedCluster`, `KlusterletAddonConfig`
5. Labels: `opdev.io/managed-by=opdev-cluster-bot`, `opdev.io/weekend-hibernate=true`
6. Annotations: owner Slack ID/email, topology, instance type

### Data flow — hibernate

1. Slash command or reminder button → Block Kit confirm
2. Patch `ClusterDeployment.spec.powerState` to `Hibernating` or `Running`
3. Never act on `local-cluster`

### Scheduling

- Reminders post Block Kit; clicks are handled by the live Deployment
- Weekend job skips clusters with `opdev.io/weekend-hibernate=false`
- Monday resume only for bot-managed clusters that participate in weekend hibernate

## Configuration

Injected via ConfigMap + Secret (see `deploy/`):

- Slack: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- Hive: `AWS_REGION`, `BASE_DOMAIN`, creds namespace/secret names
- Behavior: `DRY_RUN`, `MAX_CONCURRENT_PROVISIONS`, `REMINDER_CHANNEL`, `ADMIN_SLACK_GROUP_IDS`

## Security / guardrails

- In-cluster ServiceAccount; least-privilege ClusterRoles (no cluster-admin)
- Socket Mode: single replica
- Destructive power changes require confirm dialogs
- Weekend automation scoped to bot-managed label set

## Out of scope (MVP)

- Destroy/deprovision command
- Azure/GCP backends
- ClusterPool / claim flow
- HTTP Events API / multi-replica HA
- Cost estimates in Slack messages

## Related docs

- [Slack app setup](slack-app-setup.md)
- [Hub smoke checklist](hub-smoke-checklist.md)
- [README](../README.md)
