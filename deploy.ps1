#Requires -Version 5.1
<#
.SYNOPSIS
    Terraform wrapper for AWS AI Blue Team

.DESCRIPTION
    Manages Terraform operations: bootstrap, init, validate, fmt, plan, apply, destroy

.EXAMPLE
    .\deploy.ps1 bootstrap
    .\deploy.ps1 plan
    .\deploy.ps1 apply
    .\deploy.ps1 -Environment prod plan
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("bootstrap", "init", "validate", "fmt", "plan", "apply", "destroy", "help")]
    [string]$Command = "help",

    [Alias("e")]
    [ValidateSet("dev", "prod")]
    [string]$Environment = "dev",

    [Alias("r")]
    [string]$Region = "us-east-1"
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
$ProjectName = "aws-ai-blue-team"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TfDir = Join-Path $ScriptDir "terraform"
$BootstrapDir = Join-Path $TfDir "bootstrap"
$EnvDir = Join-Path $TfDir "environments" $Environment
$PlanFile = Join-Path $TfDir "$Environment.tfplan"
$BackendConfig = Join-Path $EnvDir "backend.hcl"
$TfVarsFile = Join-Path $EnvDir "terraform.tfvars"

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------
function Write-Banner {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║       AWS AI Blue Team - Deploy Tool        ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step  { param([string]$Msg) Write-Host "[STEP] " -ForegroundColor Cyan -NoNewline; Write-Host $Msg }
function Write-Info  { param([string]$Msg) Write-Host "[INFO] " -ForegroundColor Green -NoNewline; Write-Host $Msg }
function Write-Warn  { param([string]$Msg) Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline; Write-Host $Msg }
function Write-Err   { param([string]$Msg) Write-Host "[ERROR] " -ForegroundColor Red -NoNewline; Write-Host $Msg }

function Show-Help {
    Write-Banner
    Write-Host "Usage: .\deploy.ps1 [-Environment dev|prod] [-Region us-east-1] <Command>"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  bootstrap   One-time: create state backend + CI/CD roles (local state)"
    Write-Host "  init        Initialize Terraform with remote backend"
    Write-Host "  validate    Run fmt check, validate, and tflint"
    Write-Host "  fmt         Auto-format all .tf files"
    Write-Host "  plan        Generate and save an execution plan"
    Write-Host "  apply       Apply the saved plan"
    Write-Host "  destroy     Destroy all managed infrastructure"
    Write-Host "  help        Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\deploy.ps1 bootstrap                    # First-time setup"
    Write-Host "  .\deploy.ps1 init                         # Initialize for dev"
    Write-Host "  .\deploy.ps1 plan                         # Plan dev changes"
    Write-Host "  .\deploy.ps1 apply                        # Apply dev changes"
    Write-Host "  .\deploy.ps1 -Environment prod plan       # Plan prod changes"
    Write-Host "  .\deploy.ps1 -Environment prod apply      # Apply prod changes"
    Write-Host ""
}

function Test-Prerequisites {
    # Check Terraform
    if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
        Write-Err "Terraform is not installed. Install from https://developer.hashicorp.com/terraform/install"
        exit 1
    }
    $tfVersion = (terraform version -json 2>$null | ConvertFrom-Json).terraform_version
    if (-not $tfVersion) { $tfVersion = "unknown" }
    Write-Info "Terraform v$tfVersion"

    # Check AWS credentials
    $hasProfile = $env:AWS_PROFILE
    $hasAccessKey = $env:AWS_ACCESS_KEY_ID
    $hasRoleArn = $env:AWS_ROLE_ARN
    if (-not $hasProfile -and -not $hasAccessKey -and -not $hasRoleArn) {
        Write-Err "No AWS credentials found. Set AWS_PROFILE, AWS_ACCESS_KEY_ID, or AWS_ROLE_ARN."
        exit 1
    }
    Write-Info "AWS credentials configured"
}

function Invoke-Bootstrap {
    Write-Step "Running bootstrap (one-time state backend setup)..."

    if (-not (Test-Path $BootstrapDir)) {
        Write-Err "Bootstrap directory not found: $BootstrapDir"
        exit 1
    }

    Push-Location $BootstrapDir
    try {
        Write-Info "Initializing bootstrap module (local state)..."
        terraform init
        if ($LASTEXITCODE -ne 0) { Write-Err "Init failed"; exit 1 }

        Write-Info "Planning bootstrap resources..."
        terraform plan -out="bootstrap.tfplan"
        if ($LASTEXITCODE -ne 0) { Write-Err "Plan failed"; exit 1 }

        Write-Host ""
        Write-Warn "This will create the Terraform state bucket, lock table, and CI/CD roles."
        $confirm = Read-Host "Proceed with apply? (yes/no)"
        if ($confirm -ne "yes") {
            Write-Warn "Aborted."
            exit 0
        }

        Write-Info "Applying bootstrap..."
        terraform apply "bootstrap.tfplan"
        if ($LASTEXITCODE -ne 0) { Write-Err "Apply failed"; exit 1 }

        Write-Host ""
        Write-Info "Bootstrap complete. Outputs:"
        terraform output

        Write-Host ""
        Write-Step "Next steps:"
        Write-Host "  1. The backend.hcl is already configured with your account ID."
        Write-Host "  2. Run: .\deploy.ps1 init"
        Write-Host "  3. Configure GitHub Secret AWS_ROLE_ARN with the apply_role_arn output."
        Write-Host ""
        Write-Info "After init, migrate bootstrap state to remote:"
        Write-Host "     cd terraform\bootstrap"
        Write-Host "     terraform init -migrate-state ``"
        Write-Host "       -backend-config=`"bucket=954272306896-us-east-1-terraform-state`" ``"
        Write-Host "       -backend-config=`"key=bootstrap/terraform.tfstate`" ``"
        Write-Host "       -backend-config=`"region=$Region`" ``"
        Write-Host "       -backend-config=`"dynamodb_table=terraform-state-lock`" ``"
        Write-Host "       -backend-config=`"encrypt=true`""
    }
    finally {
        Pop-Location
    }
}

function Invoke-Init {
    Write-Step "Initializing Terraform for environment: $Environment..."

    if (-not (Test-Path $BackendConfig)) {
        Write-Err "Backend config not found: $BackendConfig"
        Write-Err "Run '.\deploy.ps1 bootstrap' first."
        exit 1
    }

    Push-Location $TfDir
    try {
        terraform init -backend-config="$BackendConfig" -reconfigure
        if ($LASTEXITCODE -ne 0) { Write-Err "Init failed"; exit 1 }
        Write-Info "Initialization complete for $Environment."
    }
    finally {
        Pop-Location
    }
}

function Invoke-Validate {
    Write-Step "Validating Terraform configuration..."
    Push-Location $TfDir
    try {
        Write-Info "Checking formatting..."
        terraform fmt -check -recursive
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Formatting issues found. Run '.\deploy.ps1 fmt' to fix."
            exit 1
        }
        Write-Info "Formatting OK"

        Write-Info "Validating syntax..."
        terraform validate
        if ($LASTEXITCODE -ne 0) { Write-Err "Validation failed"; exit 1 }
        Write-Info "Validation passed"

        if (Get-Command tflint -ErrorAction SilentlyContinue) {
            Write-Info "Running tflint..."
            tflint --recursive
            if ($LASTEXITCODE -ne 0) { Write-Err "tflint found issues"; exit 1 }
            Write-Info "tflint passed"
        }
        else {
            Write-Warn "tflint not installed, skipping."
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-Fmt {
    Write-Step "Formatting Terraform files..."
    Push-Location $TfDir
    try {
        terraform fmt -recursive
        Write-Info "Formatting complete."
    }
    finally {
        Pop-Location
    }
}

function Invoke-Plan {
    Write-Step "Planning infrastructure changes for: $Environment..."

    if (-not (Test-Path $TfVarsFile)) {
        Write-Err "Tfvars file not found: $TfVarsFile"
        exit 1
    }

    Push-Location $TfDir
    try {
        terraform plan `
            -var-file="$TfVarsFile" `
            -var="aws_region=$Region" `
            -out="$PlanFile"
        if ($LASTEXITCODE -ne 0) { Write-Err "Plan failed"; exit 1 }

        Write-Host ""
        Write-Info "Plan saved to: $PlanFile"
        Write-Info "Review the plan above, then run: .\deploy.ps1 -Environment $Environment apply"
    }
    finally {
        Pop-Location
    }
}

function Invoke-Apply {
    Write-Step "Applying plan for: $Environment..."

    if (-not (Test-Path $PlanFile)) {
        Write-Err "No plan file found at: $PlanFile"
        Write-Err "Run '.\deploy.ps1 -Environment $Environment plan' first."
        exit 1
    }

    Push-Location $TfDir
    try {
        terraform apply "$PlanFile"
        if ($LASTEXITCODE -ne 0) { Write-Err "Apply failed"; exit 1 }

        Remove-Item -LiteralPath $PlanFile -Force -ErrorAction SilentlyContinue
        Write-Info "Apply complete. Plan file cleaned up."
    }
    finally {
        Pop-Location
    }
}

function Invoke-Destroy {
    Write-Step "Destroying infrastructure for: $Environment..."
    Write-Warn "This will DESTROY all resources in the $Environment environment!"

    $confirm = Read-Host "Type 'destroy $Environment' to confirm"
    if ($confirm -ne "destroy $Environment") {
        Write-Warn "Aborted."
        exit 0
    }

    Push-Location $TfDir
    try {
        terraform destroy `
            -var-file="$TfVarsFile" `
            -var="aws_region=$Region"
        if ($LASTEXITCODE -ne 0) { Write-Err "Destroy failed"; exit 1 }
        Write-Info "Destroy complete."
    }
    finally {
        Pop-Location
    }
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
Write-Banner
Test-Prerequisites

switch ($Command) {
    "bootstrap" { Invoke-Bootstrap }
    "init"      { Invoke-Init }
    "validate"  { Invoke-Validate }
    "fmt"       { Invoke-Fmt }
    "plan"      { Invoke-Plan }
    "apply"     { Invoke-Apply }
    "destroy"   { Invoke-Destroy }
    "help"      { Show-Help }
}
