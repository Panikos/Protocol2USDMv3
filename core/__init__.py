"""
Core utilities for Protocol2USDM pipeline.

This module consolidates shared functionality to eliminate duplication:
- LLM client management
- JSON parsing and cleaning
- Provenance tracking
- Constants and configuration
"""

from .llm_client import get_llm_client, LLMConfig, LLMResponse, get_default_model
from .json_utils import (
    parse_llm_json,
    extract_json_str,
    standardize_ids,
    clean_json_response,
    get_timeline,
    make_hashable,
)
from .provenance import ProvenanceTracker, ProvenanceSource
from .constants import (
    USDM_VERSION,
    SYSTEM_NAME,
    SYSTEM_VERSION,
    DEFAULT_MODEL,
    REASONING_MODELS,
)

__all__ = [
    # LLM Client
    "get_llm_client",
    "get_default_model",
    "LLMConfig",
    "LLMResponse",
    # JSON Utilities
    "parse_llm_json",
    "extract_json_str",
    "standardize_ids",
    "clean_json_response",
    "get_timeline",
    "make_hashable",
    # Provenance
    "ProvenanceTracker",
    "ProvenanceSource",
    # Constants
    "USDM_VERSION",
    "SYSTEM_NAME",
    "SYSTEM_VERSION",
    "DEFAULT_MODEL",
    "REASONING_MODELS",
]
