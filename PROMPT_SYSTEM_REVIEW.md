# Comprehensive LLM Prompt System Review
## Review Date: 2025-10-05
## Scope: Generated Prompts, Mapping Files, and Template Infrastructure

---

## Executive Summary

### Current State: ✅ **FUNCTIONAL BUT FRAGMENTED**

The prompt generation system is working correctly for its current purpose, but there's a **parallel template infrastructure** (`prompt_templates.py`) that was built but **never integrated**. This creates:
- ✅ **Working:** Current system generates prompts successfully
- ⚠️ **Technical debt:** Duplicate prompt logic in different places
- ❌ **Underutilized:** Advanced template system exists but unused
- ⚠️ **Scalability:** Hard to maintain consistency across multiple LLM steps

### Recommendation: **CONSOLIDATE & MODERNIZE** (Priority: Medium)
- Current system works fine for immediate needs
- Refactor recommended for long-term maintainability
- Can be done incrementally without breaking changes

---

## Part 1: Generated Prompt Files Analysis

### File 1: `1_llm_prompt.txt` (Minimal SoA-focused)

**Purpose:** Used by Steps 5 (text extraction) and 6 (vision extraction) for SoA timeline extraction

**Structure:**
```
1. OBJECTIVE - Clear task definition ✅
2. USDM WRAPPER-INPUT SCHEMA - Embedded schema reference ✅
3. KEY CONCEPTS AND ENTITY RELATIONSHIPS - Entity explanations ✅
4. NAMING VS. TIMING RULE - Critical naming guidance ✅
5. MINI EXAMPLE - Quick reference ✅
6. EXAMPLE OUTPUT FORMAT - Full valid example ✅
7. DETAILED SCHEMA DEFINITIONS - Field-level specs ✅
8. REQUIRED OUTPUT (JSON ONLY) - Format constraints ✅
9. MODELING RULES - Extraction guidelines ✅
```

**Strengths:**
- ✅ Well-structured with clear sections
- ✅ Follows OpenAI prompt engineering best practices
- ✅ Includes both positive and negative examples
- ✅ Schema-grounded (embeds actual USDM schema)
- ✅ Entity-focused (only 8 core SoA entities)
- ✅ Explicit output format requirements

**Issues Identified:**
1. **❌ CRITICAL: Outdated Example**
   - Line 23-26: Example shows old entity names
   - Example uses `PlannedTimepoint.name = "Day -7"` (WRONG per their own rule!)
   - Should be `name = "Screening Visit"`, `description = "Day -7"`
   - **This contradicts the "Naming vs. Timing Rule" stated earlier**

2. **⚠️ Schema Truncation**
   - Schema is minified/truncated (line 14: `...[3007 bytes truncated]`)
   - May not include all necessary entity definitions
   - Could cause LLM to miss required fields

3. **⚠️ Missing Provenance Guidance**
   - No mention of `p2uProvenance` extension
   - LLMs may or may not include it
   - Inconsistent provenance generation

4. **⚠️ Encounter.type Field**
   - Line 149: Shows `type [Complex Datatype Relationship] (allowed: Visit) (required)`
   - Not explained HOW to format this complex type
   - LLMs may struggle with proper structure

5. **⚠️ PlannedTimepoint Complexity**
   - Lines 184-200: Shows 15+ fields for PlannedTimepoint
   - Many are marked "required" (`value`, `valueLabel`, `relativeFromScheduledInstanceId`, `type`, `relativeToFrom`)
   - No examples showing how to populate these complex temporal fields
   - **This likely causes LLM extraction failures**

### File 2: `1_llm_prompt_full.txt` (Comprehensive)

**Purpose:** "Kept for reference / future use" (not currently used in pipeline)

**Key Differences from Minimal:**
- Includes Study Design Classification section
- Covers ALL entities (not just SoA core)
- More verbose entity definitions

**Status:** ⚠️ **UNUSED - Consider removing or documenting purpose**

### File 3: `1_llm_entity_groups.json` (Entity Catalog)

**Purpose:** Grouped entity definitions from USDM schema

**Structure:**
```json
{
  "soa_core": { ... 8 entities ... },
  "study_design": { ... 5 entities ... },
  "interventions": { ... 4 entities ... },
  "eligibility": { ... 3 entities ... },
  "other": { ... remaining entities ... }
}
```

**Analysis:**
- ✅ Well-organized by functional groups
- ✅ Useful for future template expansion
- ⚠️ Currently only "soa_core" is used in minimal prompt
- ⚠️ Large file (231KB) - most unused

---

## Part 2: Prompt Generation Code Review

### File: `generate_soa_llm_prompt.py`

**Responsibilities:**
1. Load USDM schema
2. Load entity mapping
3. Load prompt example
4. Generate minimal prompt (SoA-focused)
5. Generate full prompt (comprehensive)
6. Generate entity groups catalog

**Code Quality:** ✅ **GOOD**
- Clean, well-structured
- Good separation of concerns
- Proper error handling
- Documented functions

**Issues Identified:**

1. **❌ Example File Inconsistency**
   ```python
   # Line 291-295: Loads soa_prompt_example.json
   example_json_str = example_path.read_text(encoding="utf-8")
   ```
   **Problem:** The example file (checked above) violates the naming rule
   - PlannedTimepoint has `name: "Day -7"` (should be visit name only)
   - This gets embedded in the prompt, teaching the LLM the WRONG pattern

2. **⚠️ Schema Truncation Logic**
   ```python
   # Lines 61-63
   if len(schema_json) > max_tokens * 4:
       schema_json = schema_json[:max_tokens * 4] + "...}}"
   ```
   - Hard truncation could break JSON mid-field
   - Better: Truncate at entity boundaries
   - Or: Use semantic compression

3. **⚠️ Hardcoded Paths**
   ```python
   MAPPING_PATH = "soa_entity_mapping.json"  # Line 16
   SCHEMA_PATH = "USDM OpenAPI schema/USDM_API.json"  # Line 17
   ```
   - Not configurable
   - Could use Path objects or config

4. **⚠️ Minimal Schema Extraction**
   ```python
   # Lines 48-52: Only extracts 3 schema components
   minimal_schema = {
       "Wrapper-Input": components.get("Wrapper-Input", {}),
       "Study-Input": components.get("Study-Input", {}),
       "StudyVersion-Input": components.get("StudyVersion-Input", {}),
   }
   ```
   - Doesn't include Timeline, Epoch, Encounter, Activity, etc.
   - LLM may lack full field definitions for these entities
   - **Recommendation:** Extract all SoA_CORE_ENTITIES schemas

### File: `soa_entity_mapping.json`

**Source:** Generated from USDM OpenAPI schema (6793 lines)

**Quality:** ✅ **AUTHORITATIVE**
- Directly from CDISC USDM spec
- Includes all attributes, relationships, constraints
- Well-structured JSON

**Usage:** ✅ **CORRECT**
- Filtered to SOA_CORE_ENTITIES for minimal prompt
- Full mapping kept for comprehensive prompt

### File: `soa_prompt_example.json`

**Purpose:** One-shot example embedded in prompt

**Status:** ❌ **INCONSISTENT WITH RULES**

**Issues:**
```json
{
  "plannedTimepoints": [
    {
      "id": "pt_1",
      "name": "Day -7",     // ❌ WRONG - Should be visit name
      "encounterId": "enc_1",
      "instanceType": "PlannedTimepoint"
    }
  ]
}
```

**Expected (per Naming Rule):**
```json
{
  "plannedTimepoints": [
    {
      "id": "pt_1",
      "name": "Screening Visit",  // ✅ Visit label only
      "description": "Day -7",     // ✅ Timing in description
      "encounterId": "enc_1",
      "instanceType": "PlannedTimepoint"
    }
  ]
}
```

**Impact:** 🔴 **HIGH**
- LLMs learn from this example
- Directly contradicts stated rules
- Causes inconsistent entity naming
- Post-processing must fix this (technical debt)

---

## Part 3: Parallel Template System (Unused)

### Files:
- `prompt_templates.py` (409 lines)
- `prompts/soa_extraction.yaml` (8673 bytes)
- `tests/test_prompt_templates.py` (19 tests)

**Status:** ✅ **BUILT BUT NEVER INTEGRATED**

**Capabilities:**
- YAML-based template storage
- Variable substitution with defaults
- Metadata tracking (version, task type)
- Template validation
- Registry pattern for caching
- Section-based composition
- Follows OpenAI best practices

**Why It's Not Used:**
1. Built during Phase 4 (multi-model support)
2. Existing prompts already work
3. Integration would require refactoring
4. No immediate business need

**Should We Use It?**
- **Short-term:** No - current system works
- **Long-term:** Yes - benefits outweigh migration cost

**Benefits of Migration:**
1. **Version Control:** YAML files easier to diff/review
2. **Consistency:** Single source of truth for all LLM steps
3. **Testing:** Structured validation
4. **Maintenance:** Easier to update prompts
5. **Scalability:** Ready for new extraction tasks

---

## Part 4: Prompt Usage Across Pipeline

### Current Prompt Architecture:

| Step | Prompt Source | Type | Issues |
|------|---------------|------|--------|
| **Step 5** (Text) | `1_llm_prompt.txt` | Static file + dynamic headers | ⚠️ Example bug |
| **Step 6** (Vision) | `1_llm_prompt.txt` | Static file + dynamic headers | ⚠️ Example bug |
| **Step 9** (Reconcile) | Hardcoded string | Python constant | ⚠️ No versioning |

### Prompt in `send_pdf_to_llm.py`:

```python
def get_llm_prompt(prompt_file, header_structure_file):
    # Load base prompt
    base_prompt = read(prompt_file)
    
    # Add dynamic header hints from Step 4
    header_hints = {...}  # Timepoints + ActivityGroups
    
    return base_prompt + header_prompt_part
```

**Strengths:**
- ✅ Dynamic injection of detected structure
- ✅ Provides LLM with actual IDs from table

**Issues:**
- ⚠️ Header hints format not validated
- ⚠️ No versioning or tracking of prompt changes

### Prompt in `reconcile_soa_llm.py`:

```python
LLM_PROMPT = (
    "You are an expert in clinical trial data curation...\n"
    "Compare and reconcile the two objects...\n"
    ...
)
```

**Issues:**
- ❌ Hardcoded in Python (no external file)
- ❌ No version tracking
- ❌ Difficult to A/B test
- ❌ No structured validation

---

## Part 5: Issues Summary & Impact Analysis

### Critical Issues (Fix Immediately)

| Issue | Impact | Affected Steps | Severity |
|-------|--------|---------------|----------|
| **Example file contradicts naming rule** | LLMs learn wrong pattern | Steps 5, 6 | 🔴 **HIGH** |
| **Missing PlannedTimepoint examples** | LLMs struggle with complex temporal fields | Steps 5, 6 | 🔴 **HIGH** |

### High-Priority Issues (Fix Soon)

| Issue | Impact | Affected Steps | Severity |
|-------|--------|---------------|----------|
| **Schema truncation** | LLM may miss required fields | Steps 5, 6 | 🟠 **MEDIUM** |
| **Encounter.type not explained** | Inconsistent complex type generation | Steps 5, 6 | 🟠 **MEDIUM** |
| **Reconciliation prompt not versioned** | Hard to track what changed | Step 9 | 🟠 **MEDIUM** |

### Medium-Priority Issues (Address in Refactor)

| Issue | Impact | Affected Steps | Severity |
|-------|--------|---------------|----------|
| **Template system unused** | Maintenance burden | All | 🟡 **LOW** |
| **Full prompt unused** | Dead code | None | 🟡 **LOW** |
| **No provenance guidance** | Inconsistent extension usage | Steps 5, 6 | 🟡 **LOW** |

---

## Part 6: Recommendations

### Immediate Actions (This Week)

#### 1. Fix Example File ⏰ **30 minutes**

**File:** `soa_prompt_example.json`

**Change:**
```json
{
  "plannedTimepoints": [
    {
      "id": "pt_1",
      "name": "Screening Visit",        // ✅ Match encounter name
      "description": "Day -7",           // ✅ Timing here
      "encounterId": "enc_1",
      "value": -7,                       // ✅ Numeric value
      "valueLabel": "Day -7",            // ✅ Human-readable
      "relativeFromScheduledInstanceId": "enc_1",  // ✅ Required field
      "type": {"code": "C123", "decode": "Fixed Reference"},  // ✅ Required
      "relativeToFrom": {"code": "C124", "decode": "Start to Start"},  // ✅ Required
      "instanceType": "PlannedTimepoint"
    }
  ]
}
```

**Impact:** Teaches LLM correct pattern, reduces post-processing burden

#### 2. Add PlannedTimepoint Guidance ⏰ **1 hour**

**File:** `generate_soa_llm_prompt.py`

**Add new section to MINIMAL_PROMPT_TEMPLATE:**
```python
PLANNEDTIMEPOINT_GUIDANCE = """
════════════════════════════════════════════════════════════════════
 PLANNEDTIMEPOINT SPECIAL INSTRUCTIONS
════════════════════════════════════════════════════════════════════

PlannedTimepoint is one of the most complex entities. Here's how to populate it:

**Required Fields:**
1. `value` (number): Numeric offset (e.g., -7, 0, 14)
2. `valueLabel` (string): Human-readable (e.g., "Day -7", "Week 2")
3. `relativeFromScheduledInstanceId` (string): Usually the encounterId
4. `type`: Code object with:
   - For scheduled timepoints: {"code": "C99999", "decode": "Fixed Reference"}
   - For relative timepoints: {"code": "C99999", "decode": "After"} or "Before"
5. `relativeToFrom`: Code object (usually {"code": "C99999", "decode": "Start to Start"})

**Example:**
```json
{
  "id": "pt_week2",
  "name": "Visit 3",
  "description": "Week 2 ±3 days",
  "encounterId": "enc_3",
  "value": 14,
  "valueLabel": "Week 2",
  "windowLabel": "±3 days",
  "windowLower": -3,
  "windowUpper": 3,
  "relativeFromScheduledInstanceId": "enc_3",
  "type": {"code": "C99999", "decode": "Fixed Reference"},
  "relativeToFrom": {"code": "C99999", "decode": "Start to Start"},
  "instanceType": "PlannedTimepoint"
}
```

**When to use windowLabel:**
If the protocol specifies a visit window (e.g., "Week 4 ±7 days"), put the window in both:
- `windowLabel`: "±7 days" (human-readable)
- `windowLower`: -7, `windowUpper`: 7 (numeric bounds)
"""
```

#### 3. Expand Schema Embedding ⏰ **1 hour**

**File:** `generate_soa_llm_prompt.py` (line 48)

**Change:**
```python
# Before: Only 3 components
minimal_schema = {
    "Wrapper-Input": components.get("Wrapper-Input", {}),
    "Study-Input": components.get("Study-Input", {}),
    "StudyVersion-Input": components.get("StudyVersion-Input", {}),
}

# After: Include all SoA entities
SCHEMA_ENTITIES_TO_INCLUDE = [
    "Wrapper-Input",
    "Study-Input",
    "StudyVersion-Input",
    "Timeline-Input",           # NEW
    "Epoch-Input",              # NEW
    "Encounter-Input",          # NEW
    "PlannedTimepoint-Input",   # NEW
    "Activity-Input",           # NEW
    "ActivityTimepoint-Input",  # NEW
    "ActivityGroup-Input",      # NEW
]

minimal_schema = {
    name: components.get(name, {})
    for name in SCHEMA_ENTITIES_TO_INCLUDE
}
```

**Impact:** LLM gets full field definitions, reduces hallucination

### Short-Term Actions (Next Sprint)

#### 4. Version Reconciliation Prompt ⏰ **2 hours**

**Current:** Hardcoded in `reconcile_soa_llm.py`

**Change:**
1. Create `prompts/reconciliation.txt`
2. Add version header (e.g., `# v1.1 - 2025-10-05`)
3. Load from file instead of constant
4. Track changes in CHANGELOG

**Benefits:**
- Easier A/B testing
- Git-trackable changes
- Consistent with other prompts

#### 5. Add Provenance Guidance ⏰ **30 minutes**

**File:** `generate_soa_llm_prompt.py`

**Add to MINIMAL_PROMPT_TEMPLATE:**
```python
PROVENANCE_GUIDANCE = """
════════════════════════════════════════════════════════════════════
 PROVENANCE EXTENSION (OPTIONAL)
════════════════════════════════════════════════════════════════════

You MAY include a top-level `p2uProvenance` key to track entity origins:

```json
{
  "study": { ... },
  "usdmVersion": "4.0.0",
  "p2uProvenance": {
    "plannedTimepoints": {
      "pt_1": "extracted",
      "pt_2": "extracted"
    },
    "activities": {
      "act_1": "extracted",
      "act_2": "extracted"
    },
    "encounters": {
      "enc_1": "extracted"
    }
  }
}
```

**Note:** This is a custom extension. Downstream processing will split it into a separate file.
"""
```

### Medium-Term Actions (Next Quarter)

#### 6. Migrate to Template System ⏰ **1 week**

**Rationale:**
- Better maintainability
- Consistent versioning
- Easier testing
- Ready for expansion

**Migration Plan:**
1. **Week 1:** Convert existing prompts to YAML
   - `prompts/soa_extraction_text.yaml` (Step 5)
   - `prompts/soa_extraction_vision.yaml` (Step 6)
   - `prompts/reconciliation.yaml` (Step 9)

2. **Week 2:** Update pipeline to use PromptTemplate
   - Refactor `send_pdf_to_llm.py`
   - Refactor `reconcile_soa_llm.py`
   - Add integration tests

3. **Week 3:** Add new capabilities
   - Prompt A/B testing framework
   - Prompt versioning in output files
   - Automated prompt validation

4. **Week 4:** Documentation & cleanup
   - Update README
   - Archive old prompt generation code
   - Document best practices

**Benefits:**
- Single source of truth for all prompts
- YAML diffs in PR reviews
- Automated validation
- Ready for future extraction tasks

#### 7. Create Prompt Performance Dashboard ⏰ **3 days**

**Goal:** Track which prompts produce best results

**Metrics to track:**
- Schema validation pass rate
- Entity extraction completeness
- Linkage error rate
- Post-processing fixes needed
- Model + prompt combinations

**Implementation:**
- Log prompt version with each extraction
- Store metrics in SQLite
- Simple dashboard to view trends

---

## Part 7: Testing Recommendations

### Current Test Coverage

**Prompt System Tests:**
- ✅ `test_prompt_templates.py` - 19 tests for template infrastructure
- ❌ **NO tests for actual prompt quality**
- ❌ **NO tests for example validity**

### Recommended Tests

#### Test 1: Example Validation
```python
def test_prompt_example_follows_naming_rule():
    """Ensure example in prompt follows the naming vs timing rule."""
    example = json.load(open('soa_prompt_example.json'))
    
    # Check PlannedTimepoints don't have timing in name
    for pt in example['study']['versions'][0]['timeline']['plannedTimepoints']:
        name = pt.get('name', '')
        # Name should NOT contain timing keywords
        assert not any(word in name.lower() for word in ['day', 'week', 'month', 'year', '±'])
        # Should have description or encounter with timing
        assert pt.get('description') or pt.get('encounterId')
```

#### Test 2: Schema Completeness
```python
def test_embedded_schema_includes_core_entities():
    """Ensure embedded schema includes all SoA core entities."""
    # Generate prompt
    prompt = generate_prompt()
    
    # Extract embedded schema
    schema_match = re.search(r'USDM WRAPPER-INPUT SCHEMA.*?{(.+?)}', prompt, re.DOTALL)
    schema = json.loads('{' + schema_match.group(1) + '}')
    
    # Check all core entities present
    required_entities = [
        'Timeline-Input',
        'Epoch-Input',
        'Encounter-Input',
        'PlannedTimepoint-Input',
        'Activity-Input',
        'ActivityTimepoint-Input',
    ]
    for entity in required_entities:
        assert entity in schema, f"Missing {entity} in embedded schema"
```

#### Test 3: Prompt Consistency
```python
def test_prompts_consistent_across_steps():
    """Ensure text and vision prompts are consistent."""
    text_prompt = load_prompt('1_llm_prompt.txt')
    # Vision uses same prompt currently
    
    # Check for critical sections
    assert 'NAMING VS. TIMING RULE' in text_prompt
    assert 'EXAMPLE OUTPUT FORMAT' in text_prompt
    assert 'MODELING RULES' in text_prompt
```

---

## Appendix A: File Inventory

### Generated Files (Per Study)
```
output/<StudyName>/
├── 1_llm_prompt.txt                 [Step 1] Minimal SoA prompt
├── 1_llm_prompt_full.txt            [Step 1] Comprehensive prompt (unused)
└── 1_llm_entity_groups.json         [Step 1] Entity catalog (mostly unused)
```

### Source Files (Repository)
```
Root/
├── generate_soa_llm_prompt.py       Main prompt generator
├── soa_entity_mapping.json          Entity definitions (from USDM schema)
├── soa_prompt_example.json          One-shot example (HAS BUGS)
├── prompt_templates.py              Template infrastructure (unused)
├── prompts/
│   └── soa_extraction.yaml          YAML template (unused)
└── tests/
    └── test_prompt_templates.py     Template tests
```

### Schema Files
```
USDM OpenAPI schema/
└── USDM_API.json                    CDISC USDM v4.0 specification
```

---

## Appendix B: Prompt Evolution History

### Version 1.0 (Initial)
- Basic entity extraction
- Minimal examples
- No schema embedding

### Version 1.1 (Current)
- Added "Naming vs. Timing Rule"
- Schema anchoring (Wrapper-Input embedded)
- JSON-only output fences
- Filtered to SOA_CORE_ENTITIES

### Future v2.0 (Proposed)
- Fix example file
- Add PlannedTimepoint guidance
- Full schema for core entities
- Provenance guidance
- Migrate to YAML templates

---

## Appendix C: Prompt Best Practices Checklist

Based on OpenAI Prompt Engineering Guide:

| Principle | Current Status | Notes |
|-----------|---------------|-------|
| **Clear instructions** | ✅ **GOOD** | Objective section clear |
| **Provide reference text** | ⚠️ **PARTIAL** | Schema embedded but truncated |
| **Split complex tasks** | ✅ **GOOD** | Separate steps for different entities |
| **Give time to "think"** | ❌ **NO** | No chain-of-thought prompting |
| **Use external tools** | ✅ **GOOD** | Schema validation post-extraction |
| **Test systematically** | ❌ **NO** | No prompt quality tests |
| **Positive examples** | ✅ **GOOD** | Includes valid example |
| **Negative examples** | ✅ **GOOD** | Shows wrong vs right format |
| **Output format explicit** | ✅ **GOOD** | JSON-only, no markdown |
| **Boundary conditions** | ✅ **GOOD** | "Do not invent" rules |

**Score: 7/10** ⭐⭐⭐⭐⭐⭐⭐☆☆☆

---

## Final Verdict

### Current System: ✅ **FUNCTIONAL - MINOR ISSUES**

The prompt generation system is well-designed and produces good results, but has some quality issues that should be addressed:

**Must Fix:**
- Example file contradicts stated rules
- Missing complex entity examples

**Should Fix:**
- Schema truncation
- Reconciliation prompt versioning
- Template system integration

**Priority Order:**
1. 🔴 Fix example file (30 min)
2. 🔴 Add PlannedTimepoint guidance (1 hour)
3. 🟠 Expand schema embedding (1 hour)
4. 🟠 Version reconciliation prompt (2 hours)
5. 🟡 Migrate to template system (1 week)

**Estimated Total Effort:** ~1-2 weeks for complete modernization

---

**Review Completed:** 2025-10-05  
**Reviewed By:** AI Assistant (Cascade)  
**Next Review:** After implementing critical fixes
