"""
Executive Summary Agent - Weekly Security Brief Generator
==========================================================
Epic 5 Subissue 2

Runs every Monday at 8AM UTC via EventBridge.
Queries OpenSearch for the prior 7 days of agent metrics,
generates a plain-English executive brief and commits it to GitHub.
"""

import os
import json
import logging
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
import urllib3

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "donta-dalpoas/AWS-Blue-Team")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Setup logging
logger = logging.getLogger("executive-summary")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

http = urllib3.PoolManager()


# -----------------------------------------------------------------------------
# OpenSearch Queries
# -----------------------------------------------------------------------------
def query_opensearch(query_body: dict, index: str = "agent-metrics-*") -> dict:
    """Execute a query against OpenSearch."""
    url = f"https://{OPENSEARCH_ENDPOINT}/{index}/_search"

    try:
        response = http.request(
            "POST",
            url,
            body=json.dumps(query_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

        if response.status != 200:
            logger.error(f"OpenSearch query failed: {response.status} - {response.data.decode()}")
            raise Exception(f"OpenSearch returned {response.status}")

        return json.loads(response.data.decode("utf-8"))
    except Exception as e:
        logger.error(f"OpenSearch connection error: {e}")
        raise


def get_metrics_for_period(start_date: datetime, end_date: datetime) -> dict:
    """Query all required metrics for a given time period."""
    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": start_date.isoformat(),
                                "lte": end_date.isoformat(),
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "total_alerts": {"value_count": {"field": "alert_id.keyword"}},
            "mttd_stats": {"percentiles": {"field": "mttd_seconds", "percents": [50, 95]}},
            "mttr_stats": {"percentiles": {"field": "mttr_seconds", "percents": [50, 95]}},
            "auto_remediations": {
                "filter": {"term": {"action_type.keyword": "auto_remediate"}},
                "aggs": {"count": {"value_count": {"field": "action_id.keyword"}}},
            },
            "approval_gated": {
                "filter": {"term": {"action_type.keyword": "approval_gated"}},
                "aggs": {"count": {"value_count": {"field": "action_id.keyword"}}},
            },
            "compliance_violations_found": {
                "filter": {"term": {"metric_type.keyword": "compliance_violation_found"}},
                "aggs": {"count": {"value_count": {"field": "metric_id.keyword"}}},
            },
            "compliance_violations_fixed": {
                "filter": {"term": {"metric_type.keyword": "compliance_violation_fixed"}},
                "aggs": {"count": {"value_count": {"field": "metric_id.keyword"}}},
            },
            "hunt_runs": {
                "filter": {"term": {"agent.keyword": "threat-hunter"}},
                "aggs": {"count": {"value_count": {"field": "run_id.keyword"}}},
            },
            "rules_generated": {
                "filter": {"term": {"metric_type.keyword": "detection_rule_created"}},
                "aggs": {"count": {"value_count": {"field": "rule_id.keyword"}}},
            },
            "redteam_detection_rate": {
                "filter": {"term": {"agent.keyword": "red-team"}},
                "aggs": {
                    "detected": {
                        "filter": {"term": {"detected.keyword": "true"}},
                        "aggs": {"count": {"value_count": {"field": "technique_id.keyword"}}},
                    },
                    "total": {"value_count": {"field": "technique_id.keyword"}},
                },
            },
            "redteam_mttd": {
                "filter": {
                    "bool": {
                        "must": [
                            {"term": {"agent.keyword": "red-team"}},
                            {"term": {"detected.keyword": "true"}},
                        ]
                    }
                },
                "aggs": {"avg_mttd": {"avg": {"field": "mttd_seconds"}}},
            },
        },
    }

    return query_opensearch(query)


def get_top_incidents(start_date: datetime, end_date: datetime, count: int = 3) -> list:
    """Get top incidents from the past week by severity."""
    query = {
        "size": count,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"@timestamp": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                    {"terms": {"severity.keyword": ["critical", "high"]}},
                ]
            }
        },
        "sort": [{"severity_score": {"order": "desc"}}, {"@timestamp": {"order": "desc"}}],
        "_source": ["title", "severity", "agent", "resolution_status"],
    }

    result = query_opensearch(query, index="security-incidents-*")
    return result.get("hits", {}).get("hits", [])


# -----------------------------------------------------------------------------
# Metrics Extraction
# -----------------------------------------------------------------------------
def extract_metrics(response: dict) -> dict:
    """Extract metrics from OpenSearch aggregation response."""
    aggs = response.get("aggregations", {})

    return {
        "total_alerts": int(aggs.get("total_alerts", {}).get("value", 0)),
        "mttd_p50": aggs.get("mttd_stats", {}).get("values", {}).get("50.0", 0),
        "mttd_p95": aggs.get("mttd_stats", {}).get("values", {}).get("95.0", 0),
        "mttr_p50": aggs.get("mttr_stats", {}).get("values", {}).get("50.0", 0),
        "mttr_p95": aggs.get("mttr_stats", {}).get("values", {}).get("95.0", 0),
        "auto_remediations": int(
            aggs.get("auto_remediations", {}).get("count", {}).get("value", 0)
        ),
        "approval_gated": int(
            aggs.get("approval_gated", {}).get("count", {}).get("value", 0)
        ),
        "compliance_found": int(
            aggs.get("compliance_violations_found", {}).get("count", {}).get("value", 0)
        ),
        "compliance_fixed": int(
            aggs.get("compliance_violations_fixed", {}).get("count", {}).get("value", 0)
        ),
        "hunt_runs": int(aggs.get("hunt_runs", {}).get("count", {}).get("value", 0)),
        "rules_generated": int(
            aggs.get("rules_generated", {}).get("count", {}).get("value", 0)
        ),
        "redteam_detected": int(
            aggs.get("redteam_detection_rate", {}).get("detected", {}).get("count", {}).get("value", 0)
        ),
        "redteam_total": int(
            aggs.get("redteam_detection_rate", {}).get("total", {}).get("value", 0)
        ),
        "redteam_mttd": aggs.get("redteam_mttd", {}).get("avg_mttd", {}).get("value", 0),
    }


def compute_trend(current: float, previous: float) -> str:
    """Compute trend indicator between two values."""
    if previous == 0:
        return "—" if current == 0 else "NEW"
    change = ((current - previous) / previous) * 100
    if abs(change) < 5:
        return "stable"
    elif change > 0:
        return f"+{change:.0f}%"
    else:
        return f"{change:.0f}%"


def compute_time_trend(current: float, previous: float) -> str:
    """Compute trend for time metrics (lower is better)."""
    if previous == 0:
        return "—" if current == 0 else "NEW"
    change = ((current - previous) / previous) * 100
    if abs(change) < 5:
        return "stable"
    elif change > 0:
        return f"+{change:.0f}% (degraded)"
    else:
        return f"{change:.0f}% (improved)"


# -----------------------------------------------------------------------------
# Report Generation
# -----------------------------------------------------------------------------
def format_seconds(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds == 0:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def generate_executive_summary(current: dict, previous: dict, incidents: list) -> str:
    """Generate the executive summary paragraph."""
    total_alerts = current["total_alerts"]
    auto_remediations = current["auto_remediations"]
    compliance_score = (
        (current["compliance_fixed"] / current["compliance_found"] * 100)
        if current["compliance_found"] > 0
        else 100
    )
    detection_rate = (
        (current["redteam_detected"] / current["redteam_total"] * 100)
        if current["redteam_total"] > 0
        else 0
    )

    alert_trend = "increased" if current["total_alerts"] > previous["total_alerts"] else "decreased"

    summary = (
        f"This week the platform processed {total_alerts} security alerts, "
        f"{'an increase' if alert_trend == 'increased' else 'a decrease'} "
        f"from {previous['total_alerts']} last week. "
        f"{auto_remediations} incidents were automatically remediated without human intervention. "
        f"The compliance posture stands at {compliance_score:.0f}% of resources within baseline. "
    )

    if detection_rate > 0:
        summary += (
            f"Red Team exercises achieved a {detection_rate:.0f}% detection rate "
            f"with a mean time to detect of {format_seconds(current['redteam_mttd'])}."
        )
    else:
        summary += "No Red Team exercises were conducted this period."

    return summary


def generate_watch_items(current: dict, previous: dict) -> list:
    """Identify metrics that degraded week-over-week."""
    watch_items = []

    # MTTD degradation
    if current["mttd_p50"] > previous["mttd_p50"] * 1.1 and previous["mttd_p50"] > 0:
        watch_items.append(
            f"Mean Time to Detect (p50) increased from {format_seconds(previous['mttd_p50'])} "
            f"to {format_seconds(current['mttd_p50'])}"
        )

    # MTTR degradation
    if current["mttr_p50"] > previous["mttr_p50"] * 1.1 and previous["mttr_p50"] > 0:
        watch_items.append(
            f"Mean Time to Respond (p50) increased from {format_seconds(previous['mttr_p50'])} "
            f"to {format_seconds(current['mttr_p50'])}"
        )

    # Alert volume spike
    if current["total_alerts"] > previous["total_alerts"] * 1.5 and previous["total_alerts"] > 0:
        watch_items.append(
            f"Alert volume spiked {current['total_alerts'] / previous['total_alerts']:.1f}x "
            f"week-over-week ({previous['total_alerts']} -> {current['total_alerts']})"
        )

    # Compliance score drop
    current_compliance = (
        current["compliance_fixed"] / current["compliance_found"] * 100
        if current["compliance_found"] > 0
        else 100
    )
    previous_compliance = (
        previous["compliance_fixed"] / previous["compliance_found"] * 100
        if previous["compliance_found"] > 0
        else 100
    )
    if current_compliance < previous_compliance - 5:
        watch_items.append(
            f"Compliance score dropped from {previous_compliance:.0f}% to {current_compliance:.0f}%"
        )

    # Detection rate drop
    current_rate = (
        current["redteam_detected"] / current["redteam_total"] * 100
        if current["redteam_total"] > 0
        else None
    )
    previous_rate = (
        previous["redteam_detected"] / previous["redteam_total"] * 100
        if previous["redteam_total"] > 0
        else None
    )
    if current_rate and previous_rate and current_rate < previous_rate - 10:
        watch_items.append(
            f"Red Team detection rate dropped from {previous_rate:.0f}% to {current_rate:.0f}%"
        )

    if not watch_items:
        watch_items.append("No significant degradations detected this week.")

    return watch_items


def generate_brief(
    report_date: datetime,
    current: dict,
    previous: dict,
    incidents: list,
) -> str:
    """Generate the full executive brief markdown."""
    date_str = report_date.strftime("%Y-%m-%d")

    # Compute compliance score
    compliance_score = (
        (current["compliance_fixed"] / current["compliance_found"] * 100)
        if current["compliance_found"] > 0
        else 100
    )
    prev_compliance = (
        (previous["compliance_fixed"] / previous["compliance_found"] * 100)
        if previous["compliance_found"] > 0
        else 100
    )

    # Detection coverage
    detection_coverage = (
        (current["redteam_detected"] / current["redteam_total"] * 100)
        if current["redteam_total"] > 0
        else 0
    )
    prev_detection = (
        (previous["redteam_detected"] / previous["redteam_total"] * 100)
        if previous["redteam_total"] > 0
        else 0
    )

    lines = [
        f"## Weekly Security Brief - {date_str}",
        "",
        "### Executive Summary",
        generate_executive_summary(current, previous, incidents),
        "",
        "### Key Metrics",
        "| Metric | This Week | Last Week | Trend |",
        "|--------|-----------|-----------|-------|",
        f"| Alerts Processed | {current['total_alerts']} | {previous['total_alerts']} | {compute_trend(current['total_alerts'], previous['total_alerts'])} |",
        f"| MTTD (p50) | {format_seconds(current['mttd_p50'])} | {format_seconds(previous['mttd_p50'])} | {compute_time_trend(current['mttd_p50'], previous['mttd_p50'])} |",
        f"| MTTD (p95) | {format_seconds(current['mttd_p95'])} | {format_seconds(previous['mttd_p95'])} | {compute_time_trend(current['mttd_p95'], previous['mttd_p95'])} |",
        f"| MTTR (p50) | {format_seconds(current['mttr_p50'])} | {format_seconds(previous['mttr_p50'])} | {compute_time_trend(current['mttr_p50'], previous['mttr_p50'])} |",
        f"| MTTR (p95) | {format_seconds(current['mttr_p95'])} | {format_seconds(previous['mttr_p95'])} | {compute_time_trend(current['mttr_p95'], previous['mttr_p95'])} |",
        f"| Auto-Remediations | {current['auto_remediations']} | {previous['auto_remediations']} | {compute_trend(current['auto_remediations'], previous['auto_remediations'])} |",
        f"| Approval-Gated Actions | {current['approval_gated']} | {previous['approval_gated']} | {compute_trend(current['approval_gated'], previous['approval_gated'])} |",
        f"| Compliance Score | {compliance_score:.0f}% | {prev_compliance:.0f}% | {compute_trend(compliance_score, prev_compliance)} |",
        f"| Detection Coverage | {detection_coverage:.0f}% | {prev_detection:.0f}% | {compute_trend(detection_coverage, prev_detection)} |",
        f"| Hunt Runs | {current['hunt_runs']} | {previous['hunt_runs']} | {compute_trend(current['hunt_runs'], previous['hunt_runs'])} |",
        f"| Rules Generated | {current['rules_generated']} | {previous['rules_generated']} | {compute_trend(current['rules_generated'], previous['rules_generated'])} |",
        "",
        "### Top 3 Incidents",
    ]

    if incidents:
        for i, incident in enumerate(incidents[:3], 1):
            source = incident.get("_source", {})
            title = source.get("title", "Untitled incident")
            severity = source.get("severity", "unknown")
            lines.append(f"{i}. [{severity.upper()}] {title}")
    else:
        lines.append("*No critical/high incidents this week.*")

    lines.append("")
    lines.append("### Watch Items")

    watch_items = generate_watch_items(current, previous)
    for item in watch_items:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated automatically by Executive Summary Agent on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# GitHub Integration
# -----------------------------------------------------------------------------
def commit_to_github(content: str, report_date: datetime) -> bool:
    """Commit the report to docs/weekly-reports/ via GitHub API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.warning("GitHub token/repo not configured; skipping commit")
        return False

    date_str = report_date.strftime("%Y-%m-%d")
    file_path = f"docs/weekly-reports/{date_str}.md"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Check if file exists (for update vs create)
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # Try to get existing file SHA
    sha = None
    try:
        get_response = http.request("GET", api_url, headers=headers, timeout=10.0)
        if get_response.status == 200:
            existing = json.loads(get_response.data.decode("utf-8"))
            sha = existing.get("sha")
    except Exception:
        pass

    # Create/update the file
    payload = {
        "message": f"docs: weekly security brief {date_str}",
        "content": encoded_content,
        "committer": {
            "name": "executive-summary-agent[bot]",
            "email": "executive-summary-agent[bot]@users.noreply.github.com",
        },
    }
    if sha:
        payload["sha"] = sha

    try:
        response = http.request(
            "PUT",
            api_url,
            body=json.dumps(payload).encode("utf-8"),
            headers=headers,
            timeout=15.0,
        )

        if response.status in (200, 201):
            logger.info(f"Successfully committed report to {file_path}")
            return True
        else:
            logger.error(f"GitHub commit failed: {response.status} - {response.data.decode()}")
            return False
    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return False


# -----------------------------------------------------------------------------
# Lambda Handler
# -----------------------------------------------------------------------------
def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for the Executive Summary Agent.

    Triggered by EventBridge every Monday at 8AM UTC.
    """
    logger.info("Executive Summary Agent invoked")
    logger.info(f"Event: {json.dumps(event)}")

    now = datetime.now(timezone.utc)
    report_date = now

    # Define time periods
    current_end = now
    current_start = now - timedelta(days=7)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=7)

    try:
        # Query metrics for current and previous weeks
        logger.info(f"Querying metrics: current={current_start.isoformat()} to {current_end.isoformat()}")
        current_response = get_metrics_for_period(current_start, current_end)
        current_metrics = extract_metrics(current_response)

        logger.info(f"Querying metrics: previous={previous_start.isoformat()} to {previous_end.isoformat()}")
        previous_response = get_metrics_for_period(previous_start, previous_end)
        previous_metrics = extract_metrics(previous_response)

        # Get top incidents
        logger.info("Querying top incidents")
        incidents = get_top_incidents(current_start, current_end)

        # Generate the brief
        logger.info("Generating executive brief")
        brief = generate_brief(report_date, current_metrics, previous_metrics, incidents)

        # Commit to GitHub
        logger.info("Committing to GitHub")
        github_success = commit_to_github(brief, report_date)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Executive summary generated successfully",
                    "report_date": report_date.strftime("%Y-%m-%d"),
                    "github_committed": github_success,
                    "metrics": {
                        "total_alerts": current_metrics["total_alerts"],
                        "mttd_p50": current_metrics["mttd_p50"],
                        "mttr_p50": current_metrics["mttr_p50"],
                    },
                }
            ),
        }

    except Exception as e:
        error_msg = f"Executive Summary Agent failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}),
        }
