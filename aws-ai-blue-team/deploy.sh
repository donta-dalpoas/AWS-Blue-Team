#!/usr/bin/env bash
#
# deploy.sh - Terraform wrapper for AWS AI Blue Team
#
# Usage:
#   ./deploy.sh [OPTIONS] COMMAND
#
# Commands:
#   bootstrap   One-time setup: creates state bucket, lock table, OIDC, CI/CD roles
#   init        Initialize Terraform with remote backend
#   validate    Run fmt check, validate, and tflint
#   fmt         Auto-format all .tf files
#   plan        Generate and save an execution plan
#   apply       Apply the saved plan
#   destroy     Destroy all managed infrastructure
#   help        Show this help message
#
# Options:
#   -e ENV      Environment (dev|prod). Default: dev
#   -r REGION   AWS region. Default: us-east-1
#   -h          Show help
#
set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_NAME="aws-ai-blue-team"
DEFAULT_ENV="dev"
DEFAULT_REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="${SCRIPT_DIR}/terraform"
BOOTSTRAP_DIR="${TF_DIR}/bootstrap"

# -----------------------------------------------------------------------------
# Colors
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------
banner() {
  echo -e "${BLUE}"
  echo "╔══════════════════════════════════════════════╗"
  echo "║       AWS AI Blue Team - Deploy Tool        ║"
  echo "╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
}

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "${BLUE}[STEP]${NC} $1"; }

show_help() {
  banner
  echo "Usage: ./deploy.sh [OPTIONS] COMMAND"
  echo ""
  echo "Commands:"
  echo "  bootstrap   One-time: create state backend + CI/CD roles (runs with local state)"
  echo "  init        Initialize Terraform with remote backend"
  echo "  validate    Run fmt check, validate, and tflint"
  echo "  fmt         Auto-format all .tf files"
  echo "  plan        Generate and save an execution plan"
  echo "  apply       Apply the saved plan"
  echo "  destroy     Destroy all managed infrastructure"
  echo "  help        Show this help message"
  echo ""
  echo "Options:"
  echo "  -e ENV      Environment: dev or prod (default: dev)"
  echo "  -r REGION   AWS region (default: us-east-1)"
  echo "  -h          Show help"
  echo ""
  echo "Examples:"
  echo "  ./deploy.sh bootstrap                  # First-time setup"
  echo "  ./deploy.sh init                       # Initialize for dev"
  echo "  ./deploy.sh plan                       # Plan dev changes"
  echo "  ./deploy.sh apply                      # Apply dev changes"
  echo "  ./deploy.sh -e prod plan               # Plan prod changes"
  echo "  ./deploy.sh -e prod apply              # Apply prod changes"
  echo "  ./deploy.sh validate                   # Check formatting + validate"
  echo ""
}

check_prerequisites() {
  # Check Terraform is installed
  if ! command -v terraform &> /dev/null; then
    log_error "Terraform is not installed. Install from https://developer.hashicorp.com/terraform/install"
    exit 1
  fi
  log_info "Terraform $(terraform version -json 2>/dev/null | grep -o '"terraform_version":"[^"]*"' | cut -d'"' -f4 || terraform version | head -1)"

  # Check AWS credentials
  if [[ -z "${AWS_PROFILE:-}" ]] && [[ -z "${AWS_ACCESS_KEY_ID:-}" ]] && [[ -z "${AWS_ROLE_ARN:-}" ]]; then
    log_error "No AWS credentials found. Set AWS_PROFILE, AWS_ACCESS_KEY_ID, or AWS_ROLE_ARN."
    exit 1
  fi
  log_info "AWS credentials configured"
}

# -----------------------------------------------------------------------------
# Parse Options
# -----------------------------------------------------------------------------
ENV="${DEFAULT_ENV}"
REGION="${DEFAULT_REGION}"

while getopts "e:r:h" opt; do
  case ${opt} in
    e) ENV="${OPTARG}" ;;
    r) REGION="${OPTARG}" ;;
    h) show_help; exit 0 ;;
    *) show_help; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

COMMAND="${1:-help}"
ENV_DIR="${TF_DIR}/environments/${ENV}"
PLAN_FILE="${TF_DIR}/${ENV}.tfplan"
BACKEND_CONFIG="${ENV_DIR}/backend.hcl"
TFVARS_FILE="${ENV_DIR}/terraform.tfvars"

# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------
cmd_bootstrap() {
  log_step "Running bootstrap (one-time state backend setup)..."

  if [[ ! -d "${BOOTSTRAP_DIR}" ]]; then
    log_error "Bootstrap directory not found: ${BOOTSTRAP_DIR}"
    exit 1
  fi

  cd "${BOOTSTRAP_DIR}"

  log_info "Initializing bootstrap module (local state)..."
  terraform init

  log_info "Planning bootstrap resources..."
  terraform plan -out=bootstrap.tfplan

  echo ""
  log_warn "This will create the Terraform state bucket, lock table, and CI/CD roles."
  read -p "Proceed with apply? (yes/no): " confirm
  if [[ "${confirm}" != "yes" ]]; then
    log_warn "Aborted."
    exit 0
  fi

  log_info "Applying bootstrap..."
  terraform apply bootstrap.tfplan

  echo ""
  log_info "Bootstrap complete. Outputs:"
  terraform output

  echo ""
  log_step "Next steps:"
  echo "  1. Copy the state_bucket_name and lock_table_name outputs into"
  echo "     terraform/environments/${ENV}/backend.hcl"
  echo "  2. Run: ./deploy.sh init"
  echo "  3. Configure GitHub Secret AWS_ROLE_ARN with the apply_role_arn output"
  echo ""
  log_info "After init, migrate bootstrap state to remote:"
  echo "     cd terraform/bootstrap"
  echo "     terraform init -migrate-state \\"
  echo "       -backend-config=\"bucket=<state_bucket_name>\" \\"
  echo "       -backend-config=\"key=bootstrap/terraform.tfstate\" \\"
  echo "       -backend-config=\"region=${REGION}\" \\"
  echo "       -backend-config=\"dynamodb_table=terraform-state-lock\" \\"
  echo "       -backend-config=\"encrypt=true\""
}

cmd_init() {
  log_step "Initializing Terraform for environment: ${ENV}..."

  if [[ ! -f "${BACKEND_CONFIG}" ]]; then
    log_error "Backend config not found: ${BACKEND_CONFIG}"
    log_error "Run './deploy.sh bootstrap' first, then create the backend config."
    exit 1
  fi

  cd "${TF_DIR}"
  terraform init -backend-config="${BACKEND_CONFIG}" -reconfigure
  log_info "Initialization complete for ${ENV}."
}

cmd_validate() {
  log_step "Validating Terraform configuration..."
  cd "${TF_DIR}"

  log_info "Checking formatting..."
  if terraform fmt -check -recursive; then
    log_info "Formatting OK"
  else
    log_error "Formatting issues found. Run './deploy.sh fmt' to fix."
    exit 1
  fi

  log_info "Validating syntax..."
  terraform validate
  log_info "Validation passed"

  if command -v tflint &> /dev/null; then
    log_info "Running tflint..."
    tflint --recursive
    log_info "tflint passed"
  else
    log_warn "tflint not installed, skipping. Install from https://github.com/terraform-linters/tflint"
  fi
}

cmd_fmt() {
  log_step "Formatting Terraform files..."
  cd "${TF_DIR}"
  terraform fmt -recursive
  log_info "Formatting complete."
}

cmd_plan() {
  log_step "Planning infrastructure changes for: ${ENV}..."

  if [[ ! -f "${TFVARS_FILE}" ]]; then
    log_error "Tfvars file not found: ${TFVARS_FILE}"
    exit 1
  fi

  cd "${TF_DIR}"
  terraform plan \
    -var-file="${TFVARS_FILE}" \
    -var="aws_region=${REGION}" \
    -out="${PLAN_FILE}"

  echo ""
  log_info "Plan saved to: ${PLAN_FILE}"
  log_info "Review the plan above, then run: ./deploy.sh -e ${ENV} apply"
}

cmd_apply() {
  log_step "Applying plan for: ${ENV}..."

  if [[ ! -f "${PLAN_FILE}" ]]; then
    log_error "No plan file found at: ${PLAN_FILE}"
    log_error "Run './deploy.sh -e ${ENV} plan' first."
    exit 1
  fi

  cd "${TF_DIR}"
  terraform apply "${PLAN_FILE}"

  # Clean up plan file after successful apply
  rm -f "${PLAN_FILE}"
  log_info "Apply complete. Plan file cleaned up."
}

cmd_destroy() {
  log_step "Destroying infrastructure for: ${ENV}..."
  log_warn "This will DESTROY all resources in the ${ENV} environment!"

  read -p "Type 'destroy ${ENV}' to confirm: " confirm
  if [[ "${confirm}" != "destroy ${ENV}" ]]; then
    log_warn "Aborted."
    exit 0
  fi

  cd "${TF_DIR}"
  terraform destroy \
    -var-file="${TFVARS_FILE}" \
    -var="aws_region=${REGION}"

  log_info "Destroy complete."
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
banner
check_prerequisites

case "${COMMAND}" in
  bootstrap) cmd_bootstrap ;;
  init)      cmd_init ;;
  validate)  cmd_validate ;;
  fmt)       cmd_fmt ;;
  plan)      cmd_plan ;;
  apply)     cmd_apply ;;
  destroy)   cmd_destroy ;;
  help)      show_help ;;
  *)
    log_error "Unknown command: ${COMMAND}"
    show_help
    exit 1
    ;;
esac
