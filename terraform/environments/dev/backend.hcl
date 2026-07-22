# Backend configuration for dev environment
# Update these values with the outputs from ./deploy.sh bootstrap
bucket         = "954272306896-us-east-1-terraform-state"
key            = "env/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-lock"
encrypt        = true
