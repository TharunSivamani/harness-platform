# Terraform — Infra Skeleton (v0.3 stub)

This is an empty skeleton so later PRs do not restructure the repo. No resources are provisioned yet.

## Layout

```
infra/terraform/
├── main.tf            # root module — provider + placeholder
├── variables.tf       # inputs (env, region, instance_type, etc.)
├── outputs.tf         # outputs (api_url, etc.)
├── envs/
│   ├── dev/           # dev tfvars + backend stub
│   └── prod/          # prod tfvars + backend stub
└── modules/
    └── forgeai/       # future: vpc, compute, docker, etc.
```

## Usage (future)

```bash
cd infra/terraform
terraform init
terraform plan -var-file=envs/dev/terraform.tfvars
terraform apply -var-file=envs/dev/terraform.tfvars
```

Until IaC is implemented (planned ~v0.7), these files are stubs and CI does not run `terraform`.

## Conventions

- `envs/<env>/terraform.tfvars` holds per-env values — never commit secrets; use `*.tfvars` + env vars.
- Backend (S3/GCS) will be configured in `envs/<env>/backend.tf` when needed.
- Add modules under `modules/<name>/` with `main.tf`, `variables.tf`, `outputs.tf`, `README.md`.
