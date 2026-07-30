// @agent: Incident Responder
// @description: Automated incident response agent - performs containment and remediation with approval gates
//
// Permissions for the Incident Responder:
// - Can read findings and incidents
// - Can perform containment actions (isolate, revoke, block)
// - Can remediate specific resource types
// - Cannot delete resources permanently
// - Cannot modify IAM policies (only revoke sessions/keys)
// - P1/P2 actions require human approval via Microsoft Teams

// @allows: ReadFinding, IsolateResource, RevokeCredentials, BlockIP, QuarantineInstance, RevertConfig
// @denies: DeleteResource, ModifyIAMPolicy, CreateUser, ModifyOrganization, DisableCloudTrail

permit (
    principal == Agent::"incident-responder",
    action in [
        Action::"ReadFinding",
        Action::"ReadIncident",
        Action::"IsolateResource",
        Action::"RevokeCredentials",
        Action::"BlockIP",
        Action::"QuarantineInstance",
        Action::"RevertConfig",
        Action::"RevertBucketPolicy",
        Action::"DisableAccessKey",
        Action::"QueryOpenSearch",
        Action::"PostTeams",
        Action::"RequestApproval"
    ],
    resource in AWSResources::"managed"
);

forbid (
    principal == Agent::"incident-responder",
    action in [
        Action::"DeleteResource",
        Action::"ModifyIAMPolicy",
        Action::"CreateUser",
        Action::"ModifyOrganization",
        Action::"DisableCloudTrail",
        Action::"DisableGuardDuty",
        Action::"ModifyKMSKey",
        Action::"DeleteS3Bucket"
    ],
    resource in AWSResources::"all"
);
