# =============================================================================
# AgentCore Policy Module - Cedar Evaluator Lambda
# =============================================================================

data "archive_file" "cedar_evaluator" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/cedar-evaluator"
  output_path = "${path.module}/cedar-evaluator.zip"
}

# Policy bucket
resource "aws_s3_bucket" "cedar_policies" {
  bucket = "${var.account_id}-${var.aws_region}-cedar-policies"

  tags = { Name = "${var.name_prefix}-cedar-policies" }
}

resource "aws_s3_bucket_versioning" "cedar_policies" {
  bucket = aws_s3_bucket.cedar_policies.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "cedar_policies" {
  bucket                  = aws_s3_bucket.cedar_policies.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Cedar Evaluator Lambda
resource "aws_lambda_function" "cedar_evaluator" {
  filename         = data.archive_file.cedar_evaluator.output_path
  function_name    = "cedar-policy-evaluator"
  role             = aws_iam_role.cedar_evaluator.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.cedar_evaluator.output_base64sha256
  runtime          = "python3.12"
  architectures    = ["arm64"]
  memory_size      = 256
  timeout          = 5

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      POLICY_BUCKET = aws_s3_bucket.cedar_policies.id
      POLICY_PREFIX = "cedar/"
    }
  }

  tags = { Name = "${var.name_prefix}-cedar-evaluator" }
}

# IAM Role
resource "aws_iam_role" "cedar_evaluator" {
  name = "${var.name_prefix}-cedar-evaluator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${var.name_prefix}-cedar-evaluator-role" }
}

resource "aws_iam_role_policy" "cedar_evaluator" {
  name = "cedar-evaluator-permissions"
  role = aws_iam_role.cedar_evaluator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.cedar_policies.arn,
          "${aws_s3_bucket.cedar_policies.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
