output "agent_role_arns" {
  description = "Map of agent name to IAM role ARN"
  value = {
    soc-analyst          = aws_iam_role.soc_analyst.arn
    incident-responder   = aws_iam_role.incident_responder.arn
    threat-hunter        = aws_iam_role.threat_hunter.arn
    compliance-auditor   = aws_iam_role.compliance_auditor.arn
    red-team             = aws_iam_role.red_team.arn
  }
}

output "permission_boundary_arn" {
  description = "ARN of the shared agent permission boundary"
  value       = aws_iam_policy.agent_boundary.arn
}
