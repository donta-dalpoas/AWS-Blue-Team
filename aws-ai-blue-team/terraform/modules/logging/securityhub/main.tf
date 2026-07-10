# =============================================================================
# SecurityHub Module
# =============================================================================
# Enables SecurityHub with configurable compliance standards.
# NOTE: GuardDuty must be enabled first for findings integration.
# =============================================================================

resource "aws_securityhub_account" "main" {}

# AWS Foundational Security Best Practices
resource "aws_securityhub_standards_subscription" "aws_foundational" {
  depends_on    = [aws_securityhub_account.main]
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"
}

# CIS AWS Foundations Benchmark v1.4.0
resource "aws_securityhub_standards_subscription" "cis" {
  count         = var.enable_cis_standard ? 1 : 0
  depends_on    = [aws_securityhub_account.main]
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/cis-aws-foundations-benchmark/v/1.4.0"
}

# PCI DSS v3.2.1
resource "aws_securityhub_standards_subscription" "pci" {
  count         = var.enable_pci_standard ? 1 : 0
  depends_on    = [aws_securityhub_account.main]
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/pci-dss/v/3.2.1"
}

data "aws_region" "current" {}
