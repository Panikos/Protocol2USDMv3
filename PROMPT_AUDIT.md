# LLM Prompt Audit - Pipeline-Wide Analysis

**Date:** 2025-10-05  
**Status:** ⚠️ PARTIAL MIGRATION - Only reconciliation prompt migrated to YAML

---

## Current State Summary

### ✅ Migrated to YAML Templates
1. **Reconciliation Prompt** (`reconcile_soa_llm.py`)
   - Template: `prompts/soa_reconciliation.yaml` (v2.0)
   - Status: ✅ Fully integrated with fallback
   - Both Gemini & OpenAI: ✅ Uses same template

### ❌ NOT Yet Migrated (Hardcoded)

2. **Text Extraction Prompt** (`send_pdf_to_llm.py`)
   - **Location:** Lines 102-103
   - **Current:** Hardcoded system message
   - **Template exists:** `prompts/soa_extraction.yaml` ✅ (but NOT USED)
   - **Both Gemini & OpenAI:** ❌ Separate hardcoded strings
   - **Generated prompt:** Loaded from file (`1_llm_prompt.txt`)

3. **Vision Extraction Prompt** (`vision_extract_soa.py`)
   - **Location:** Lines 90-93 (Gemini), 135-138 (OpenAI)
   - **Current:** Hardcoded system messages (DIFFERENT for each provider)
   - **Template:** ❌ Does not exist
   - **Both Gemini & OpenAI:** ❌ Completely separate prompts
   - **Base prompt:** Loaded from file

4. **Find SoA Pages Prompt** (`find_soa_pages.py`)
   - **Location:** Lines 58-82
   - **Current:** Hardcoded `textwrap.dedent` blocks
   - **Template:** ❌ Does not exist
   - **Both Gemini & OpenAI:** ✅ Uses same hardcoded prompt

5. **Legacy Text Extraction** (`send_pdf_to_openai.py`)
   - **Location:** Line 77
   - **Current:** Hardcoded system message
   - **Template:** ❌ Does not exist
   - **Status:** ⚠️ Legacy file (may not be used)

6. **Epoch/Encounter Mapping** (`map_epochs_encounters_llm.py`)
   - **Location:** Contains LLM calls
   - **Template:** ❌ Does not exist

7. **Structure Analysis** (`analyze_soa_structure.py`)
   - **Location:** Contains LLM calls
   - **Template:** ❌ Does not exist

---

## Key Issues Identified

### Issue 1: Inconsistent Prompts Across Providers
**Problem:** Gemini and OpenAI often have DIFFERENT prompts for the same task.

**Example - Vision Extraction:**
```python
# Gemini (vision_extract_soa.py:90)
"You are an expert medical writer specializing in authoring clinical trial protocols..."

# OpenAI (vision_extract_soa.py:135)  
"You are an expert medical writer specializing in authoring clinical trial protocols..."
# Similar but SEPARATE implementations
```

**Impact:**
- Difficult to optimize prompts (must change in multiple places)
- No way to A/B test
- Inconsistent behavior between models

### Issue 2: Template Exists But Not Used
**Problem:** `prompts/soa_extraction.yaml` exists but `send_pdf_to_llm.py` doesn't use it.

**Current workflow:**
1. `generate_soa_llm_prompt.py` creates text file (`1_llm_prompt.txt`)
2. `send_pdf_to_llm.py` loads that text file
3. Adds hardcoded system message
4. YAML template is ignored

**Should be:**
1. Load `prompts/soa_extraction.yaml`
2. Render with variables
3. Use for both Gemini and OpenAI

### Issue 3: No Version Tracking
**Problem:** Only reconciliation prompt has version tracking.

**Missing for:**
- Text extraction prompts
- Vision extraction prompts
- SoA page finding prompts
- All other LLM steps

**Impact:**
- Can't track which prompt version produced which output
- Can't A/B test different versions
- Can't revert to previous versions easily

---

## Migration Roadmap

### Phase 1: Create Missing Templates (HIGH PRIORITY)

#### 1.1 Vision Extraction Template
```yaml
# prompts/vision_soa_extraction.yaml
metadata:
  name: vision_soa_extraction
  version: 2.0
  task_type: vision_extraction
  
system_prompt: |
  You are an expert medical writer specializing in clinical trial protocols.
  Analyze the provided SoA table image(s) and extract contents into structured JSON.
  ...
```

#### 1.2 Text Extraction Migration
- Migrate from `1_llm_prompt.txt` generation to direct YAML usage
- Use existing `prompts/soa_extraction.yaml`
- Remove hardcoded system messages

#### 1.3 SoA Page Finding Template
```yaml
# prompts/find_soa_pages.yaml
metadata:
  name: find_soa_pages
  version: 2.0
  
system_prompt: |
  You are an expert document analysis assistant...
```

### Phase 2: Integrate Templates (CRITICAL)

#### 2.1 Update `vision_extract_soa.py`
```python
# Replace hardcoded prompts with:
from prompt_templates import PromptTemplate

template = PromptTemplate.load("vision_soa_extraction", "prompts")
messages = template.render(
    base_prompt=base_prompt,
    header_structure=header_structure
)
```

#### 2.2 Update `send_pdf_to_llm.py`
```python
# Replace file loading + hardcoded system message with:
from prompt_templates import PromptTemplate

template = PromptTemplate.load("soa_extraction", "prompts")
messages = template.render(
    usdm_schema_text=schema,
    entity_instructions=instructions,
    protocol_text=text
)
```

#### 2.3 Update `find_soa_pages.py`
```python
# Replace textwrap.dedent blocks with:
template = PromptTemplate.load("find_soa_pages", "prompts")
```

### Phase 3: Provider Abstraction (RECOMMENDED)

**Current pattern (duplicated):**
```python
# Gemini code
if 'gemini' in model:
    response = gemini_client.generate_content([system_prompt, user_prompt])
    
# OpenAI code
else:
    messages = [{"role": "system", "content": system_prompt}, ...]
    response = openai_client.chat.completions.create(messages=messages)
```

**Better pattern (unified):**
```python
from llm_providers import LLMProviderFactory

provider = LLMProviderFactory.create(model)
response = provider.generate(
    template="vision_soa_extraction",
    variables={...}
)
```

---

## Detailed File Analysis

### 1. `reconcile_soa_llm.py` ✅
**Status:** COMPLETE
- Template: `prompts/soa_reconciliation.yaml`
- Version: 2.0
- Fallback: v1.0 hardcoded (maintained)
- Provider abstraction: ❌ Still separate Gemini/OpenAI code

### 2. `send_pdf_to_llm.py` ⚠️
**Status:** PARTIAL
- Loads base prompt from file: ✅
- System message: ❌ Hardcoded line 102
- Template exists but not used: `prompts/soa_extraction.yaml`
- Provider abstraction: ✅ Can use llm_providers.py

**Hardcoded prompt:**
```python
{"role": "system", "content": "You are an expert medical writer..."}
```

**Should use:**
```python
template = PromptTemplate.load("soa_extraction")
messages = template.render(protocol_text=text, ...)
```

### 3. `vision_extract_soa.py` ❌
**Status:** NEEDS WORK
- Gemini prompt: Hardcoded lines 90-93
- OpenAI prompt: Hardcoded lines 135-138
- Template: ❌ Does not exist
- Provider abstraction: ❌ Completely separate code paths

**Issues:**
- Prompts are SIMILAR but not identical
- No version tracking
- Changes require editing multiple locations
- Can't A/B test

### 4. `find_soa_pages.py` ⚠️
**Status:** PARTIALLY UNIFIED
- Prompt: Hardcoded lines 58-82
- Both providers: ✅ Use same prompt
- Template: ❌ Does not exist
- Version tracking: ❌ None

**Good:** At least uses same prompt for both providers  
**Bad:** Still hardcoded, no versioning

### 5. `generate_soa_llm_prompt.py` 🤔
**Status:** HYBRID APPROACH
- Uses template strings: `MINIMAL_PROMPT_TEMPLATE`
- Generates text file: `1_llm_prompt.txt`
- Not YAML-based
- Good: Single source of truth
- Bad: Not using prompt_templates.py system

**Question:** Should this migrate to YAML or is file generation OK?

### 6. Other Files
- `send_pdf_to_openai.py` - ⚠️ Legacy, may not be used
- `map_epochs_encounters_llm.py` - ❌ Contains LLM calls, no template
- `analyze_soa_structure.py` - ❌ Contains LLM calls, no template

---

## Answers to Your Questions

### Q1: Are all prompts aligned to YAML template approach?
**Answer:** ❌ **NO** - Only reconciliation prompt is fully migrated.

**Breakdown:**
- ✅ Reconciliation: YAML template (1/8)
- ⚠️ Text extraction: Template exists but not used
- ❌ Vision extraction: Hardcoded
- ❌ SoA page finding: Hardcoded
- ❌ Other LLM steps: Hardcoded

### Q2: Are all prompts for Gemini and OpenAI abstracted?
**Answer:** ❌ **NO** - Most scripts have separate code paths.

**Breakdown:**
- ✅ `send_pdf_to_llm.py`: Can use provider abstraction (but doesn't always)
- ❌ `vision_extract_soa.py`: Completely separate Gemini/OpenAI blocks
- ❌ `reconcile_soa_llm.py`: Template unified, but calling code separate
- ⚠️ `find_soa_pages.py`: Same prompt, but separate API calls

### Q3: Can we optimize and benchmark them?
**Answer:** ⚠️ **PARTIALLY** - Difficult due to fragmentation.

**Challenges:**
1. **Inconsistent implementation** - Changes must be made in multiple places
2. **No version tracking** - Can't compare prompt v1.0 vs v2.0 performance
3. **Provider-specific code** - Hard to ensure consistent behavior
4. **Mixed approaches** - Some use templates, some use files, some hardcoded

**What works:**
- Reconciliation prompt: ✅ Can optimize and version track
- Generated prompts: ⚠️ Centralized but not YAML-based

**What doesn't work:**
- Vision extraction: ❌ Must change in 2+ places
- No logging of which prompt version was used
- No easy way to A/B test

---

## Recommended Action Plan

### Immediate (This Session)
1. **Create vision extraction template** - `prompts/vision_soa_extraction.yaml`
2. **Integrate into `vision_extract_soa.py`** - Remove hardcoded prompts
3. **Create SoA page finding template** - `prompts/find_soa_pages.yaml`
4. **Integrate into `find_soa_pages.py`**

### Short Term (Next Session)
5. **Migrate `send_pdf_to_llm.py`** - Use `soa_extraction.yaml` properly
6. **Add provider abstraction** - Use `llm_providers.py` everywhere
7. **Version tracking** - Log which prompt version was used in each step

### Medium Term (Future)
8. **Decide on `generate_soa_llm_prompt.py`** - Migrate to YAML or keep hybrid?
9. **Create templates for remaining LLM steps** - Epoch mapping, structure analysis
10. **Benchmarking framework** - Track metrics by prompt version

---

## Migration Checklist

- [ ] Create `prompts/vision_soa_extraction.yaml`
- [ ] Update `vision_extract_soa.py` to use template
- [ ] Create `prompts/find_soa_pages.yaml`
- [ ] Update `find_soa_pages.py` to use template
- [ ] Update `send_pdf_to_llm.py` to use `soa_extraction.yaml`
- [ ] Add provider abstraction to `vision_extract_soa.py`
- [ ] Add provider abstraction to `reconcile_soa_llm.py`
- [ ] Add prompt version logging to all steps
- [ ] Create templates for remaining LLM steps
- [ ] Update tests to validate new templates
- [ ] Document new template system usage

---

## Conclusion

**Current Status: 🟡 PARTIAL MIGRATION**

Only 1 out of ~8 LLM prompts is fully migrated to the YAML template system. The reconciliation prompt demonstrates the approach works well, but the rest of the pipeline still uses hardcoded prompts with separate implementations for Gemini and OpenAI.

**To achieve full alignment:**
- Need to create 5-7 more YAML templates
- Need to refactor 6+ Python files
- Need to add provider abstraction layer
- Estimated effort: 4-6 hours

**Benefits of completing migration:**
- Single source of truth for each prompt
- Easy optimization and A/B testing
- Version tracking and rollback capability
- Consistent behavior across models
- Simplified maintenance
