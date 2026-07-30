// @agent: Executive Summary Agent
// @description: Weekly executive briefing agent - generates plain-English security summaries for leadership
//
// Permissions for the Executive Summary Agent:
// - Can query OpenSearch metrics (read-only)
// - Can post to Microsoft Teams
// - Can commit reports to the repository
// - Cannot access or modify any AWS resources
// - Read-only analytics access

// @allows: QueryOpenSearch, ReadMetrics, GenerateReport, PostTeams, CommitReport
// @denies: ModifyResource, RemediateResource, ModifyIAM, DeleteResource, ReadSecrets

permit (
    principal == Agent::"executive-summary",
    action in [
        Action::"QueryOpenSearch",
        Action::"ReadMetrics",
        Action::"GenerateReport",
        Action::"PostTeams",
        Action::"CommitReport"
    ],
    resource in Analytics::"metrics"
);

forbid (
    principal == Agent::"executive-summary",
    action in [
        Action::"ModifyResource",
        Action::"RemediateResource",
        Action::"ModifyIAM",
        Action::"DeleteResource",
        Action::"ReadSecrets",
        Action::"ReadFinding",
        Action::"ModifySecurityGroup"
    ],
    resource in AWSResources::"all"
);
