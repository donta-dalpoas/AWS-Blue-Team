# =============================================================================
# VPC Flow Logs Module
# =============================================================================
# Enables flow logs on each provided VPC, writing to S3 in Parquet format.
# =============================================================================

resource "aws_flow_log" "vpc" {
  count = length(var.vpc_ids)

  vpc_id               = var.vpc_ids[count.index]
  log_destination_type = "s3"
  log_destination      = "${var.s3_bucket_arn}/vpc-flow-logs/"
  traffic_type         = "ALL"
  max_aggregation_interval = 60

  log_format = "$${version} $${account-id} $${interface-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${start} $${end} $${action} $${log-status} $${vpc-id} $${subnet-id} $${tcp-flags} $${type} $${pkt-srcaddr} $${pkt-dstaddr} $${flow-direction} $${traffic-path}"

  destination_options {
    file_format                = "parquet"
    hive_compatible_partitions = true
    per_hour_partition         = true
  }

  tags = {
    Name = "${var.name_prefix}-flow-log-${count.index}"
  }
}
