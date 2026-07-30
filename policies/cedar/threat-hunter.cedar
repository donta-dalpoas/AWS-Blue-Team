// @agent: Threat Hunter
// @description: Proactive threat hunting agent - searches for undiscovered threats using hypothesis-driven queries
//
// Permissions for the Threat Hunter:
// - Can query all log sources
// - Can create new detection rules (for review)
// - Can read threat intelligence feeds
// - Cannot perform any remediation
// - Cannot modify security configurations

// @allows: QueryLogs, QueryOpenSearch, ReadThreatIntel, CreateDetectionRule, GenerateHypothesis
// @denies: RemediateResource, ModifyIAM, ModifySecurityGroup, DeleteResource, BlockIP

permit (
    principal == Agent::"threat-hunter",
    action in [
        Action::"QueryLogs",
        Action::"QueryOpenSearch",
        Action::"ReadThreatIntel",
        Action::"CreateDetectionRule",
        Action::"GenerateHypothesis",
        Action::"PostTeams",
        Action::"CommitDetection"
    ],
    resource in SecurityFindings::"all"
);

forbid (
    principal == Agent::"threat-hunter",
    action in [
        Action::"RemediateResource",
        Action::"ModifyIAM",
        Action::"ModifySecurityGroup",
        Action::"DeleteResource",
        Action::"BlockIP",
        Action::"RevokeCredentials",
        Action::"StopInstance"
    ],
    resource in AWSResources::"all"
);
