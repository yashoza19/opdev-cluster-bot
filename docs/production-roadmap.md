# Production roadmap & feature backlog

Living checklist for taking `opdev-cluster-bot` from hub smoke to team production.
Update status as work lands; prefer small PRs per item.

**Legend:** `done` · `in progress` · `todo` · `nice-to-have` · `wont-do (MVP)`

---

## How credentials & install-config work today

Shared secrets live in namespace `opdev-cluster-bot-creds` (names from ConfigMap):

| Secret | Purpose |
|--------|---------|
| `aws-creds` | Hive AWS platform credentials (`aws_access_key_id` / `aws_secret_access_key`) |
| `pull-secret` | OpenShift pull secret (`kubernetes.io/dockerconfigjson`) |
| `ssh-privatekey` | SSH private key for install / node access |

On `/spin`, the bot:

1. Renders **install-config** from Jinja (`templates/install-config-aws.yaml.j2`) using `BASE_DOMAIN`, `AWS_REGION`, topology, and instance type. `pullSecret` / `sshKey` fields in that YAML are empty; Hive injects them from secret refs.
2. Creates the cluster namespace.
3. **Copies** the three shared secrets into that namespace (same names).
4. Creates `{cluster}-install-config` Secret with `install-config.yaml`.
5. Creates `ClusterDeployment` that references:
   - `platform.aws.credentialsSecretRef` → `aws-creds`
   - `provisioning.installConfigSecretRef` → `{cluster}-install-config`
   - `provisioning.sshPrivateKeySecretRef` → `ssh-privatekey`
   - `pullSecretRef` → `pull-secret`
6. Creates `ManagedCluster` + `KlusterletAddonConfig`.

Hive then provisions IPI. After install succeeds, Hive usually writes (in the cluster namespace):

- admin kubeconfig Secret (often `{cd-name}-admin-kubeconfig` or similar)
- kubeadmin password Secret (often `{cd-name}-admin-password`)

The bot does **not** yet read or DM those — that is a P0 below.

---

## Validation to finish before calling it “production-ready”

### A. Provision path (you are here)

- [ ] `spin` succeeds end-to-end; `ClusterDeployment` reaches `Installed` / `Ready`
- [ ] Spoke appears as `ManagedCluster` joined / available (ACM)
- [ ] Console URL / API reachable for SNO and (separately) multinode
- [ ] Secrets copied only into the new namespace; hub `opdev-cluster-bot-creds` unchanged
- [ ] Concurrent cap: second/third spins blocked at `MAX_CONCURRENT_PROVISIONS`
- [ ] Bad inputs: unknown version, invalid name, missing ClusterImageSet → clear Slack error
- [ ] Cleanup of failed / leftover namespaces after failed spins

### B. Power & lifecycle (existing commands)

- [ ] `hibernate` / `resume` with Block Kit confirm on a real installed cluster
- [ ] `status` / `list` accuracy (power, owner, weekend label, version/topology annotations)
- [ ] `keep-weekend` flips label; Friday job skips that cluster
- [ ] Never touches `local-cluster`

### C. CronJobs (America/New_York)

- [ ] Manual Job from `opdev-remind-hibernate` → owner DM or `REMINDER_CHANNEL` + Hibernate button works
- [ ] Manual Job from `opdev-weekend-hibernate` hibernates bot-managed Running clusters
- [ ] Manual Job from `opdev-daily-resume` resumes all hibernating bot-managed clusters
- [ ] Timezone / schedule correct on the hub (CronJob `schedule` + `TZ`)

### D. Ops / security

- [ ] SA is not cluster-admin; RBAC sufficient for spin/hibernate/list
- [ ] Slack tokens only in Secret; image pull policy / Quay access documented
- [ ] Document rotate procedure for AWS keys, pull-secret, Slack tokens
- [ ] Rollback: scale Deployment to 0; suspend CronJobs
- [ ] Logging: provision failures and power changes are greppable

---

## Feature backlog

Hub validation tracker: [#7](https://github.com/yashoza19/opdev-cluster-bot/issues/7).

### P0 — needed before broad team use

| ID | Feature | Issue | Status | Notes |
|----|---------|-------|--------|-------|
| P0-1 | **Ready notification + credentials DM** | [#8](https://github.com/yashoza19/opdev-cluster-bot/issues/8) | `todo` | When CD becomes installed, DM requester: console URL, kubeadmin password, kubeconfig (file upload or time-limited link), EOD/weekend hibernate policy. Watch via Deployment loop or short-lived Job/Informer. Needs Slack scopes for files + DMs. |
| P0-2 | **Destroy / deprovision** | [#9](https://github.com/yashoza19/opdev-cluster-bot/issues/9) | `in progress` | `/opdev-cluster-bot destroy <name>` with double confirm; delete CD (Hive cleanup) + ManagedCluster + namespace; audit who destroyed. |
| P0-3 | **Ownership & ACL** | [#10](https://github.com/yashoza19/opdev-cluster-bot/issues/10) | `todo` | Only owner (or admins via `ADMIN_SLACK_GROUP_IDS`) can hibernate/resume/destroy/keep-weekend; admins can act on any bot-managed cluster. |
| P0-4 | **Install progress / failure DM** | [#11](https://github.com/yashoza19/opdev-cluster-bot/issues/11) | `todo` | Slack updates on provisioning → installing → failed/installed; surface Hive condition messages on failure. |
| P0-5 | **Production runbook** | [#12](https://github.com/yashoza19/opdev-cluster-bot/issues/12) | `todo` | Expand smoke checklist into on-call: rotate secrets, stuck install, Quay outage, Socket Mode disconnect, AWS quota. |
| P0-6 | **Image tag discipline** | [#13](https://github.com/yashoza19/opdev-cluster-bot/issues/13) | `todo` | Stop relying only on `:latest` in prod; pin digest or semver tags; document promote path. |

### P1 — strong production hygiene

| ID | Feature | Issue | Status | Notes |
|----|---------|-------|--------|-------|
| P1-1 | **TTL / auto-destroy** | [#14](https://github.com/yashoza19/opdev-cluster-bot/issues/14) | `todo` | Annotation `opdev.io/expires-at`; CronJob warns then destroys stale clusters. |
| P1-2 | **Quota per user / team** | [#15](https://github.com/yashoza19/opdev-cluster-bot/issues/15) | `todo` | Max clusters per Slack user; optional total AWS spend proxy (count × size). |
| P1-3 | **Channel audit trail** | [#16](https://github.com/yashoza19/opdev-cluster-bot/issues/16) | `todo` | Optional ops channel: spin/hibernate/destroy events (no secrets). |
| P1-4 | **Multinode + instance-type allowlists** | [#17](https://github.com/yashoza19/opdev-cluster-bot/issues/17) | `todo` | ConfigMap allowlist; hard-block undersized SNO if desired. |
| P1-5 | **Re-send credentials** | [#18](https://github.com/yashoza19/opdev-cluster-bot/issues/18) | `todo` | `/opdev-cluster-bot creds <name>` re-DMs kubeconfig/password to owner. |
| P1-6 | **Metrics / health** | [#19](https://github.com/yashoza19/opdev-cluster-bot/issues/19) | `todo` | Prometheus metrics or at least Slack “bot heartbeat”; alert on CrashLoop. |
| P1-7 | **Integration tests on hub** | [#20](https://github.com/yashoza19/opdev-cluster-bot/issues/20) | `todo` | Scripted smoke against disposable cluster (or dry-run + power on fixture). |

### P2 — nice-to-have

| ID | Feature | Issue | Status | Notes |
|----|---------|-------|--------|-------|
| P2-1 | Cost estimate in spin confirm | [#21](https://github.com/yashoza19/opdev-cluster-bot/issues/21) | `nice-to-have` | Rough AWS rate table by instance type × topology. |
| P2-2 | Azure / GCP backends | — | `wont-do (MVP)` | Design allows later; not for v1. |
| P2-3 | ClusterPool / claim | — | `wont-do (MVP)` | |
| P2-4 | Multi-replica HA / Events API | — | `wont-do (MVP)` | Socket Mode stays single replica. |
| P2-5 | Custom install-config overrides | [#22](https://github.com/yashoza19/opdev-cluster-bot/issues/22) | `nice-to-have` | Extra CIDR, zones, machine CIDR via flags. |
| P2-6 | Transfer ownership | [#23](https://github.com/yashoza19/opdev-cluster-bot/issues/23) | `nice-to-have` | `/transfer <name> @user`. |
| P2-7 | Hibernation schedule overrides | [#24](https://github.com/yashoza19/opdev-cluster-bot/issues/24) | `nice-to-have` | Per-cluster EOD opt-out weekdays. |

### Already shipped (track as done)

| Feature | Status |
|---------|--------|
| Socket Mode slash commands + Block Kit confirms | `done` |
| Inventory list/status (bot-managed) | `done` |
| Hibernate / resume via `powerState` | `done` |
| Spin AWS Hive IPI (SNO / multinode) | `done` (validate E2E) |
| Shared creds copy + generated install-config | `done` |
| EOD remind + weekend hibernate + daily 08:00 ET resume CronJobs | `done` (validate on hub) |
| Weekend opt-out (`keep-weekend`) | `done` |
| Deploy manifests + docs + unit tests | `done` |

---

## P0-1 design sketch (credentials DM)

**Trigger:** poll or watch `ClusterDeployment` for bot-managed clusters where `status.installed` (or equivalent condition) flips true and annotation `opdev.io/creds-notified!=true`.

**Payload (DM to `ANNOTATION_OWNER_SLACK_ID`):**

1. Cluster name, API/console URLs (from CD status / Hive)
2. kubeadmin password from Hive admin-password Secret
3. kubeconfig as Slack file upload (or truncated warning + “use `/creds`”)
4. Policy blurb: *EOD hibernate reminders Mon–Fri; auto-hibernate weekends unless `keep-weekend`; Monday resume*

**Security:**

- Never post credentials to a public channel
- Mark notified via annotation to avoid re-spam
- Optional short TTL: delete uploaded file metadata reminder; prefer re-fetch via `/creds`
- Slack app needs `im:write`, `files:write`, and users already able to DM the bot

**Implementation options:**

1. Background loop in the Deployment (simplest with Socket Mode)
2. Separate CronJob every 1–2 minutes (keeps bot process thin)
3. Kubernetes Informer side-car (more code, lower latency)

Prefer (1) or (2) for first production cut.

---

## Suggested next implementation order

1. Finish validation A–C on the current hub
2. Implement **P0-1** (ready DM + creds)
3. Implement **P0-2** destroy
4. Implement **P0-3** ownership ACL
5. Pin image tags + runbook (**P0-5**, **P0-6**)
6. Then P1 items as traffic grows

---

## Related docs

- [Design](design.md)
- [Hub smoke checklist](hub-smoke-checklist.md)
- [Slack app setup](slack-app-setup.md)
- [README](../README.md)
