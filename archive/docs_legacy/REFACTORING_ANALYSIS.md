# Protocol2USDM v3 - Codebase Refactoring Analysis

**Date**: November 2025  
**Purpose**: Comprehensive analysis of codebase bloat and proposed modular refactoring

---

## PROGRESS UPDATE (November 26, 2025)

### Completed Work

#### Phase 1: Core Module Consolidation ✅

Created `core/` module with consolidated utilities:

| File | Purpose | Eliminates Duplication In |
|------|---------|---------------------------|
| `core/__init__.py` | Module exports | - |
| `core/llm_client.py` | Unified LLM client management | 5+ files |
| `core/json_utils.py` | JSON parsing, cleaning, standardization | 4+ files |
| `core/provenance.py` | Provenance tracking | 3+ files |
| `core/constants.py` | Centralized constants | All files |
| `core/usdm_types.py` | Typed dataclasses for USDM entities | - |

Updated backward compatibility wrappers:
- `json_utils.py` → imports from `core.json_utils`
- `p2u_constants.py` → imports from `core.constants`

#### Phase 2: New Extraction Module ✅

Created `extraction/` module with clean architecture:

| File | Purpose | Replaces |
|------|---------|----------|
| `extraction/soa_finder.py` | Heuristic + LLM page detection | find_soa_pages.py |
| `extraction/header_analyzer.py` | Vision-based STRUCTURE extraction | Complex vision extraction |
| `extraction/text_extractor.py` | Text-based DATA extraction | send_pdf_to_llm complexity |
| `extraction/validator.py` | Vision validates text extraction | reconcile_soa_llm complexity |
| `extraction/pipeline.py` | Simple orchestrator | main.py complexity |

New entry point:
- `main_v2.py` - Simplified pipeline using new modules (with `--view` flag for Streamlit)

#### Phase 3: Update Existing Scripts to Use Core Imports ✅

Updated scripts to use `core/` module imports:
- `send_pdf_to_llm.py` - Now uses `core.USDM_VERSION`, `core.extract_json_str`
- `vision_extract_soa.py` - Now uses `core.extract_json_str`, `core.llm_client`
- `reconcile_soa_llm.py` - Now uses `core.parse_llm_json`, `core.provenance`
- `soa_postprocess_consolidated.py` - Now uses `core.USDM_VERSION`, `core.standardize_ids`

#### Phase 4: Archive Workaround Scripts ✅

Moved to `archive/` directory:
- `fix_provenance_keys.py`
- `fix_reconciled_soa.py`
- `apply_clinical_corrections.py`
- `align_structure.py`
- `regenerate_instances.py`
- `audit_timepoints.py`

### Test Results

**Core Module Tests (23 passed):**
- JSON utils: 8 tests ✅
- Provenance: 6 tests ✅
- USDM types: 5 tests ✅
- Constants: 2 tests ✅
- Backward compatibility: 2 tests ✅

**Pipeline Test (CDISC Pilot Study):**
- ✅ Successfully extracted 28 activities, 14 timepoints, 133 ticks
- ✅ Validation completed (0 hallucinations flagged)
- ✅ Output: `output/CDISC_Pilot_Study/9_final_soa.json`

**Import Verification:**
- ✅ `send_pdf_to_llm.py` imports work
- ✅ `vision_extract_soa.py` imports work
- ✅ `reconcile_soa_llm.py` imports work
- ✅ `soa_postprocess_consolidated.py` imports work

### Remaining Work

1. **Simplify large files** - Reduce `soa_postprocess_consolidated.py` and `reconcile_soa_llm.py`
2. **Update main.py** - Add option to use new modular pipeline
3. **Improve prompts** - Reduce need for post-processing
4. **Add more tests** - Integration tests for full pipeline

---

## 1. Original Architectural Intent

Based on documentation and memories, the **original design principles** were:

### Core Philosophy
```
Protocol PDF → Semantic USDM Understanding → Structured Extraction → Validated USDM JSON
```

### Key Design Decisions
1. **Text Extraction = PRIMARY DATA SOURCE** - LLM extracts entities, activities, timepoints from protocol text
2. **Vision Analysis = STRUCTURAL VALIDATION** - Vision identifies SoA table hierarchy, header structure, tick marks
3. **USDM Semantic Prompts** - Prompts grounded in USDM entity definitions to ensure model outputs are schema-aware
4. **Vision validates Text** - Not a parallel extraction; vision confirms/corrects text extraction

### Expected Pipeline Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                        ORIGINAL INTENT                          │
├─────────────────────────────────────────────────────────────────┤
│  PDF                                                            │
│   │                                                             │
│   ├──► Find SoA Pages                                           │
│   │                                                             │
│   ├──► Vision: Extract STRUCTURE                                │
│   │    • Epochs, Encounters (column headers)                    │
│   │    • Activity Groups (row sections)                         │
│   │    • Tick mark positions (validation reference)             │
│   │    OUTPUT: Header Structure JSON                            │
│   │                                                             │
│   └──► Text: Extract DATA (anchored by Header Structure)        │
│        • Activities (names, descriptions, codes)                │
│        • PlannedTimepoints (timing metadata)                    │
│        • ActivityTimepoints (the tick matrix)                   │
│        OUTPUT: SoA Entities JSON                                │
│                                                                 │
│   ├──► Validation: Vision validates Text                        │
│   │    • Tick marks align with vision detection                 │
│   │    • No hallucinated activities/timepoints                  │
│   │    OUTPUT: Validated SoA JSON                               │
│   │                                                             │
│   └──► USDM Generation: Schema-compliant output                 │
│        OUTPUT: Final USDM JSON                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Current State Analysis

### 2.1 File Size Metrics (Bloat Indicators)

| File | Lines | Bytes | Concern |
|------|-------|-------|---------|
| `soa_postprocess_consolidated.py` | 1,307 | 58KB | **CRITICAL** - Too many responsibilities |
| `reconcile_soa_llm.py` | 1,146 | 59KB | **CRITICAL** - Complex reconciliation logic |
| `vision_extract_soa.py` | 757 | 36KB | HIGH - Should be simpler |
| `send_pdf_to_llm.py` | 747 | 33KB | HIGH - Mixed concerns |
| `generate_soa_llm_prompt.py` | 572 | 28KB | MEDIUM - Prompt generation |
| `find_soa_pages.py` | ~500 | 19KB | MEDIUM |

### 2.2 Code Duplication Identified

#### Pattern 1: LLM Client Initialization (appears in 5+ files)
```python
# Duplicated in: reconcile_soa_llm.py, send_pdf_to_llm.py, vision_extract_soa.py, 
#                soa_postprocess_consolidated.py, find_soa_pages.py

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
# ... client initialization
```

#### Pattern 2: Template Loading Fallback (appears in 4+ files)
```python
try:
    from prompt_templates import PromptTemplate
    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False
    
# ... later
if TEMPLATES_AVAILABLE:
    template = PromptTemplate.load(...)
else:
    # fallback to hardcoded
```

#### Pattern 3: ID Standardization (appears in 3+ files)
```python
def standardize_ids_recursive(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and (key == 'id' or key.endswith('Id')):
                obj[key] = value.replace('-', '_')
            # ...
```

#### Pattern 4: JSON Extraction/Cleaning (spread across files)
- `json_utils.py` has `extract_json_str`
- `vision_extract_soa.py` has `clean_llm_json`
- `send_pdf_to_llm.py` has its own parsing logic

### 2.3 Mixed Responsibilities

#### `soa_postprocess_consolidated.py` (1,307 lines) handles:
1. Entity mapping loading
2. LLM-based activity group inference
3. ID standardization
4. Names vs timing normalization
5. Required field defaulting
6. Header ID enforcement (with fuzzy matching)
7. Timing code normalization
8. Provenance tagging
9. Group membership repair
10. Code object completion

**Problem**: This file does too much. It's trying to fix everything the LLM might have gotten wrong.

#### `reconcile_soa_llm.py` (1,146 lines) handles:
1. LLM-based reconciliation
2. Provenance merging
3. Cell-level provenance building
4. Name-based activity matching
5. Anti-smear logic
6. Vision miss detection
7. ID rewriting
8. ScheduleTimeline generation

**Problem**: Reconciliation has become complex because it's merging two potentially conflicting extractions.

### 2.4 Accumulated Workaround Scripts

These files indicate problems were fixed downstream rather than at the source:

| Script | Purpose | Root Cause |
|--------|---------|------------|
| `fix_provenance_keys.py` | Align provenance IDs | ID mismatches between sources |
| `fix_reconciled_soa.py` | Fix reconciled output | Reconciliation bugs |
| `apply_clinical_corrections.py` | Manual fixes | LLM hallucinations |
| `regenerate_instances.py` | Transform structure | Wrong USDM structure |
| `align_structure.py` | Restructure output | Structural drift |

### 2.5 Architectural Drift

**What changed from original intent:**

| Original | Current | Problem |
|----------|---------|---------|
| Vision = Validation | Vision = Parallel extraction | Two conflicting data sources |
| Text = Primary | Text = One of two sources | Reconciliation complexity |
| Simple validation | Complex anti-smear logic | Trying to merge inconsistent data |
| USDM-native output | Post-processing fixes everything | Prompts don't produce clean output |

---

## 3. Root Cause Analysis

### Why did complexity grow?

1. **Prompt/Model Output Issues**
   - LLM outputs didn't match USDM schema → added post-processing
   - IDs were inconsistent → added ID enforcement
   - Timing in names → added normalization

2. **Dual Extraction Strategy**
   - Vision and Text extract independently → need reconciliation
   - IDs don't match → need fuzzy matching
   - Conflicts → need anti-smear logic

3. **Incremental Fixes**
   - Each bug fixed with new code rather than fixing root cause
   - Workaround scripts accumulated
   - Complexity compounds

---

## 4. Proposed Modular Architecture

### 4.1 New Directory Structure

```
protocol2usdm/
├── core/
│   ├── __init__.py
│   ├── config.py           # Centralized configuration
│   ├── usdm_types.py       # USDM dataclasses/Pydantic models
│   ├── usdm_schema.py      # Schema validation, conformance
│   ├── llm_client.py       # Unified LLM interface (consolidate llm_providers.py)
│   ├── json_utils.py       # All JSON parsing/cleaning
│   └── provenance.py       # Provenance tracking
│
├── extraction/
│   ├── __init__.py
│   ├── pdf_processor.py    # PDF → text/images
│   ├── soa_finder.py       # Find SoA pages
│   ├── header_analyzer.py  # Vision: Extract structure ONLY
│   ├── text_extractor.py   # Text: Extract data WITH header anchor
│   └── validator.py        # Vision validates text (not parallel extraction)
│
├── processing/
│   ├── __init__.py
│   ├── normalizer.py       # Minimal normalization (should be mostly unnecessary)
│   ├── enricher.py         # Add missing metadata (codes, descriptions)
│   └── usdm_builder.py     # Build final USDM structure
│
├── prompts/
│   ├── templates/          # YAML prompt templates
│   └── loader.py           # Template loading logic
│
├── output/
│   ├── __init__.py
│   ├── usdm_writer.py      # Write USDM JSON
│   └── viewer.py           # Streamlit viewer (simplified)
│
├── tests/
│   └── ...                 # Organized by module
│
├── main.py                 # Orchestrator (simplified)
└── requirements.txt
```

### 4.2 Simplified Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSED PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 1: PDF Processing                                         │
│  ─────────────────────                                          │
│  pdf_processor.process(pdf_path)                                │
│  → text, images                                                 │
│                                                                 │
│  STEP 2: Find SoA Pages                                         │
│  ──────────────────────                                         │
│  soa_finder.find_pages(text, images)                            │
│  → page_numbers, soa_images                                     │
│                                                                 │
│  STEP 3: Vision Structure Analysis                              │
│  ─────────────────────────────────                              │
│  header_analyzer.analyze(soa_images)                            │
│  → HeaderStructure (epochs, encounters, timepoints, groups)     │
│  PURPOSE: Provides STRUCTURE for text extraction anchor         │
│                                                                 │
│  STEP 4: Text Data Extraction (PRIMARY)                         │
│  ─────────────────────────────────────                          │
│  text_extractor.extract(soa_text, header_structure)             │
│  → SoAEntities (activities, timepoints, tick_matrix)            │
│  PURPOSE: Extract ALL DATA using header structure as guide      │
│                                                                 │
│  STEP 5: Vision Validation (NOT extraction)                     │
│  ─────────────────────────────────────────                      │
│  validator.validate(soa_entities, soa_images, header_structure) │
│  → ValidationResult (confirmed_ticks, flagged_issues)           │
│  PURPOSE: Confirm tick marks, flag potential hallucinations     │
│                                                                 │
│  STEP 6: USDM Generation                                        │
│  ───────────────────────                                        │
│  usdm_builder.build(validated_entities)                         │
│  → USDM JSON (schema-compliant)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Key Architectural Changes

| Current | Proposed | Benefit |
|---------|----------|---------|
| Vision extracts full SoA | Vision extracts structure only | Eliminates reconciliation |
| Text and Vision parallel | Text uses Vision structure | Single source of truth |
| Complex reconciliation | Simple validation | Reduced complexity |
| Post-processing fixes | Better prompts | Clean output from start |
| Workaround scripts | Root cause fixes | No accumulated fixes |

---

## 5. Implementation Roadmap

### Phase 1: Consolidate Core Utilities ✅ COMPLETE
**Goal**: Single source of truth for shared utilities

- [x] Create `core/llm_client.py` - Consolidate all LLM initialization
- [x] Create `core/json_utils.py` - Consolidate all JSON parsing
- [x] Create `core/provenance.py` - Consolidate provenance tracking
- [x] Create `core/constants.py` - Centralized constants
- [x] Create `core/usdm_types.py` - Typed dataclasses
- [x] Update all files to import from core modules
- [x] Run tests to ensure no regressions (23 tests passing)

### Phase 2: Simplify Vision Role ✅ COMPLETE
**Goal**: Vision = Structure extraction only

- [x] Create `extraction/header_analyzer.py` - Vision extracts STRUCTURE only
- [x] Output: HeaderStructure JSON (epochs, encounters, timepoints, groups)
- [x] Does NOT extract full SoA data - provides anchor for text extraction

### Phase 3: Refactor Text Extraction ✅ COMPLETE
**Goal**: Text extraction anchored by Header Structure

- [x] Create `extraction/text_extractor.py`
- [x] Inject HeaderStructure into text extraction prompt
- [x] Text extraction uses Header IDs (no more ID mismatches)
- [x] Produces clean USDM output

### Phase 4: Replace Reconciliation with Validation ✅ COMPLETE
**Goal**: Eliminate complex reconciliation

- [x] Create `extraction/validator.py`
- [x] Validate tick marks against vision
- [x] Flag potential hallucinations for review
- [x] `reconcile_soa_llm.py` no longer needed for new pipeline

### Phase 5: Clean Up 🔄 IN PROGRESS
**Goal**: Remove accumulated workarounds

- [x] Archive: `fix_provenance_keys.py`, `fix_reconciled_soa.py`
- [x] Archive: `apply_clinical_corrections.py`, `align_structure.py`
- [x] Archive: `regenerate_instances.py`, `audit_timepoints.py`
- [x] Create `processing/` module for normalization/enrichment
- [x] Reduce `soa_postprocess_consolidated.py` from 1307 to 1029 lines (-21%)
- [ ] Mark legacy scripts for deprecation
- [ ] Update documentation

---

## 6. Quick Wins (Can Do Now)

### 6.1 Immediate Consolidation

**Create `core/llm_client.py`:**
```python
# Single file for all LLM client needs
from llm_providers import LLMProviderFactory, LLMConfig, LLMResponse

def get_client(model_name: str):
    """Get configured LLM client for any model."""
    return LLMProviderFactory.auto_detect(model_name)
```

**Update imports everywhere:**
```python
# Before (in every file)
from openai import OpenAI
import google.generativeai as genai
# ... 20 lines of setup

# After
from core.llm_client import get_client
```

### 6.2 Consolidate JSON Utilities

**Create unified `core/json_utils.py`:**
```python
# Consolidate: json_utils.py, clean_llm_json from vision, parsing from send_pdf
def parse_llm_json(raw_output: str) -> dict:
    """Universal LLM JSON parser with all fallback strategies."""
    pass

def standardize_ids(obj: dict) -> dict:
    """Single implementation of ID standardization."""
    pass
```

### 6.3 Improve Prompts to Reduce Post-Processing

**Add to extraction prompts:**
```yaml
# Force LLM to use provided IDs
constraints:
  - "You MUST use the exact IDs provided in the headerHints structure"
  - "Never create new IDs - only reference IDs from headerHints"
  - "For activities, use format: act_{index} where index is row position"
```

---

## 7. Success Metrics

After refactoring, we should see:

| Metric | Current | Target |
|--------|---------|--------|
| Lines in largest file | 1,307 | < 400 |
| Number of fix/workaround scripts | 5 | 0 |
| Post-processing functions | 15+ | < 5 |
| Reconciliation complexity | High (anti-smear, fuzzy match) | Simple validation |
| Test coverage | ~70% | > 90% |
| Pipeline steps | 11 | 7 |

---

## 8. Next Steps

1. **Review this analysis** with stakeholders
2. **Decide on Phase 1** implementation
3. **Create core/ directory** and consolidate utilities
4. **Update one script at a time** (start with `find_soa_pages.py`)
5. **Run full test suite** after each change

---

## Appendix: Files to Archive

These files should be moved to `archive/` once refactoring is complete:

- `fix_provenance_keys.py`
- `fix_reconciled_soa.py`
- `apply_clinical_corrections.py`
- `align_structure.py`
- `regenerate_instances.py`
- `audit_timepoints.py` (utility becomes part of validator)
- Deprecated prompt files in `prompts/v2.0_baseline/`

---

*Document Version: 1.0*  
*Generated by Cascade analysis*
