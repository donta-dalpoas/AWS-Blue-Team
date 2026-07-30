// @agent: SOC Agent
// @description: Automated Security Operations Center triage agent - classifies and routes security findings
//
// Permissions for the SOC Agent:
// - Can read security findings from all sources
// - Can write triage decisions and classifications
// - Can invoke enrichment tools
// - Cannot perform remediation actions directly
// - Cannot modify IAM or security configurations

// @allows: ReadFinding, ClassifyFinding, EnrichFinding, RouteFinding, QueryOpenSearch, PostTeams
// @denies: RemediateResource, ModifyIAM, ModifySecurityGroup, DeleteResource, ModifyBucketPolicy

permit (
    principal == Agent::"soc-agent",
    action in [
        Action::"ReadFinding",
        Action::"ClassifyFinding",
        Action::"EnrichFinding",
        Action::"RouteFinding",
        Action::"QueryOpenSearch",
        Action::"PostTeams",
        Action::"CreateIncident",
        Action::"UpdateIncident"
    ],
    resource in SecurityFindings::"all"
);

forbid (
    principal == Agent::"soc-agent",
    action in [
        Action::"RemediateResource",
        Action::"ModifyIAM",
        Action::"ModifySecurityGroup",
        Action::"DeleteResource",
        Action::"ModifyBucketPolicy",
        Action::"StopInstance",
        Action::"RevokeCredentials"
    ],
    resource in AWSResources::"all"
);
