#!/usr/bin/env python3
"""
Generate Agent Capabilities Document
======================================
Reads agent config files from config/agents/ and Lambda definitions from lambdas/
to generate docs/agent-capabilities.md with a table showing:
Agent Name, Trigger, Tools Available, Cedar Policy Scope, Session Type, Timeout.
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime

AGENTS_CONFIG_DIR = Path("config/agents")
LAMBDAS_DIR = Path("lambdas")
OUTPUT_FILE = Path("docs/agent-capabilities.md")


def load_agent_configs():
    """Load all agent configuration YAML files."""
    agents = []

    if not AGENTS_CONFIG_DIR.exists():
        print(f"WARNING: {AGENTS_CONFIG_DIR} does not exist. Creating empty doc.")
        return agents

    for yaml_file in sorted(AGENTS_CONFIG_DIR.glob("*.yml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                data["_source_file"] = yaml_file.name
                agents.append(data)
        except yaml.YAMLError as e:
            print(f"ERROR: Failed to parse {yaml_file}: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to read {yaml_file}: {e}", file=sys.stderr)
            sys.exit(1)

    return agents


def generate_markdown(agents):
    """Generate the agent capabilities markdown."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Agent Capabilities",
        "",
        f"> Auto-generated on {timestamp} by `scripts/generate-agent-capabilities.py`",
        "> **Do not edit manually** — this file is regenerated on every merge to `main`.",
        "",
        f"**Total Agents:** {len(agents)}",
        "",
        "| Agent Name | Trigger | Tools Available | Cedar Policy Scope | Session Type | Timeout |",
        "|------------|---------|-----------------|-------------------|--------------|---------|",
    ]

    for agent in agents:
        name = agent.get("name", "Unknown")
        trigger = agent.get("trigger", {})
        trigger_type = trigger.get("type", "Unknown")
        trigger_detail = trigger.get("schedule", trigger.get("source", ""))
        trigger_display = f"{trigger_type}"
        if trigger_detail:
            trigger_display += f" (`{trigger_detail}`)"

        tools = agent.get("tools", [])
        tools_display = ", ".join(tools) if tools else "None"

        cedar_scope = agent.get("cedar_policy", {}).get("scope", "N/A")
        session_type = agent.get("session_type", "stateless")
        timeout = agent.get("timeout_seconds", "N/A")
        timeout_display = f"{timeout}s" if timeout != "N/A" else "N/A"

        lines.append(
            f"| **{name}** | {trigger_display} | {tools_display} | "
            f"{cedar_scope} | {session_type} | {timeout_display} |"
        )

    lines.append("")

    # Detailed breakdown per agent
    lines.append("## Agent Details")
    lines.append("")

    for agent in agents:
        name = agent.get("name", "Unknown")
        description = agent.get("description", "No description available.")
        lambda_name = agent.get("lambda_function", "N/A")
        runtime = agent.get("runtime", "python3.11")
        memory = agent.get("memory_mb", "N/A")
        architecture = agent.get("architecture", "arm64")

        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"**Description:** {description}")
        lines.append("")
        lines.append(f"- **Lambda:** `{lambda_name}`")
        lines.append(f"- **Runtime:** {runtime}")
        lines.append(f"- **Memory:** {memory} MB")
        lines.append(f"- **Architecture:** {architecture}")
        lines.append("")

        # Cedar permissions
        cedar = agent.get("cedar_policy", {})
        if cedar:
            lines.append("**Permissions (Cedar):**")
            allowed = cedar.get("allowed_actions", [])
            denied = cedar.get("denied_actions", [])
            if allowed:
                lines.append(f"- Allowed: {', '.join(allowed)}")
            if denied:
                lines.append(f"- Denied: {', '.join(denied)}")
            lines.append("")

    lines.append("---")
    lines.append(
        f"*Generated from `{AGENTS_CONFIG_DIR}/` and `{LAMBDAS_DIR}/` — "
        f"{len(agents)} agents indexed.*"
    )
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"[docs-regen] Generating agent capabilities from {AGENTS_CONFIG_DIR}/...")

    agents = load_agent_configs()
    content = generate_markdown(agents)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print(f"[docs-regen] Wrote {OUTPUT_FILE} ({len(agents)} agents)")


if __name__ == "__main__":
    main()
