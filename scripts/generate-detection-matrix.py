#!/usr/bin/env python3
"""
Generate Detection Matrix Document
===================================
Reads all YAML files from detections/ and generates docs/detection-matrix.md
with a table showing: Rule ID, Name, MITRE Technique, Severity, Author, Last Updated.
Sorted by severity (Critical first).
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime

DETECTIONS_DIR = Path("detections")
OUTPUT_FILE = Path("docs/detection-matrix.md")

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


def load_detection_rules():
    """Load all YAML detection rule files."""
    rules = []

    if not DETECTIONS_DIR.exists():
        print(f"WARNING: {DETECTIONS_DIR} directory does not exist. Creating empty matrix.")
        return rules

    for yaml_file in sorted(DETECTIONS_DIR.glob("*.yml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                data["_source_file"] = yaml_file.name
                rules.append(data)
        except yaml.YAMLError as e:
            print(f"ERROR: Failed to parse {yaml_file}: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to read {yaml_file}: {e}", file=sys.stderr)
            sys.exit(1)

    return rules


def sort_rules(rules):
    """Sort rules by severity (Critical first), then by name."""
    return sorted(
        rules,
        key=lambda r: (
            SEVERITY_ORDER.get(r.get("severity", "low").lower(), 99),
            r.get("name", ""),
        ),
    )


def generate_markdown(rules):
    """Generate the detection matrix markdown content."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Detection Matrix",
        "",
        f"> Auto-generated on {timestamp} by `scripts/generate-detection-matrix.py`",
        "> **Do not edit manually** — this file is regenerated on every merge to `main`.",
        "",
        f"**Total Detection Rules:** {len(rules)}",
        "",
        "| Rule ID | Name | MITRE Technique | Severity | Author | Last Updated |",
        "|---------|------|-----------------|----------|--------|--------------|",
    ]

    for rule in rules:
        rule_id = rule.get("id", "N/A")
        name = rule.get("name", "Unnamed Rule")
        technique = rule.get("mitre_technique", "N/A")
        severity = rule.get("severity", "Unknown")
        author = rule.get("author", "Unknown")
        last_updated = rule.get("last_updated", "Unknown")

        # Format severity with emoji indicator
        severity_display = {
            "critical": "🔴 Critical",
            "high": "🟠 High",
            "medium": "🟡 Medium",
            "low": "🟢 Low",
            "informational": "ℹ️ Info",
        }.get(severity.lower(), severity)

        lines.append(
            f"| {rule_id} | {name} | {technique} | {severity_display} | {author} | {last_updated} |"
        )

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated from `{DETECTIONS_DIR}/` — {len(rules)} rules indexed.*")
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"[docs-regen] Generating detection matrix from {DETECTIONS_DIR}/...")

    rules = load_detection_rules()
    sorted_rules = sort_rules(rules)
    content = generate_markdown(sorted_rules)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print(f"[docs-regen] Wrote {OUTPUT_FILE} ({len(sorted_rules)} rules)")


if __name__ == "__main__":
    main()
