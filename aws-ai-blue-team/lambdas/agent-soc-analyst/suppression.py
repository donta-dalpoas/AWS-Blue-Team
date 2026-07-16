"""
Alert Suppression - Filters known-good patterns before reasoning.
"""
import json
import logging
import ipaddress
import os

logger = logging.getLogger()

# Load suppression rules at cold start
_suppression_rules = None


def load_suppression_rules():
    """Load suppression rules from bundled config file."""
    global _suppression_rules
    if _suppression_rules is not None:
        return _suppression_rules

    config_path = os.path.join(os.path.dirname(__file__), "suppression-rules.json")
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            _suppression_rules = data.get("rules", [])
            logger.info("Loaded %d suppression rules", len(_suppression_rules))
    except FileNotFoundError:
        logger.warning("Suppression rules file not found at %s", config_path)
        _suppression_rules = []
    except json.JSONDecodeError as e:
        logger.error("Failed to parse suppression rules: %s", str(e))
        _suppression_rules = []

    return _suppression_rules


def check_suppression(finding_meta):
    """Check if a finding matches any suppression rule.

    Returns: {"suppressed": bool, "rule_id": str, "reason": str}
    """
    rules = load_suppression_rules()

    for rule in rules:
        if not rule.get("enabled", True):
            continue

        match_config = rule.get("match", {})
        field = match_config.get("field", "")
        operator = match_config.get("operator", "")
        value = match_config.get("value", "")

        # Get the field value from finding metadata
        field_value = finding_meta.get(field, "")
        if not field_value:
            continue

        # Apply operator
        if matches(field_value, operator, value):
            return {
                "suppressed": True,
                "rule_id": rule.get("id", "unknown"),
                "reason": rule.get("reason", "Matched suppression rule"),
            }

    return {"suppressed": False, "rule_id": None, "reason": None}


def matches(field_value, operator, rule_value):
    """Evaluate a suppression match condition."""
    try:
        if operator == "equals":
            return field_value == rule_value
        elif operator == "contains":
            return rule_value in field_value
        elif operator == "starts_with":
            return field_value.startswith(rule_value)
        elif operator == "in_cidr":
            # rule_value is a list of CIDR ranges
            cidrs = rule_value if isinstance(rule_value, list) else [rule_value]
            try:
                ip = ipaddress.ip_address(field_value)
                return any(ip in ipaddress.ip_network(cidr) for cidr in cidrs)
            except ValueError:
                return False
        elif operator == "regex":
            import re
            return bool(re.search(rule_value, field_value))
    except Exception as e:
        logger.warning("Suppression match error (op=%s): %s", operator, str(e))

    return False
