// @agent: Compliance Auditor
// @description: Automated compliance scanning agent - checks resource configurations against security baselines
//
// Permissions for the Compliance Auditor:
// - Can read all resource configurations
// - Can query compliance state
// - Can generate compliance reports
// - Cannot modify any resources
// - Read-only access to all AWS resource metadata

// @allows: ReadConfig, QueryCompliance, GenerateReport, ReadBaseline, QueryOpenSearch
// @denies: ModifyResource, RemediateResource, ModifyIAM, DeleteResource, WriteConfig

permit (
    principal == Agent::"compliance-auditor",
    action in [
        Action::"ReadConfig",
        Action::"QueryCompliance",
        Action::"GenerateReport",
        Action::"ReadBaseline",
        Action::"QueryOpenSearch",
        Action::"PostTeams",
        Action::"CommitReport"
    ],
    resource in AWSResources::"all"
);

forbid (
    principal == Agent::"compliance-auditor",
    action in [
        Action::"ModifyResource",
        Action::"RemediateResource",
        Action::"ModifyIAM",
        Action::"DeleteResource",
        Action::"WriteConfig",
        Action::"StopInstance",
        Action::"CreateResource"
    ],
    resource in AWSResources::"all"
);
