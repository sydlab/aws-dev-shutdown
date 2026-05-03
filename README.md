# aws-dev-shutdown

Scheduled **development** AWS cost control: stop (or optionally terminate) tagged EC2 instances that have been running longer than a threshold. Orchestrated by **GitHub Actions** every 12 hours, with **Slack** notifications for `#infra-aws`.

**Branches:** **`main`** holds documentation-only README. **`dev`** (this branch) has workflows, code, and Terraform. Set **`dev`** as the **repository default branch** so scheduled Actions run (`schedule` workflows use the default branch only).

> **Safety:** Defaults to **dry-run**. Only tagged resources are candidates. Use a **sandbox account** or strict tag policy; never tag production workloads with `AutoShutdown=true`.

## What it does

1. Finds **running** EC2 instances with a given tag (default `AutoShutdown=true`).
2. If instance **launch time** is older than `MAX_AGE_HOURS`, stops the instance (unless `DRY_RUN=true`).
3. Posts a summary to Slack via **Incoming Webhook**.

## Repository layout

| Path | Purpose |
|------|---------|
| `.github/workflows/shutdown.yml` | Cron (every 12h UTC) + manual `workflow_dispatch` |
| `scripts/shutdown.py` | Boto3 logic |
| `terraform/` | Optional: GitHub OIDC → IAM role (no long-lived AWS keys in GitHub) |

## Create / clone this repository

**New repo:** create `sydlab/aws-dev-shutdown` (adjust org/name), push both **`main`** and **`dev`**, then set **default branch → `dev`**.

From your clone (already on **`dev`** for workflows):

```bash
git remote add origin https://github.com/sydlab/aws-dev-shutdown.git   # replace if different
git push -u origin main
git push -u origin dev
```

After the first push, in GitHub: **Settings → General → Default branch → `dev`**.


If you use a different repo name, update `github_repo` in `terraform/variables.tf` (or `terraform.tfvars`) so the OIDC trust matches `repo:sydlab/<name>:*`.

## GitHub configuration

### Secrets (Repository → Settings → Secrets and variables → Actions)

| Secret | Required | Description |
|--------|----------|-------------|
| `AWS_ROLE_ARN` | Recommended | IAM role ARN for OIDC (see `terraform/` output `github_actions_role_arn`) |
| `SLACK_WEBHOOK_URL` | Recommended | [Incoming Webhook](https://api.slack.com/messaging/webhooks) for `#infra-aws` |

If `AWS_ROLE_ARN` is missing, the **Configure AWS (OIDC)** step fails—the workflow does not embedded an account ID; the account is whichever account trust this role.

If you are **not** using OIDC yet, you can temporarily use `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` instead of `AWS_ROLE_ARN` by editing the workflow to use the access-key variant (documented in the workflow file comments). Those keys must belong to an IAM principal in the target account with `ec2:DescribeInstances` and `ec2:StopInstances` (scoped to your tagging policy).

### Variables (optional)

Repository **Variables** (Settings → Secrets and variables → Actions → Variables tab):

| Name | Default | Description |
|------|---------|-------------|
| `AWS_REGION` | `us-east-1` | Region passed to boto3 (`scripts/shutdown.py` also respects `AWS_DEFAULT_REGION`) |
| `MAX_AGE_HOURS` | `8` | Stop instances older than this many hours |
| `TARGET_TAG_KEY` | `AutoShutdown` | Tag key to match |
| `TARGET_TAG_VALUE` | `true` | Tag value to match |
| `DRY_RUN` | `true` | Set to `false` when ready to actually stop instances |

**IAM vs variables:** Terraform attaches `ec2:StopInstances` only when `ec2:ResourceTag/<TARGET_TAG_KEY>` equals `TARGET_TAG_VALUE` using the tag values defined in **`terraform.tfvars` / `variables.tf`** at apply time. If you later change GitHub Variables `TARGET_TAG_KEY` / `TARGET_TAG_VALUE` without updating IAM (or Terraform variables and re-applying), `DescribeInstances` may still succeed but **`StopInstances` can return `AccessDenied`**. Keep them aligned.

**Important:** Keep `DRY_RUN=true` until CloudWatch/logging in the Actions run looks correct.

### Slack webhook for `#infra-aws`

1. Slack → **Apps** → **Incoming Webhooks** → Add to workspace → pick channel **#infra-aws**.
2. Copy the webhook URL into GitHub secret `SLACK_WEBHOOK_URL`.

## One-time AWS setup (OIDC, recommended)

1. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and adjust region / repo if needed.
2. From `terraform/`:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

3. Copy output `github_actions_role_arn` into GitHub secret `AWS_ROLE_ARN`.

The trust policy allows only this repo: `repo:sydlab/aws-dev-shutdown:*` (adjust `github_org` / `github_repo` in `terraform/variables.tf` if needed).

**If `aws_iam_openid_connect_provider` for `token.actions.githubusercontent.com` already exists** in the account (common when you already use GitHub OIDC), `terraform apply` will error on duplicate URL. In that case, remove the `aws_iam_openid_connect_provider` resource and `tls_certificate` data source from `terraform/main.tf`, add a `data "aws_iam_openid_connect_provider" "github_actions"` block with that URL, and reference `data.aws_iam_openid_connect_provider.github_actions.arn` in the assume-role policy instead of `aws_iam_openid_connect_provider.github_actions.arn`.

## Tag your dev instances

On EC2 (console or IaC):

- `AutoShutdown=true`
- (Optional) `Environment=dev`

Only matching **running** instances older than `MAX_AGE_HOURS` are stopped.

## Local test

Uses the same credential chain as the AWS CLI (profile, env keys, SSO, etc.); set region explicitly if your profile omits it.

```bash
export AWS_PROFILE=your-dev-profile
export AWS_REGION=us-east-1
export DRY_RUN=true
export MAX_AGE_HOURS=8
pip install -r requirements.txt
python scripts/shutdown.py
```

## Schedule

The workflow uses cron `0 */12 * * *` (every 12 hours at **00:00 and 12:00 UTC**). GitHub Actions schedules can drift slightly; for stricter timing use EventBridge + Lambda in AWS instead.

## More automation ideas (dev AWS)

- **RDS dev instances:** stop after hours; respect max stop duration per engine.
- **Schedule-based scale-to-zero:** ASG `DesiredCapacity=0` nights/weekends via EventBridge.
- **EIP / unattached EBS / old snapshots:** weekly cleanup job with tag or age filters.
- **NAT Gateway:** replace with VPC endpoints or tear down ephemeral dev VPCs entirely.
- **Cost anomaly + budget alerts:** AWS Budgets → Slack via SNS.
- **Account vending:** separate AWS account per developer; SCP deny expensive services.
- **Lambda in AWS** as backup runner if GitHub is down (optional duplicate of this script).

## License

MIT
