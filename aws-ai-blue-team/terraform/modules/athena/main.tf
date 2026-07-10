# =============================================================================
# Athena Module - Glue Catalog + Athena Workgroup
# =============================================================================

# -----------------------------------------------------------------------------
# Glue Catalog Database
# -----------------------------------------------------------------------------
resource "aws_glue_catalog_database" "security_logs" {
  name = "security_logs"

  description = "Database for AWS AI Blue Team security log analysis"
}

# -----------------------------------------------------------------------------
# Glue Table: CloudTrail Logs
# -----------------------------------------------------------------------------
resource "aws_glue_catalog_table" "cloudtrail_logs" {
  name          = "cloudtrail_logs"
  database_name = aws_glue_catalog_database.security_logs.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "projection.enabled"        = "true"
    "projection.region.type"    = "enum"
    "projection.region.values"  = join(",", var.active_regions)
    "projection.year.type"      = "integer"
    "projection.year.range"     = "2024,2030"
    "projection.month.type"     = "integer"
    "projection.month.range"    = "01,12"
    "projection.month.digits"   = "2"
    "projection.day.type"       = "integer"
    "projection.day.range"      = "01,31"
    "projection.day.digits"     = "2"
    "storage.location.template" = "s3://${var.s3_bucket_name}/cloudtrail/AWSLogs/${var.account_id}/CloudTrail/$${region}/$${year}/$${month}/$${day}/"
    "classification"            = "cloudtrail"
    "compressionType"           = "gzip"
  }

  storage_descriptor {
    location      = "s3://${var.s3_bucket_name}/cloudtrail/AWSLogs/${var.account_id}/CloudTrail/"
    input_format  = "com.amazon.emr.cloudtrail.CloudTrailInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hive.hcatalog.data.JsonSerDe"
    }

    columns {
      name = "eventversion"
      type = "string"
    }
    columns {
      name = "eventtime"
      type = "string"
    }
    columns {
      name = "eventsource"
      type = "string"
    }
    columns {
      name = "eventname"
      type = "string"
    }
    columns {
      name = "awsregion"
      type = "string"
    }
    columns {
      name = "sourceipaddress"
      type = "string"
    }
    columns {
      name = "useragent"
      type = "string"
    }
    columns {
      name = "errorcode"
      type = "string"
    }
    columns {
      name = "errormessage"
      type = "string"
    }
    columns {
      name = "useridentity"
      type = "string"
    }
    columns {
      name = "requestparameters"
      type = "string"
    }
    columns {
      name = "responseelements"
      type = "string"
    }
    columns {
      name = "requestid"
      type = "string"
    }
    columns {
      name = "eventid"
      type = "string"
    }
    columns {
      name = "eventtype"
      type = "string"
    }
    columns {
      name = "recipientaccountid"
      type = "string"
    }
  }

  partition_keys {
    name = "region"
    type = "string"
  }
  partition_keys {
    name = "year"
    type = "string"
  }
  partition_keys {
    name = "month"
    type = "string"
  }
  partition_keys {
    name = "day"
    type = "string"
  }
}

# -----------------------------------------------------------------------------
# Glue Table: VPC Flow Logs (Parquet)
# -----------------------------------------------------------------------------
resource "aws_glue_catalog_table" "vpc_flow_logs" {
  name          = "vpc_flow_logs"
  database_name = aws_glue_catalog_database.security_logs.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "projection.enabled"        = "true"
    "projection.year.type"      = "integer"
    "projection.year.range"     = "2024,2030"
    "projection.month.type"     = "integer"
    "projection.month.range"    = "01,12"
    "projection.month.digits"   = "2"
    "projection.day.type"       = "integer"
    "projection.day.range"      = "01,31"
    "projection.day.digits"     = "2"
    "projection.hour.type"      = "integer"
    "projection.hour.range"     = "00,23"
    "projection.hour.digits"    = "2"
    "storage.location.template" = "s3://${var.s3_bucket_name}/vpc-flow-logs/AWSLogs/${var.account_id}/vpcflowlogs/year=$${year}/month=$${month}/day=$${day}/hour=$${hour}/"
    "classification"            = "parquet"
  }

  storage_descriptor {
    location      = "s3://${var.s3_bucket_name}/vpc-flow-logs/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "version"
      type = "int"
    }
    columns {
      name = "account_id"
      type = "string"
    }
    columns {
      name = "interface_id"
      type = "string"
    }
    columns {
      name = "srcaddr"
      type = "string"
    }
    columns {
      name = "dstaddr"
      type = "string"
    }
    columns {
      name = "srcport"
      type = "int"
    }
    columns {
      name = "dstport"
      type = "int"
    }
    columns {
      name = "protocol"
      type = "bigint"
    }
    columns {
      name = "packets"
      type = "bigint"
    }
    columns {
      name = "bytes"
      type = "bigint"
    }
    columns {
      name = "start"
      type = "bigint"
    }
    columns {
      name = "end_time"
      type = "bigint"
    }
    columns {
      name = "action"
      type = "string"
    }
    columns {
      name = "log_status"
      type = "string"
    }
    columns {
      name = "vpc_id"
      type = "string"
    }
    columns {
      name = "subnet_id"
      type = "string"
    }
    columns {
      name = "tcp_flags"
      type = "int"
    }
    columns {
      name = "type"
      type = "string"
    }
    columns {
      name = "pkt_srcaddr"
      type = "string"
    }
    columns {
      name = "pkt_dstaddr"
      type = "string"
    }
    columns {
      name = "flow_direction"
      type = "string"
    }
    columns {
      name = "traffic_path"
      type = "int"
    }
  }

  partition_keys {
    name = "year"
    type = "string"
  }
  partition_keys {
    name = "month"
    type = "string"
  }
  partition_keys {
    name = "day"
    type = "string"
  }
  partition_keys {
    name = "hour"
    type = "string"
  }
}

# -----------------------------------------------------------------------------
# Athena Workgroup
# -----------------------------------------------------------------------------
resource "aws_athena_workgroup" "security_analytics" {
  name = "security-analytics"

  configuration {
    enforce_workgroup_configuration = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 10737418240 # 10 GB

    result_configuration {
      output_location = "s3://${var.s3_bucket_name}/athena-results/"
    }
  }

  tags = {
    Name = "${var.name_prefix}-athena-workgroup"
  }
}

# Validation named query
resource "aws_athena_named_query" "validation" {
  name      = "${var.name_prefix}-validation-query"
  workgroup = aws_athena_workgroup.security_analytics.name
  database  = aws_glue_catalog_database.security_logs.name
  query     = "SELECT eventtime, eventsource, eventname, sourceipaddress, awsregion FROM security_logs.cloudtrail_logs WHERE region = '${var.active_regions[0]}' LIMIT 10;"

  description = "Validation query to confirm CloudTrail partition projection works"
}
