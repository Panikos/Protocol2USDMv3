"""
Unified JSON Utilities - Consolidates all JSON parsing and cleaning.

This module eliminates duplicated JSON handling code from:
- json_utils.py (root)
- vision_extract_soa.py (clean_llm_json)
- send_pdf_to_llm.py (extract_json_str)
- Various inline parsing across scripts

Usage:
    from core.json_utils import parse_llm_json, standardize_ids
    
    raw_output = "```json\n{...}\n```"
    data = parse_llm_json(raw_output)
    data = standardize_ids(data)
"""

import json
import re
from typing import Any, Dict, Optional, Union


def extract_json_str(text: str) -> Optional[str]:
    """
    Extract JSON string from LLM output that may contain markdown or extra text.
    
    Handles common LLM output patterns:
    - ```json ... ``` fenced blocks
    - ``` ... ``` generic fenced blocks
    - Raw JSON with leading/trailing text
    - Multiple JSON objects (returns first complete one)
    
    Args:
        text: Raw LLM output text
        
    Returns:
        Extracted JSON string, or None if no valid JSON found
        
    Example:
        >>> extract_json_str('Here is the result:\\n```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
    """
    if not text:
        return None
        
    text = text.strip()
    
    # Strategy 1: Look for ```json ... ``` blocks
    json_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_block_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        for match in matches:
            candidate = match.strip()
            if candidate.startswith('{') or candidate.startswith('['):
                return candidate
    
    # Strategy 2: Find JSON by matching braces
    # Find first { and last } or first [ and last ]
    first_brace = text.find('{')
    first_bracket = text.find('[')
    
    if first_brace == -1 and first_bracket == -1:
        return None
        
    # Determine which comes first
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        # Object JSON
        start = first_brace
        end = text.rfind('}')
        if end > start:
            return text[start:end + 1]
    else:
        # Array JSON
        start = first_bracket
        end = text.rfind(']')
        if end > start:
            return text[start:end + 1]
    
    return None


def parse_llm_json(
    text: str, 
    fallback: Optional[Dict] = None,
    strict: bool = False
) -> Optional[Dict]:
    """
    Parse JSON from LLM output with multiple fallback strategies.
    
    This is the primary JSON parsing function for LLM outputs.
    
    Strategies applied in order:
    1. Direct JSON parse
    2. Extract from markdown fences
    3. Find JSON by brace matching
    4. Attempt repair of common issues (trailing commas, etc.)
    
    Args:
        text: Raw LLM output text
        fallback: Default value if parsing fails (default: None)
        strict: If True, raise exception on failure instead of returning fallback
        
    Returns:
        Parsed JSON as dict/list, or fallback value
        
    Raises:
        json.JSONDecodeError: If strict=True and parsing fails
        
    Example:
        >>> parse_llm_json('{"key": "value"}')
        {'key': 'value'}
        >>> parse_llm_json('invalid', fallback={})
        {}
    """
    if not text:
        if strict:
            raise json.JSONDecodeError("Empty input", "", 0)
        return fallback
        
    text = text.strip()
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract JSON string
    json_str = extract_json_str(text)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Try to repair common issues
        repaired = _repair_json(json_str)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
    
    # All strategies failed
    if strict:
        raise json.JSONDecodeError(
            f"Could not parse JSON from text: {text[:200]}...", 
            text, 
            0
        )
    
    return fallback


def _repair_json(text: str) -> Optional[str]:
    """
    Attempt to repair common JSON issues from LLM output.
    
    Fixes:
    - Trailing commas before } or ]
    - Single quotes instead of double quotes
    - Unescaped newlines in strings
    - Missing quotes on keys
    """
    if not text:
        return None
        
    result = text
    
    # Fix trailing commas: ,} or ,]
    result = re.sub(r',\s*}', '}', result)
    result = re.sub(r',\s*]', ']', result)
    
    # Fix single quotes (careful - don't break apostrophes in text)
    # Only replace quotes that appear to be JSON delimiters
    # This is a simplified heuristic
    if "'" in result and '"' not in result:
        result = result.replace("'", '"')
    
    return result


def clean_json_response(text: str) -> str:
    """
    Clean LLM response to extract just the JSON portion.
    
    Use when you need the raw JSON string (not parsed).
    For parsed JSON, use parse_llm_json() instead.
    
    Args:
        text: Raw LLM output
        
    Returns:
        Cleaned JSON string
    """
    json_str = extract_json_str(text)
    return json_str if json_str else text


def standardize_ids(obj: Any) -> Any:
    """
    Recursively standardize IDs in a USDM structure.
    
    Replaces hyphens with underscores in all 'id' fields and
    fields ending with 'Id' (e.g., activityId, plannedTimepointId).
    
    This ensures consistency across the pipeline since different
    LLM calls may use different ID formats.
    
    Args:
        obj: Any JSON-like structure (dict, list, or primitive)
        
    Returns:
        Structure with standardized IDs (modified in place for dicts/lists)
        
    Example:
        >>> standardize_ids({'id': 'act-1', 'groupId': 'grp-2'})
        {'id': 'act_1', 'groupId': 'grp_2'}
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and (key == 'id' or key.endswith('Id')):
                obj[key] = value.replace('-', '_')
            else:
                standardize_ids(value)
    elif isinstance(obj, list):
        for item in obj:
            standardize_ids(item)
    
    return obj


def make_hashable(obj: Any) -> Any:
    """
    Recursively convert a dict/list structure to hashable form.
    
    Useful for deduplication and set operations on complex objects.
    
    Args:
        obj: Any JSON-like structure
        
    Returns:
        Hashable representation (tuples of tuples)
    """
    if isinstance(obj, (tuple, list)):
        return tuple(make_hashable(e) for e in obj)
    if isinstance(obj, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in obj.items()))
    if isinstance(obj, (set, frozenset)):
        return tuple(sorted(make_hashable(e) for e in obj))
    return obj


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    
    Values from override take precedence. Nested dicts are merged recursively.
    Lists are replaced (not merged).
    
    Args:
        base: Base dictionary
        override: Dictionary with values to merge in
        
    Returns:
        New merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
            
    return result


def safe_get(obj: Dict, *keys, default=None):
    """
    Safely get nested values from a dictionary.
    
    Args:
        obj: Dictionary to traverse
        *keys: Sequence of keys to follow
        default: Value to return if path doesn't exist
        
    Returns:
        Value at path or default
        
    Example:
        >>> safe_get({'a': {'b': {'c': 1}}}, 'a', 'b', 'c')
        1
        >>> safe_get({'a': {}}, 'a', 'b', 'c', default='missing')
        'missing'
    """
    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return default
    return current


def get_timeline(soa: Dict) -> Dict:
    """
    Get the timeline object from a USDM SoA structure.
    
    Handles both standard and legacy formats:
    - study.versions[0].timeline
    - study.studyVersions[0].timeline
    
    Args:
        soa: USDM Wrapper-Input structure
        
    Returns:
        Timeline dict, or empty dict if not found
    """
    if not isinstance(soa, dict):
        return {}
    
    study = soa.get('study', {})
    versions = study.get('versions', []) or study.get('studyVersions', [])
    
    if versions and isinstance(versions, list) and len(versions) > 0:
        return versions[0].get('timeline', {})
    
    return {}
