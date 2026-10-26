# ForgeAI Terraform root — v0.3 skeleton (no resources)
# Add provider + module calls here when IaC is implemented.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    # Example when you add a cloud:
    # aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  # Backend will be configured per env in envs/<env>/backend.tf
}

# Example (commented):
# module "forgeai" {
#   source = "./modules/forgeai"
#   env    = var.env
# }
