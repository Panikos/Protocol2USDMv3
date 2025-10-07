# Windsurf Project Development Rules

**Version:** 1.0  
**Last Updated:** 2025-10-04  
**Purpose:** Codify lessons learned from SOA Convertor vs. Protcol2USDMv3 analysis to ensure consistency, robustness, and maintainability.

---

## Table of Contents
1. [Prompt Engineering Principles](#1-prompt-engineering-principles)
2. [Schema Anchoring](#2-schema-anchoring)
3. [JSON Validation & Defensive Parsing](#3-json-validation--defensive-parsing)
4. [Retry & Error Recovery Strategy](#4-retry--error-recovery-strategy)
5. [Conflict Resolution & Normalization](#5-conflict-resolution--normalization)
6. [Chunk Processing for Large Documents](#6-chunk-processing-for-large-documents)
7. [File Organization & Modularity](#7-file-organization--modularity)
8. [Testing & Quality Assurance](#8-testing--quality-assurance)
9. [Documentation Standards](#9-documentation-standards)
10. [Model Selection & Configuration](#10-model-selection--configuration)

---

## 1. Prompt Engineering Principles

### 1.1 Structure & Clarity
- **Use clear sections** with visual separators (e.g., `════════`) to organize prompt content
- **Start with OBJECTIVE**: Clearly state what the model must do
- **Follow with INPUTS**: List all data sources the model will receive
- **End with OUTPUT RULES**: Explicit, strict instructions on format and constraints

### 1.2 JSON-Only Fences
Always end prompts with explicit, unambiguous instructions:

```
**REQUIRED OUTPUT (JSON ONLY)**
- Return ONE JSON object only.
- No prose, no Markdown, no code fences.
- The string must be directly loadable by json.loads().
```

### 1.3 Positive & Negative Examples
Where possible, show contrast:

```
❌ Bad: "Here is your JSON:\n{ ... }"
✅ Good: { ... }
```

### 1.4 Mini Examples
- Provide **minimal but valid** examples that demonstrate structure, not verbosity
- Keep examples scoped to 20-50 lines
- Ensure examples match the exact schema structure you expect

### 1.5 Entity Mapping & Terminology
- Always include **entity definitions** with:
  - Required vs. optional fields
  - Allowed values (from controlled terminology)
  - Relationship patterns (foreign keys, cross-references)

---

## 2. Schema Anchoring

### 2.1 Core Principle
**Always embed the authoritative schema text in LLM prompts** to reduce structural drift and hallucinated keys.

### 2.2 Implementation
```python
def load_usdm_schema_text(schema_path: str) -> str:
    """
    Load OpenAPI/JSON schema text and compact it for prompting.
    Keep token budget sane: ~3-12k tokens.
    """
    p = Path(schema_path)
    text = p.read_text(encoding="utf-8", errors="replace")
    # Light minification: collapse whitespace
    text = " ".join(text.split())
    return text[:12000]  # Truncate if needed
```

### 2.3 Prompt Integration
Include schema in prompt template:
```
════════════════════════════════════════════════════════════════════
 USDM WRAPPER-INPUT JSON SCHEMA (AUTHORITATIVE)
════════════════════════════════════════════════════════════════════
{usdm_schema_text}
```

### 2.4 Benefits
- **30-50% reduction** in invalid JSON structure errors
- Fewer missing required fields
- Better adherence to nested object patterns

---

## 3. JSON Validation & Defensive Parsing

### 3.1 Three-Layer Defense

#### Layer A: Prompt-Level Fences
```python
PROMPT_ADDENDUM = """
STRICT REMINDER:
- Return ONE JSON object only
- No prose, no markdown, no code fences
- Must parse with json.loads()
"""
```

#### Layer B: Model-Level JSON Mode
```python
# OpenAI
response = client.chat.completions.create(
    model="gpt-4o",
    response_format={"type": "json_object"},  # Force JSON
    messages=[...]
)

# Gemini
model = genai.GenerativeModel(
    "gemini-2.5-pro",
    generation_config={"response_mime_type": "application/json"}
)
```

#### Layer C: Parser with Auto-Repair
```python
def extract_json_str(s: str) -> str:
    """
    Defensive JSON extractor:
    1. Try direct parse (fast path)
    2. Strip code fences and markdown
    3. Extract first {...} block
    4. Fix trailing commas
    5. Validate and return
    """
    import json, re
    
    # Fast path
    try:
        json.loads(s)
        return s
    except:
        pass
    
    # Remove code fences
    s2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", s.strip(), flags=re.MULTILINE)
    
    # Extract JSON block
    m = re.search(r"\{.*\}", s2, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found")
    
    candidate = m.group(0)
    # Fix trailing commas
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    
    # Validate
    json.loads(candidate)
    return candidate
```

### 3.2 Usage Pattern
```python
raw_output = send_text_to_llm(chunk, prompt, model)
try:
    clean_json = extract_json_str(raw_output)
    parsed = json.loads(clean_json)
except Exception as e:
    logger.warning(f"Parse failed: {e}")
    # Trigger retry or skip
```

---

## 4. Retry & Error Recovery Strategy

### 4.1 Guarded Retry Wrapper
```python
def call_with_retry(call_fn, text_chunk, prompt, model_name, max_attempts=2):
    """
    Execute LLM call with automatic retry on parse failure.
    Each retry tightens the prompt.
    """
    last_err = None
    local_prompt = prompt
    
    for attempt in range(max_attempts):
        raw = call_fn(text_chunk, local_prompt, model_name)
        try:
            return extract_json_str(raw)
        except Exception as e:
            last_err = e
            # Tighten instruction
            local_prompt = local_prompt + (
                "\n\nSTRICT REMINDER: Return ONE JSON object only. "
                "No prose or code fences. Ensure it parses with json.loads()."
            )
    
    raise last_err
```

### 4.2 Schema-Guided Retry
When schema validation fails, provide the error to the model:
```python
validation_err = validate_against_schema(parsed_json)
if validation_err:
    retry_prompt = prompt + f"""

VALIDATION ERROR:
{validation_err}

Fix the JSON to satisfy the schema. Return the FULL corrected JSON object.
"""
    raw_output = call_with_retry(send_text_to_llm, chunk, retry_prompt, model, max_attempts=1)
```

### 4.3 Retry Budget
- **Max 2 retries per chunk** (diminishing returns after 2)
- **Log all retry attempts** for debugging
- **Skip chunk after exhausting retries** (don't block pipeline)

---

## 5. Conflict Resolution & Normalization

### 5.1 Naming vs. Timing Rule (CRITICAL)
**Problem:** LLMs often blend visit labels and timing info (e.g., "Visit 1 Week -2")

**Solution:** Enforce separation in prompt:
```
**Naming vs. Timing Rule**
1. Encounter.name and PlannedTimepoint.name MUST be identical and contain ONLY the visit label (e.g., "Visit 1")
2. Put timing info in ONE of these places:
   - PREFERRED: Encounter.timing.windowLabel (+ windowLower/Upper)
   - FALLBACK: PlannedTimepoint.description
3. NEVER repeat timing text in the name field
```

### 5.2 Post-Processing Normalization
```python
def normalize_names_vs_timing(timeline: dict):
    """
    Extract timing patterns from names and move to proper fields.
    """
    import re
    timing_pat = re.compile(r"(Week\s*[-+]?\d+|Day\s*[-+]?\d+|±\s*\d+)", re.IGNORECASE)
    
    for enc in timeline.get("encounters", []):
        name = enc.get("name", "")
        if timing_pat.search(name):
            # Strip timing from name
            clean_name = timing_pat.sub("", name).strip(" -–—:()")
            enc["name"] = clean_name
            # Move to timing.windowLabel
            enc.setdefault("timing", {}).setdefault("windowLabel", name)
    
    # Similar for PlannedTimepoints
    for pt in timeline.get("plannedTimepoints", []):
        name = pt.get("name", "")
        if timing_pat.search(name):
            clean_name = timing_pat.sub("", name).strip(" -–—:()")
            pt["name"] = clean_name
            if not pt.get("description"):
                pt["description"] = name
```

### 5.3 Fallback Behaviors
**In prompts, explicitly state:**
```
**MODELING RULES**
- Do NOT invent assessments, visits, windows, or epochs
- When data is missing, use empty arrays/objects (never null)
- Normalize repeated labels consistently across Encounter + PlannedTimepoint
- Ensure every visit produces exactly ONE Encounter + ONE PlannedTimepoint with matching names
```

**In code:**
```python
def ensure_required_fields(study: dict):
    """Ensure required USDM fields exist with sensible defaults."""
    versions = study.get("versions", []) or study.get("studyVersions", [])
    if not versions:
        study["versions"] = [{}]
        versions = study["versions"]
    
    timeline = versions[0].setdefault("timeline", {})
    
    # Ensure arrays exist
    timeline.setdefault("activities", [])
    timeline.setdefault("plannedTimepoints", [])
    timeline.setdefault("encounters", [])
    
    # Ensure epochs
    if not versions[0].get("epochs"):
        versions[0]["epochs"] = [{"id": "epoch-1", "name": "Main", "position": 1}]
```

---

## 6. Chunk Processing for Large Documents

### 6.1 Chunking Strategy
- **Target chunk size:** 50,000-75,000 characters (fits most model context windows)
- **Split by semantic sections** (not arbitrary byte counts)
- **Preserve section headers** in each chunk for context

```python
def chunk_sections(sections, max_chars=75000):
    """
    Chunk sections while respecting semantic boundaries.
    """
    chunks = []
    current = []
    current_len = 0
    
    for sec in sections:
        if current_len + len(sec) > max_chars and current:
            chunks.append('\n\n'.join(current))
            current = [sec]
            current_len = len(sec)
        else:
            current.append(sec)
            current_len += len(sec)
    
    if current:
        chunks.append('\n\n'.join(current))
    
    return chunks
```

### 6.2 Chunk Merging
- **De-duplicate entities** across chunks by ID and semantic similarity
- **Maintain ID consistency** (reindex all entity IDs after merging)
- **Preserve cross-references** (update foreign keys during reindexing)

```python
def merge_soa_jsons(soa_parts):
    """
    Merge multiple chunk outputs into single USDM object.
    Steps:
    1. Collect all unique entities across chunks
    2. Create ID mappings (old → new)
    3. Rewrite entity IDs and foreign keys
    4. Assemble final timeline
    """
    # Implementation in send_pdf_to_llm.py
    pass
```

### 6.3 Error Handling
- **Log chunk-level failures** but continue processing
- **Require minimum 1 successful chunk** to proceed
- **Report chunk success rate** in final output

---

## 7. File Organization & Modularity

### 7.1 Directory Structure
```
project/
├── main.py                          # Pipeline orchestrator
├── generate_soa_llm_prompt.py       # Prompt generation
├── send_pdf_to_llm.py               # LLM caller + chunking
├── soa_postprocess_consolidated.py  # Normalization + cleanup
├── validate_usdm_schema.py          # Schema validation
├── soa_entity_mapping.json          # Entity definitions (source of truth)
├── USDM OpenAPI schema/             # Versioned schemas
│   └── Wrapper-Input.json
├── output/                          # Per-run timestamped outputs
│   └── [protocol_name]/
│       ├── 1_llm_prompt.txt
│       ├── 5_raw_text_soa.json
│       ├── 10_reconciled_soa.json
│       └── ...
├── tests/                           # Unit & integration tests
├── requirements.txt                 # Dependencies
├── .env                             # API keys (gitignored)
└── WINDSURF_RULES.md                # This file
```

### 7.2 Script Responsibilities

| Script | Single Responsibility |
|--------|----------------------|
| `generate_soa_llm_prompt.py` | Generate prompts from entity mapping + schema |
| `send_pdf_to_llm.py` | Handle I/O, chunking, LLM calls, retries |
| `soa_postprocess_consolidated.py` | Normalize, enrich, repair USDM structure |
| `validate_usdm_schema.py` | Schema validation only |
| `main.py` | Orchestrate pipeline, pass args between scripts |

**Principle:** Each script should have a single, clear purpose. No cross-cutting concerns.

### 7.3 Configuration Files
- **`soa_entity_mapping.json`**: Entity definitions, relationships, allowed values
- **`USDM OpenAPI schema/`**: Official schema files (versioned)
- **`.env`**: API keys and secrets (never committed)
- **`p2u_constants.py`**: Shared constants (USDM_VERSION, etc.)

---

## 8. Testing & Quality Assurance

### 8.1 Test Harness Requirements
```python
# tests/test_pipeline_e2e.py
def test_pipeline_end_to_end():
    """
    Test full pipeline on known-good protocol.
    
    Assertions:
    - Output parses as valid JSON
    - Output validates against USDM schema
    - Expected entities present (activities, timepoints, encounters)
    - No ID collisions
    """
    result = run_pipeline("test_data/CDISC_Pilot_Study.pdf")
    assert result is not None
    
    # Parse test
    parsed = json.loads(result)
    
    # Schema validation test
    errors = validate_usdm_schema(parsed)
    assert len(errors) == 0, f"Schema errors: {errors}"
    
    # Content tests
    timeline = parsed["study"]["versions"][0]["timeline"]
    assert len(timeline["activities"]) > 0
    assert len(timeline["plannedTimepoints"]) > 0
```

### 8.2 CI/CD Integration
- **Run tests on every commit** (GitHub Actions, etc.)
- **Fail build if:**
  - Schema validation fails
  - JSON parse fails
  - Chunk success rate < 80%
- **Track metrics over time:**
  - Parse success rate
  - Schema validation pass rate
  - Chunk processing time

### 8.3 Regression Tests
When a bug is fixed:
1. **Add a test case** for the specific failure
2. **Document the issue** in the test docstring
3. **Keep test in regression suite** permanently

Example:
```python
def test_timing_not_in_name_field():
    """
    Regression test for issue #42: LLM was including "Week -2" in Encounter.name.
    After fix, timing should be in windowLabel only.
    """
    result = extract_soa("test_data/protocol_with_timing.pdf")
    for enc in result["study"]["versions"][0]["timeline"]["encounters"]:
        assert "Week" not in enc["name"]
        assert "Day" not in enc["name"]
```

### 8.4 Logging & Observability
```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Log critical points
logger.info(f"Processing chunk {i+1}/{len(chunks)}")
logger.warning(f"Chunk {i} parse failed: {e}")
logger.error(f"Schema validation failed: {errors}")
```

**Log to file** for post-mortem analysis:
```python
# In main.py
log_path = output_dir / "pipeline.log"
file_handler = logging.FileHandler(log_path)
logger.addHandler(file_handler)
```

---

## 9. Documentation Standards

### 9.1 Inline Documentation
Every prompt engineering decision should be commented:

```python
NAMING_RULE = (
    "**Naming vs. Timing Rule**\n\n"
    # RATIONALE: LLMs frequently blend visit labels with timing info.
    # This rule enforces clean separation, reducing post-processing.
    "For every visit you must output **two linked objects**: "
    "an `Encounter` and a `PlannedTimepoint` (PT).\n\n"
    # ...
)
```

### 9.2 Schema Versioning
When USDM schema updates:
1. **Create new schema file**: `USDM OpenAPI schema/Wrapper-Input-v4.1.0.json`
2. **Update `p2u_constants.py`**: `USDM_VERSION = "4.1.0"`
3. **Document breaking changes** in `CHANGELOG.md`
4. **Re-run full test suite**

### 9.3 Prompt Change Log
Maintain a simple log in prompts:
```python
# generate_soa_llm_prompt.py

# PROMPT CHANGELOG:
# 2025-10-04: Added schema anchoring + JSON-only fences (v1.1)
# 2025-09-15: Added naming vs. timing rule (v1.0)
```

### 9.4 README Maintenance
- **Keep pipeline workflow table up-to-date** with script changes
- **Document all CLI arguments** for each script
- **Include quickstart examples** that actually work
- **Update troubleshooting section** when new issues arise

---

## 10. Model Selection & Configuration

### 10.1 Default Model (from Memory)
- **Primary model**: `gemini-2.5-pro` (user preference)
- **Fallback**: `gpt-4o` (when Gemini unavailable)

### 10.2 Model-Specific Configuration
```python
def get_model_config(model_name):
    """Return model-specific settings."""
    configs = {
        "gemini-2.5-pro": {
            "response_mime_type": "application/json",
            "temperature": 0.0,
            "max_output_tokens": 8192
        },
        "gpt-4o": {
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 16384
        },
        "o3-mini": {
            "response_format": {"type": "json_object"},
            # Note: o3 models don't support temperature parameter
            "max_tokens": 90000
        }
    }
    return configs.get(model_name, configs["gpt-4o"])
```

### 10.3 Token Budget Management
- **Monitor prompt + text length** before each call
- **Truncate intelligently** if exceeding context window (keep schema + recent sections)
- **Log warnings** when truncation occurs

```python
def check_token_budget(prompt, text, model_name, max_tokens=100000):
    """Estimate token count and warn if approaching limit."""
    # Rough estimate: 1 token ≈ 4 chars
    estimated_tokens = (len(prompt) + len(text)) // 4
    
    if estimated_tokens > max_tokens * 0.9:
        logger.warning(
            f"Approaching token limit: {estimated_tokens}/{max_tokens} "
            f"for model {model_name}"
        )
    
    return estimated_tokens
```

---

## Appendix A: Quick Reference Checklist

When building or modifying LLM extraction pipelines, ensure:

- [ ] **Schema embedded in prompt** (Rule 2)
- [ ] **JSON-only fences at end of prompt** (Rule 1.2)
- [ ] **Model JSON mode enabled** (Rule 3.1 Layer B)
- [ ] **Defensive JSON parser implemented** (Rule 3.1 Layer C)
- [ ] **Retry wrapper with max 2 attempts** (Rule 4.1)
- [ ] **Naming vs. timing separation enforced** (Rule 5.1)
- [ ] **Post-processing normalization** (Rule 5.2)
- [ ] **Chunk merging with ID deduplication** (Rule 6.2)
- [ ] **Schema validation before output** (Rule 8)
- [ ] **Tests for regression issues** (Rule 8.3)
- [ ] **Logging at INFO/WARNING/ERROR levels** (Rule 8.4)

---

## Appendix B: Common Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Solution |
|-------------|---------|----------|
| **Prompt without schema** | LLM invents keys, wrong structure | Embed schema text (Rule 2) |
| **No JSON mode + no parser** | Frequent markdown/prose leakage | 3-layer defense (Rule 3.1) |
| **Retry without tightening** | Same prompt = same error | Add stricter reminder each retry (Rule 4.1) |
| **Timing in name fields** | Inconsistent, hard to parse | Naming vs. timing rule (Rule 5.1) |
| **Arbitrary byte chunking** | Splits sentences, breaks context | Semantic section chunking (Rule 6.1) |
| **Monolithic script** | Hard to test, maintain | Single responsibility per script (Rule 7.2) |
| **No tests** | Regressions go unnoticed | E2E + unit + regression tests (Rule 8) |

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-04 | 1.0 | Initial version based on SOA Convertor analysis |

---

## Feedback & Contributions

This is a living document. When you discover new patterns or anti-patterns:
1. **Update this file** with the lesson learned
2. **Add a test case** demonstrating the issue + fix
3. **Update relevant scripts** to follow the new rule
4. **Commit with clear message**: `"RULES: Add guidance on X (resolves Y)"`

**Principle:** Every bug fix or improvement should teach the project something new.
