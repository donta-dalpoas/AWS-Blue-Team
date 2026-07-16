"""
Detection Rules Loader - Reads YAML detection rules at cold start.
"""
import os
import json
import logging

logger = logging.getLogger()

# Try to import yaml; fall back to JSON-based rules if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    logger.info("PyYAML not available - using JSON fallback for detection rules")


def load_detection_rules():
    """Load all detection rules from the detections/ directory."""
    rules = []
    detections_dir = os.path.join(os.path.dirname(__file__), "detections")

    if not os.path.isdir(detections_dir):
        # Try relative to lambda root
        detections_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "detections")

    if not os.path.isdir(detections_dir):
        logger.warning("Detections directory not found")
        return rules

    for filename in os.listdir(detections_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(detections_dir, filename)
            rule = _load_rule_file(filepath)
            if rule:
                rules.append(rule)
        elif filename.endswith(".json"):
            filepath = os.path.join(detections_dir, filename)
            try:
                with open(filepath, "r") as f:
                    rule = json.load(f)
                    rules.append(rule)
            except Exception as e:
                logger.warning("Failed to load rule %s: %s", filename, str(e))

    logger.info("Loaded %d detection rules", len(rules))
    return rules


def _load_rule_file(filepath):
    """Load a single YAML rule file."""
    if not HAS_YAML:
        logger.debug("Skipping YAML file (no yaml module): %s", filepath)
        return None

    try:
        with open(filepath, "r") as f:
            rule = yaml.safe_load(f)
            return rule
    except Exception as e:
        logger.warning("Failed to load rule %s: %s", filepath, str(e))
        return None


def match_rules(finding_meta, rules):
    """Match a finding against all loaded detection rules.

    Returns list of matched rules.
    """
    matched = []

    for rule in rules:
        if _rule_matches(finding_meta, rule):
            matched.append(rule)

    if matched:
        logger.info("Finding matched %d detection rules: %s",
                    len(matched), [r.get("id") for r in matched])

    return matched


def _rule_matches(finding_meta, rule):
    """Check if a finding matches a single detection rule."""
    detection = rule.get("detection", {})

    # Check event_source match
    rule_source = detection.get("event_source", "")
    if rule_source:
        finding_source = finding_meta.get("event_source", "")
        # Map finding sources to rule format
        source_map = {
            "guardduty": "guardduty",
            "securityhub": "securityhub",
        }
        if source_map.get(finding_source, finding_source) != rule_source.replace(".amazonaws.com", ""):
            # Also check if the finding type contains the event source
            if rule_source not in finding_meta.get("finding_type", ""):
                return False

    # Check event_name match
    rule_event_names = detection.get("event_name", [])
    if rule_event_names:
        if isinstance(rule_event_names, str):
            rule_event_names = [rule_event_names]
        finding_type = finding_meta.get("finding_type", "")
        if not any(name.lower() in finding_type.lower() for name in rule_event_names):
            return False

    # Check conditions
    conditions = detection.get("conditions", [])
    for condition in conditions:
        field = condition.get("field", "")
        operator = condition.get("operator", "")
        value = condition.get("value", "")

        # Try to get the field from finding_meta or raw_finding
        field_value = finding_meta.get(field, "")
        if not field_value and "raw_finding" in finding_meta:
            # Dot-notation traversal of raw finding
            field_value = _get_nested(finding_meta["raw_finding"], field)

        if not field_value:
            return False

        if operator == "contains" and value.lower() not in str(field_value).lower():
            return False
        elif operator == "equals" and str(field_value) != str(value):
            return False

    return True


def _get_nested(data, dot_path):
    """Get a nested value from a dict using dot notation."""
    keys = dot_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
        if current is None:
            return None
    return current
