# =============================================================================
# AWS AI Blue Team - Root Module
# =============================================================================
# This is the main composition layer that wires all child modules together.
# Each module corresponds to a sub-issue in Epic 1.
#
# Apply order is handled by Terraform's dependency graph via input/output refs.
# =============================================================================

data "aws_caller_identity" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  name_prefix = "${var.project_name}-${var.environment}"
}

# =============================================================================
# Sub-Issue #1: Logging + Security Services
# =============================================================================

# KMS key shared across logging and storage
module "kms" {
  source      = "./modules/kms"
  name_prefix = local.name_prefix
  account_id  = local.account_id
  aws_region  = var.aws_region
}

# Centralized S3 bucket for all security logs
module "storage" {
  source                 = "./modules/storage"
  name_prefix            = local.name_prefix
  account_id             = local.account_id
  aws_region             = var.aws_region
  kms_key_arn            = module.kms.key_arn
  lifecycle_ia_days      = var.lifecycle_ia_days
  lifecycle_glacier_days = var.lifecycle_glacier_days
  lifecycle_expire_days  = var.lifecycle_expire_days
}

# VPC for the platform
module "networking" {
  source      = "./modules/networking"
  count       = var.create_vpc ? 1 : 0
  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  aws_region  = var.aws_region
}

# CloudTrail
module "cloudtrail" {
  source         = "./modules/logging/cloudtrail"
  name_prefix    = local.name_prefix
  s3_bucket_name = module.storage.bucket_name
  kms_key_arn    = module.kms.key_arn
}

# VPC Flow Logs
module "vpc_flow_logs" {
  source         = "./modules/logging/vpc-flow-logs"
  name_prefix    = local.name_prefix
  s3_bucket_arn  = module.storage.bucket_arn
  s3_bucket_name = module.storage.bucket_name
  vpc_ids        = var.create_vpc ? [module.networking[0].vpc_id] : []
}

# GuardDuty
module "guardduty" {
  source         = "./modules/logging/guardduty"
  name_prefix    = local.name_prefix
  s3_bucket_name = module.storage.bucket_name
  s3_bucket_arn  = module.storage.bucket_arn
  kms_key_arn    = module.kms.key_arn
}

# SecurityHub
module "securityhub" {
  source      = "./modules/logging/securityhub"
  name_prefix = local.name_prefix
}

# SNS Topic for security findings + EventBridge rules
module "sns" {
  source      = "./modules/sns"
  name_prefix = local.name_prefix
  kms_key_arn = module.kms.key_arn
}

# Athena query layer
module "athena" {
  source         = "./modules/athena"
  name_prefix    = local.name_prefix
  s3_bucket_name = module.storage.bucket_name
  account_id     = local.account_id
  active_regions = var.active_regions
}

# =============================================================================
# Sub-Issue #3: Baseline Generator
# =============================================================================

module "baseline_generator" {
  source              = "./modules/baseline-generator"
  name_prefix         = local.name_prefix
  s3_bucket_name      = module.storage.bucket_name
  s3_bucket_arn       = module.storage.bucket_arn
  kms_key_arn         = module.kms.key_arn
  sns_alert_topic_arn = module.sns.alert_topic_arn
  active_regions      = var.active_regions
  account_id          = local.account_id
}

# =============================================================================
# Sub-Issue #4: OpenSearch + Ingestion Pipeline
# =============================================================================

module "opensearch" {
  source                = "./modules/opensearch"
  name_prefix           = local.name_prefix
  instance_type         = var.opensearch_instance_type
  instance_count        = var.opensearch_instance_count
  ebs_volume_size       = var.opensearch_ebs_volume_size
  vpc_subnet_ids        = var.create_vpc ? module.networking[0].private_subnet_ids : []
  vpc_security_group_id = var.create_vpc ? module.networking[0].opensearch_sg_id : ""
  kms_key_arn           = module.kms.key_arn
}

module "ingestion" {
  source                = "./modules/ingestion"
  name_prefix           = local.name_prefix
  s3_bucket_name        = module.storage.bucket_name
  s3_bucket_arn         = module.storage.bucket_arn
  opensearch_endpoint   = module.opensearch.endpoint
  opensearch_domain_arn = module.opensearch.domain_arn
  kms_key_arn           = module.kms.key_arn
  sns_alert_topic_arn   = module.sns.alert_topic_arn
  lambda_concurrency    = var.ingestion_lambda_concurrency
  batch_size            = var.ingestion_batch_size
}

# =============================================================================
# Sub-Issue #5: AgentCore Platform
# =============================================================================

module "agentcore_identity" {
  source         = "./modules/agentcore-identity"
  name_prefix    = local.name_prefix
  s3_bucket_arn  = module.storage.bucket_arn
  opensearch_arn = module.opensearch.domain_arn
  sns_topic_arn  = module.sns.findings_topic_arn
  kms_key_arn    = module.kms.key_arn
  account_id     = local.account_id
}

module "agentcore_policy" {
  source      = "./modules/agentcore-policy"
  name_prefix = local.name_prefix
  account_id  = local.account_id
  aws_region  = var.aws_region
}

module "agentcore_gateway" {
  source               = "./modules/agentcore-gateway"
  name_prefix          = local.name_prefix
  policy_evaluator_arn = module.agentcore_policy.evaluator_lambda_arn
  opensearch_endpoint  = module.opensearch.endpoint
}

module "agentcore_observability" {
  source                = "./modules/agentcore-observability"
  name_prefix           = local.name_prefix
  sns_alert_topic_arn   = module.sns.alert_topic_arn
  gateway_lambda_name   = module.agentcore_gateway.lambda_name
  evaluator_lambda_name = module.agentcore_policy.evaluator_lambda_name
}

# =============================================================================
# Epic 2: SOC Analyst Agent
# =============================================================================

module "agent_soc_analyst" {
  source              = "./modules/agents/soc-analyst"
  name_prefix         = local.name_prefix
  sns_topic_arn       = module.sns.findings_topic_arn
  agent_role_arn      = module.agentcore_identity.agent_role_arns["soc-analyst"]
  opensearch_endpoint = module.opensearch.endpoint
  gateway_url         = module.agentcore_gateway.gateway_url
  s3_bucket_name      = module.storage.bucket_name
  kms_key_arn         = module.kms.key_arn
  sns_alert_topic_arn = module.sns.alert_topic_arn
}

# =============================================================================
# Epic 3: Incident Responder Agent
# =============================================================================

module "agent_incident_responder" {
  source                    = "./modules/agents/incident-responder"
  name_prefix               = local.name_prefix
  agent_role_arn            = module.agentcore_identity.agent_role_arns["incident-responder"]
  s3_bucket_name            = module.storage.bucket_name
  opensearch_endpoint       = module.opensearch.endpoint
  cedar_evaluator_arn       = module.agentcore_policy.evaluator_lambda_arn
  kms_key_arn               = module.kms.key_arn
  sns_alert_topic_arn       = module.sns.alert_topic_arn
  api_gateway_id            = module.agentcore_gateway.api_id
  api_gateway_execution_arn = module.agentcore_gateway.execution_arn
}

# =============================================================================
# Epic 4: Proactive Agents
# =============================================================================

module "agent_compliance_auditor" {
  source              = "./modules/agents/compliance-auditor"
  name_prefix         = local.name_prefix
  agent_role_arn      = module.agentcore_identity.agent_role_arns["compliance-auditor"]
  s3_bucket_name      = module.storage.bucket_name
  opensearch_endpoint = module.opensearch.endpoint
}

module "agent_threat_hunter" {
  source              = "./modules/agents/threat-hunter"
  name_prefix         = local.name_prefix
  agent_role_arn      = module.agentcore_identity.agent_role_arns["threat-hunter"]
  s3_bucket_name      = module.storage.bucket_name
  opensearch_endpoint = module.opensearch.endpoint
}

module "agent_red_team" {
  source              = "./modules/agents/red-team"
  name_prefix         = local.name_prefix
  agent_role_arn      = module.agentcore_identity.agent_role_arns["red-team"]
  s3_bucket_name      = module.storage.bucket_name
  opensearch_endpoint = module.opensearch.endpoint
}
