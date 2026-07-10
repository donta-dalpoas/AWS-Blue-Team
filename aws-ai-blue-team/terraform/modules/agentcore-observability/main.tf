# =============================================================================
# AgentCore Observability Module - Dashboard + Alarms
# =============================================================================

# -----------------------------------------------------------------------------
# CloudWatch Dashboard
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "agentcore" {
  dashboard_name = "AgentCore-Overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.gateway_lambda_name, { stat = "Sum" }]
          ]
          period = 300
          title  = "Total Gateway Invocations"
          region = data.aws_region.current.name
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 0
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.gateway_lambda_name, { stat = "Sum", id = "errors" }],
            ["AWS/Lambda", "Invocations", "FunctionName", var.gateway_lambda_name, { stat = "Sum", id = "invocations", visible = false }],
            [{ expression = "(errors/invocations)*100", label = "Error Rate %", id = "errorRate" }]
          ]
          period = 300
          title  = "Gateway Error Rate"
          region = data.aws_region.current.name
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.gateway_lambda_name, { stat = "p99" }]
          ]
          period = 60
          title  = "Gateway p99 Latency (ms)"
          region = data.aws_region.current.name
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 0
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.evaluator_lambda_name, { stat = "Sum" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.evaluator_lambda_name, { stat = "Sum" }]
          ]
          period = 300
          title  = "Cedar Policy Evaluator"
          region = data.aws_region.current.name
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.evaluator_lambda_name, { stat = "p50", label = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.evaluator_lambda_name, { stat = "p90", label = "p90" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.evaluator_lambda_name, { stat = "p99", label = "p99" }]
          ]
          period = 60
          title  = "Cedar Evaluation Latency"
          region = data.aws_region.current.name
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Throttles", "FunctionName", var.gateway_lambda_name, { stat = "Sum" }],
            ["AWS/Lambda", "Throttles", "FunctionName", var.evaluator_lambda_name, { stat = "Sum" }]
          ]
          period = 300
          title  = "Lambda Throttles"
          region = data.aws_region.current.name
        }
      }
    ]
  })
}

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# CloudWatch Alarms
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "gateway_errors" {
  alarm_name          = "${var.name_prefix}-gateway-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "AgentCore Gateway Lambda errors detected"

  dimensions = {
    FunctionName = var.gateway_lambda_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = { Name = "${var.name_prefix}-gateway-errors-alarm" }
}

resource "aws_cloudwatch_metric_alarm" "cedar_errors" {
  alarm_name          = "${var.name_prefix}-cedar-evaluator-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "CRITICAL: Cedar policy evaluator failed - agents cannot be authorized"

  dimensions = {
    FunctionName = var.evaluator_lambda_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = { Name = "${var.name_prefix}-cedar-errors-alarm" }
}

resource "aws_cloudwatch_metric_alarm" "gateway_latency" {
  alarm_name          = "${var.name_prefix}-gateway-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 10000
  alarm_description   = "AgentCore Gateway p99 latency exceeds 10 seconds"

  dimensions = {
    FunctionName = var.gateway_lambda_name
  }

  alarm_actions = [var.sns_alert_topic_arn]

  tags = { Name = "${var.name_prefix}-gateway-latency-alarm" }
}
