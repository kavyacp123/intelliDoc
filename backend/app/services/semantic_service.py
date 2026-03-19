"""
Semantic Layer Engine (Service 3 of 8).

Provides a business-logic abstraction over raw SQL.
Metrics and dimensions are loaded from a YAML config file and map
human-readable names to SQL expressions.

This layer ensures the Query Builder uses controlled, pre-defined
SQL expressions instead of arbitrary LLM-generated SQL.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ── Default config path ──
_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "semantic_config.yaml"

# Module-level cache
_config: Optional[Dict[str, Any]] = None


def _load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and cache the semantic configuration from YAML."""
    global _config
    if _config is None:
        config_path = path or _DEFAULT_CONFIG
        if not config_path.exists():
            # Return empty defaults if no config file exists
            _config = {"metrics": {}, "dimensions": {}, "time_column": "date"}
            return _config
        with open(config_path) as f:
            _config = yaml.safe_load(f) or {}
    return _config


def get_metrics() -> Dict[str, str]:
    """
    Return the metrics registry.

    Example:
        {"revenue": "SUM(revenue)", "profit": "SUM(revenue - expense)"}
    """
    return _load_config().get("metrics", {})


def get_dimensions() -> Dict[str, str]:
    """
    Return the dimensions registry.

    Example:
        {"region": "region", "month": "DATE_TRUNC('month', date)"}
    """
    return _load_config().get("dimensions", {})


def get_time_column() -> str:
    """Return the default time column name."""
    return _load_config().get("time_column", "date")


def get_metric_expression(metric_name: str) -> Optional[str]:
    """
    Look up the SQL expression for a named metric.

    Returns None if the metric is not registered.
    """
    return get_metrics().get(metric_name.lower())


def get_dimension_expression(dimension_name: str) -> Optional[str]:
    """
    Look up the SQL expression for a named dimension.

    Returns None if the dimension is not registered.
    """
    return get_dimensions().get(dimension_name.lower())


def get_semantic_summary() -> Dict[str, Any]:
    """
    Return a summary of available metrics and dimensions.

    Sent to the LLM adapter as context for intent generation.
    """
    return {
        "available_metrics": list(get_metrics().keys()),
        "available_dimensions": list(get_dimensions().keys()),
        "time_column": get_time_column(),
    }


def reload_config(path: Optional[Path] = None) -> None:
    """Force reload the semantic config (useful for testing)."""
    global _config
    _config = None
    _load_config(path)
