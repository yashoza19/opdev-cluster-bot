# Hub smoke checklist

Run after deploying `opdev-cluster-bot` to the ACM hub.

## Prerequisites

- [ ] Slack app configured (Socket Mode) — see [slack-app-setup.md](slack-app-setup.md)
- [ ] Secret `opdev-cluster-bot-slack` has valid `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`
- [ ] Namespace `opdev-cluster-bot-creds` has `aws-creds`, `pull-secret`, `ssh-privatekey`
- [ ] ConfigMap `BASE_DOMAIN` / `AWS_REGION` match your Hive environment
- [ ] At least one matching `ClusterImageSet` exists for the OCP version you will spin
- [ ] Image in `Deployment`/`CronJob` points at your built image

## Deploy verification

```bash
oc -n opdev-cluster-bot get deploy,pods,cronjob,sa,cm,secret
oc -n opdev-cluster-bot logs deploy/opdev-cluster-bot -f
```

- [ ] Pod is `Running`
- [ ] Logs show Socket Mode started (no token errors)
- [ ] Bot appears online in Slack

## Functional smoke

1. **Help / list**
   - [ ] `/opdev-cluster-bot help`
   - [ ] `/opdev-cluster-bot list` (excludes `local-cluster`)

2. **Dry-run spin**
   - [ ] Set `DRY_RUN=true` on the ConfigMap, rollout restart Deployment
   - [ ] `/opdev-cluster-bot spin 4.16.0 SNO m5.2xlarge smoke-dry`
   - [ ] Message reports dry-run manifests; no new namespace created
   - [ ] Set `DRY_RUN=false` again when ready for real provisions

3. **Hibernate / resume** (use a disposable bot-managed cluster)
   - [ ] `/opdev-cluster-bot hibernate <name>` → confirm button → `ClusterDeployment.spec.powerState=Hibernating`
   - [ ] `/opdev-cluster-bot resume <name>` → confirm → `Running`
   - [ ] `/opdev-cluster-bot status <name>` shows expected fields

4. **Weekend opt-out**
   - [ ] `/opdev-cluster-bot keep-weekend <name>`
   - [ ] Label `opdev.io/weekend-hibernate=false` on the ClusterDeployment

5. **CronJobs (manual trigger)**
   ```bash
   oc -n opdev-cluster-bot create job --from=cronjob/opdev-remind-hibernate remind-now
   oc -n opdev-cluster-bot logs job/remind-now
   ```
   - [ ] Reminder posts to `REMINDER_CHANNEL` or owner DM with Hibernate button
   - [ ] Button handled by the live Deployment

## Rollback / cleanup

- [ ] Scale Deployment to 0 if the bot misbehaves: `oc -n opdev-cluster-bot scale deploy/opdev-cluster-bot --replicas=0`
- [ ] Suspend CronJobs if needed: `oc -n opdev-cluster-bot patch cronjob <name> -p '{"spec":{"suspend":true}}'`
