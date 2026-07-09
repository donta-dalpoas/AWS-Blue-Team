# =============================================================================
# Dev Environment Variables
# =============================================================================
# Replace placeholder values with your actual configuration.

account_id  = "954272306896"
environment = "dev"
project_name = "aws-ai-blue-team"

# Regions
aws_region       = "us-east-1"
active_regions   = ["us-east-1", "us-west-2"]

# GitHub (for OIDC - already bootstrapped)
github_org  = "AWS-Blue-Team"
github_repo = "aws-ai-blue-team"

# Networking
create_vpc = true
vpc_cidr   = "10.0.0.0/16"

# OpenSearch (dev sizing)
opensearch_instance_type  = "t3.medium.search"
opensearch_instance_count = 2
opensearch_ebs_volume_size = 100

# S3 Lifecycle
lifecycle_ia_days      = 30
lifecycle_glacier_days = 90
lifecycle_expire_days  = 365

# Ingestion
ingestion_lambda_concurrency = 5
ingestion_batch_size         = 500
