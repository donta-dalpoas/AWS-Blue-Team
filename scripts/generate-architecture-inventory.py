#!/usr/bin/env python3
"""
Generate Architecture Inventory Document
==========================================
Parses Terraform module structure to generate docs/architecture-inventory.md
with a table showing: Resource Type, Resource Name, Region, Module/Epic, Tags.
Grouped by Epic.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

TERRAFORM_DIR = Path("terraform")
MODULES_DIR = TERRAFORM_DIR / "modules"
OUTPUT_FILE = Path("docs/architecture-inventory.md")

# Mapping of modules to their Epic ownership
MODULE_EPIC_MAP = {
    "kms": ("Epic 1", "KMS encryption keys"),
    "storage": ("Epic 1", "S3 log storage"),
    "networking": ("Epic 1", "VPC and security groups"),
    "logging": ("Epic 1", "CloudTrail, GuardDuty, SecurityHub, VPC Flow Logs"),
    "sns": ("Epic 1", "SNS topics for security findings"),
    "athena": ("Epic 1", "Athena query workgroups"),
    "opensearch": ("Epic 1", "OpenSearch domain for security analytics"),
    "ingestion": ("Epic 1", "Log ingestion pipeline"),
    "baseline-generator": ("Epic 1", "Baseline configuration generator"),
    "agentcore-identity": ("Epic 2", "Agent IAM roles and identity"),
    "agentcore-policy": ("Epic 2", "Cedar policy evaluator"),
    "agentcore-gateway": ("Epic 2", "Agent gateway and routing"),
    "agentcore-observability": ("Epic 4", "Agent metrics and X-Ray tracing"),
    "executive-summary": ("Epic 5", "Weekly executive summary agent"),
}


def scan_terraform_resources(module_path):
    """Scan .tf files in a module for resource declarations."""
    resources = []

    if not module_path.exists():
        return resources

    for tf_file in module_path.glob("*.tf"):
        try:
            content = tf_file.read_text(encoding="utf-8")
            # Match resource blocks: resource "type" "name" {
            for match in re.finditer(
                r'resource\s+"([^"]+)"\s+"([^"]+)"', content
            ):
                resource_type = match.group(1)
                resource_name = match.group(2)
                resources.append(
                    {
                        "type": resource_type,
                        "name": resource_name,
                        "file": tf_file.name,
                    }
                )
        except Exception as e:
            print(f"WARNING: Could not read {tf_file}: {e}", file=sys.stderr)

    return resources


def generate_markdown():
    """Generate the architecture inventory markdown."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Architecture Inventory",
        "",
        f"> Auto-generated on {timestamp} by `scripts/generate-architecture-inventory.py`",
        "> **Do not edit manually** — this file is regenerated on every merge to `main`.",
        "",
    ]

    total_resources = 0
    epics_data = {}  # epic -> list of (module, resources)

    # Scan all modules
    if MODULES_DIR.exists():
        for module_dir in sorted(MODULES_DIR.iterdir()):
            if module_dir.is_dir():
                module_name = module_dir.name
                epic_info = MODULE_EPIC_MAP.get(module_name, ("Unassigned", module_name))
                epic = epic_info[0]
                description = epic_info[1]

                resources = scan_terraform_resources(module_dir)

                if epic not in epics_data:
                    epics_data[epic] = []

                epics_data[epic].append(
                    {
                        "module": module_name,
                        "description": description,
                        "resources": resources,
                    }
                )
                total_resources += len(resources)

    lines.append(f"**Total Modules:** {len(list(MODULES_DIR.iterdir())) if MODULES_DIR.exists() else 0}")
    lines.append(f"**Total Resources:** {total_resources}")
    lines.append("")

    # Generate grouped tables
    for epic in sorted(epics_data.keys()):
        lines.append(f"## {epic}")
        lines.append("")
        lines.append("| Resource Type | Resource Name | Module | Description |")
        lines.append("|---------------|---------------|--------|-------------|")

        for module_data in epics_data[epic]:
            if module_data["resources"]:
                for res in module_data["resources"]:
                    lines.append(
                        f"| `{res['type']}` | `{res['name']}` | "
                        f"`{module_data['module']}` | {module_data['description']} |"
                    )
            else:
                lines.append(
                    f"| *(module defined)* | — | "
                    f"`{module_data['module']}` | {module_data['description']} |"
                )

        lines.append("")

    lines.append("---")
    lines.append(
        f"*Generated from `{TERRAFORM_DIR}/` — "
        f"{total_resources} resources across {len(epics_data)} epics.*"
    )
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"[docs-regen] Generating architecture inventory from {TERRAFORM_DIR}/...")

    content = generate_markdown()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    module_count = len(list(MODULES_DIR.iterdir())) if MODULES_DIR.exists() else 0
    print(f"[docs-regen] Wrote {OUTPUT_FILE} ({module_count} modules scanned)")


if __name__ == "__main__":
    main()
