#!/usr/bin/env python3
"""
Generate Cedar Policy Summary Document
========================================
Reads Cedar policy files from policies/cedar/ and generates
docs/cedar-policy-summary.md with a table showing:
Agent, Allowed Actions, Denied Actions, Resource Scope.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

CEDAR_DIR = Path("policies/cedar")
OUTPUT_FILE = Path("docs/cedar-policy-summary.md")


def parse_cedar_file(filepath):
    """Parse a Cedar policy file and extract policy information."""
    policies = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Could not read {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse permit/forbid blocks
    # Cedar format: permit|forbid (principal, action, resource) when { ... };
    policy_pattern = re.compile(
        r"(permit|forbid)\s*\(\s*"
        r"principal\s*(?:==\s*([^\s,]+)|in\s*([^\s,]+))?\s*,\s*"
        r"action\s*(?:==\s*([^\s,]+)|in\s*\[([^\]]*)\])?\s*,\s*"
        r"resource\s*(?:==\s*([^\s,)]+)|in\s*([^\s,)]+))?\s*\)",
        re.MULTILINE | re.DOTALL,
    )

    # Simpler approach: parse comment-annotated blocks
    # Look for @agent annotations and action lists
    current_agent = filepath.stem  # default to filename
    current_description = ""

    # Parse annotations
    agent_match = re.search(r"//\s*@agent:\s*(.+)", content)
    if agent_match:
        current_agent = agent_match.group(1).strip()

    desc_match = re.search(r"//\s*@description:\s*(.+)", content)
    if desc_match:
        current_description = desc_match.group(1).strip()

    # Extract permit actions
    permit_actions = []
    for match in re.finditer(r"permit\s*\([^)]*action\s*(?:==\s*Action::\"([^\"]+)\"|in\s*\[([^\]]+)\])", content):
        if match.group(1):
            permit_actions.append(match.group(1))
        elif match.group(2):
            actions = re.findall(r'Action::"([^"]+)"', match.group(2))
            permit_actions.extend(actions)

    # Extract forbid actions
    forbid_actions = []
    for match in re.finditer(r"forbid\s*\([^)]*action\s*(?:==\s*Action::\"([^\"]+)\"|in\s*\[([^\]]+)\])", content):
        if match.group(1):
            forbid_actions.append(match.group(1))
        elif match.group(2):
            actions = re.findall(r'Action::"([^"]+)"', match.group(2))
            forbid_actions.extend(actions)

    # Extract resource scope
    resource_scope = "All"
    resource_match = re.search(r"resource\s*(?:==|in)\s*([^\s,)]+)", content)
    if resource_match:
        resource_scope = resource_match.group(1)

    # Also look for simpler annotation-based format
    if not permit_actions:
        for match in re.finditer(r"//\s*@allows?:\s*(.+)", content):
            permit_actions.extend(
                [a.strip() for a in match.group(1).split(",")]
            )

    if not forbid_actions:
        for match in re.finditer(r"//\s*@(?:denies?|forbids?):\s*(.+)", content):
            forbid_actions.extend(
                [a.strip() for a in match.group(1).split(",")]
            )

    policies.append(
        {
            "agent": current_agent,
            "description": current_description,
            "allowed_actions": permit_actions,
            "denied_actions": forbid_actions,
            "resource_scope": resource_scope,
            "source_file": filepath.name,
        }
    )

    return policies


def generate_markdown(all_policies):
    """Generate the Cedar policy summary markdown."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Cedar Policy Summary",
        "",
        f"> Auto-generated on {timestamp} by `scripts/generate-cedar-policy-summary.py`",
        "> **Do not edit manually** — this file is regenerated on every merge to `main`.",
        "",
        f"**Total Policies:** {len(all_policies)}",
        f"**Policy Directory:** `{CEDAR_DIR}/`",
        "",
        "## Policy Matrix",
        "",
        "| Agent | Allowed Actions | Denied Actions | Resource Scope | Source File |",
        "|-------|----------------|----------------|----------------|-------------|",
    ]

    for policy in all_policies:
        agent = policy["agent"]
        allowed = ", ".join(policy["allowed_actions"]) if policy["allowed_actions"] else "*None explicitly listed*"
        denied = ", ".join(policy["denied_actions"]) if policy["denied_actions"] else "*None explicitly listed*"
        scope = policy["resource_scope"]
        source = policy["source_file"]

        lines.append(f"| **{agent}** | {allowed} | {denied} | `{scope}` | `{source}` |")

    lines.append("")

    # Detailed per-policy section
    lines.append("## Policy Details")
    lines.append("")

    for policy in all_policies:
        agent = policy["agent"]
        lines.append(f"### {agent}")
        lines.append("")
        if policy["description"]:
            lines.append(f"*{policy['description']}*")
            lines.append("")

        lines.append(f"**Source:** `{CEDAR_DIR}/{policy['source_file']}`")
        lines.append("")

        if policy["allowed_actions"]:
            lines.append("**Allowed Actions:**")
            for action in policy["allowed_actions"]:
                lines.append(f"- `{action}`")
            lines.append("")

        if policy["denied_actions"]:
            lines.append("**Denied Actions:**")
            for action in policy["denied_actions"]:
                lines.append(f"- `{action}`")
            lines.append("")

        lines.append(f"**Resource Scope:** `{policy['resource_scope']}`")
        lines.append("")

    lines.append("---")
    lines.append(
        f"*Generated from `{CEDAR_DIR}/` — {len(all_policies)} policies indexed.*"
    )
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"[docs-regen] Generating Cedar policy summary from {CEDAR_DIR}/...")

    all_policies = []

    if not CEDAR_DIR.exists():
        print(f"WARNING: {CEDAR_DIR} does not exist. Creating empty summary.")
    else:
        for cedar_file in sorted(CEDAR_DIR.glob("*.cedar")):
            policies = parse_cedar_file(cedar_file)
            all_policies.extend(policies)

    content = generate_markdown(all_policies)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print(f"[docs-regen] Wrote {OUTPUT_FILE} ({len(all_policies)} policies)")


if __name__ == "__main__":
    main()
