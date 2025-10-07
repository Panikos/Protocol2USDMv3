# Protocol2USDMv3 Improvement Plan

**Status:** Ready for Implementation  
**Created:** 2025-10-04  
**Priority:** High  
**Estimated Effort:** 2-3 days

---

## Executive Summary

This plan outlines structured improvements to Protocol2USDMv3 based on a comprehensive analysis comparing our solution with SOA_Convertor. The identified gaps focus on three critical areas:

1. **Schema Anchoring** - Embedding USDM schema in prompts to reduce structural errors
2. **JSON Validation & Defensive Parsing** - Multi-layer approach to ensure parseable output
3. **Conflict Resolution & Fallbacks** - Explicit rules for handling ambiguity and missing data

**Expected Impact:**
- 30-50% reduction in schema validation failures
- 40-60% reduction in JSON parse errors
- Cleaner separation of visit names and timing information
- More consistent handling of missing/ambiguous data

---

## Gap Analysis Summary

| Gap Area | Current State | Target State | Impact |
|----------|--------------|--------------|--------|
| **Embedded Schema** | Schema validated post-generation | Schema embedded in prompt | Fewer invalid keys, better structure |
| **JSON-Only Fences** | Present but soft | Strong, repeated, with examples | Less trailing prose/fences |
| **Conflict Resolution** | Naming rule strong, others lighter | Detailed rules for all conflicts | Fewer post-processing fixes needed |
| **Fallback Behaviors** | Partially stated | Clear, explicit defaults | Less "invented" content |
| **Worked Example** | Mini example | Schema-aligned full example | Fewer invalid shapes |

---

## Implementation Phases

### Phase 1: Schema Anchoring (Priority: Critical)
**Effort:** 4-6 hours  
**Files Modified:** `generate_soa_llm_prompt.py`

#### Tasks
1. **Add schema loader function**
   ```python
   def load_usdm_schema_text(schema_path: str) -> str:
       # Load and minify USDM schema
       # Keep to 3-12k tokens
   ```

2. **Update prompt templates**
   - Add `{usdm_schema_text}` placeholder to both `FULL_PROMPT_TEMPLATE` and `MINIMAL_PROMPT_TEMPLATE`
   - Position schema after SoA JSON input, before entity instructions

3. **Modify `main()` function**
   - Load schema file: `USDM OpenAPI schema/Wrapper-Input.json`
   - Pass `usdm_schema_text` parameter to `write_prompt()` calls

4. **Update `write_prompt()` signature**
   - Ensure it accepts and formats `usdm_schema_text` parameter

**Success Criteria:**
- Prompt files include minified schema text
- Schema section clearly marked with visual separators
- Token budget stays under 15k for schema section

**Testing:**
- Run `python generate_soa_llm_prompt.py`
- Verify `output/1_llm_prompt.txt` contains schema section
- Check total prompt size < 25k tokens

---

### Phase 2: Strengthen JSON-Only Fences (Priority: Critical)
**Effort:** 6-8 hours  
**Files Modified:** `generate_soa_llm_prompt.py`, `send_pdf_to_llm.py`

#### Part A: Prompt-Level Fences
**File:** `generate_soa_llm_prompt.py`

1. **Add strict output section to templates**
   ```python
   PROMPT_ADDENDUM_JSON_FENCES = """
   ════════════════════════════════════════════════════════════════════
    REQUIRED OUTPUT (JSON ONLY)
   ════════════════════════════════════════════════════════════════════
   - Return **one** JSON object that validates against the schema above
   - **No prose, no Markdown, no code fences**
   - The string must be directly loadable by json.loads()
   
   ❌ Bad: "Here is your JSON:\n{ ... }"
   ✅ Good: { ... }
   """
   ```

2. **Append to both templates**
   - Position at end of `FULL_PROMPT_TEMPLATE` and `MINIMAL_PROMPT_TEMPLATE`

#### Part B: Defensive Parser
**File:** `send_pdf_to_llm.py`

1. **Add `extract_json_str()` function** (after `clean_llm_json()`)
   ```python
   def extract_json_str(s: str) -> str:
       # Fast path: direct parse
       # Remove code fences
       # Extract first {...} block
       # Fix trailing commas
       # Validate and return
   ```

2. **Add `call_with_retry()` wrapper**
   ```python
   def call_with_retry(call_fn, text_chunk, prompt, model_name, max_attempts=2):
       # Try call
       # On failure, tighten prompt and retry
       # Log all attempts
   ```

3. **Update chunk processing loop**
   - Replace direct `send_text_to_llm()` calls with `call_with_retry()`
   - Use `extract_json_str()` before `json.loads()`

**Success Criteria:**
- Zero markdown fence leakage in outputs
- Parse success rate > 95% (vs. current ~85%)
- Max 2 retries per chunk
- All failures logged with details

**Testing:**
- Run pipeline on 3 test protocols
- Check `logs/` for parse errors
- Verify no code fences in `5_raw_text_soa.json` or `6_raw_vision_soa.json`

---

### Phase 3: Conflict Resolution & Fallbacks (Priority: High)
**Effort:** 4-6 hours  
**Files Modified:** `generate_soa_llm_prompt.py`, `soa_postprocess_consolidated.py`

#### Part A: Enhanced Modeling Rules
**File:** `generate_soa_llm_prompt.py`

1. **Add explicit modeling rules section to templates**
   ```python
   MODELING_RULES = """
   ════════════════════════════════════════════════════════════════════
    MODELING RULES
   ════════════════════════════════════════════════════════════════════
   - Use **stable, unique IDs** for all entities and maintain cross-references
   - Do **not invent** assessments, visits, windows, or epochs not in the SoA
   - When data is missing, **use empty arrays/objects** rather than hallucinating
   - Normalize repeated labels (e.g., "Visit 3", "Visit 3.1") consistently
   - Keep all activities in timeline.activities, even if unscheduled
   """
   ```

2. **Strengthen naming vs. timing rule**
   - Add negative examples showing what NOT to do
   - Emphasize windowLabel vs. description usage hierarchy

#### Part B: Post-Processing Normalization
**File:** `soa_postprocess_consolidated.py`

1. **Add `normalize_names_vs_timing()` function**
   ```python
   def normalize_names_vs_timing(timeline: dict):
       # Extract timing patterns from encounter/timepoint names
       # Move timing to windowLabel or description
       # Clean names
   ```

2. **Add `ensure_required_fields()` function**
   ```python
   def ensure_required_fields(study: dict):
       # Ensure versions array exists
       # Ensure timeline exists
       # Ensure required arrays (activities, timepoints, encounters)
       # Add default epoch if missing
   ```

3. **Call both functions in main post-processing flow**
   - After header enrichment, before validation

**Success Criteria:**
- Zero timing patterns in Encounter.name or PlannedTimepoint.name
- All timing in windowLabel or description fields
- No invented activities/visits in output
- Default epoch present when none extracted

**Testing:**
- Run on CDISC Pilot Study
- Verify all visit names are clean (no "Week -2" in names)
- Check that windowLabel contains timing info
- Ensure epochs array has at least one entry

---

### Phase 4: Validation-Guided Retry (Priority: Medium)
**Effort:** 3-4 hours  
**Files Modified:** `send_pdf_to_llm.py`, `main.py`

#### Tasks
1. **Integrate schema validation into chunk loop**
   - After successful parse, run quick schema check
   - If validation fails, capture first error

2. **Add validation error retry**
   ```python
   if validation_errors:
       retry_prompt = prompt + f"""
       
       VALIDATION ERROR:
       {validation_errors[0]}
       
       Fix the JSON to satisfy the schema. Return FULL corrected JSON.
       """
       raw_output = call_with_retry(..., max_attempts=1)
   ```

3. **Track validation retry success rate**
   - Log how often validation retry fixes the issue
   - Report in pipeline summary

**Success Criteria:**
- 20-30% of validation errors auto-corrected via retry
- No infinite retry loops (max 1 validation retry)
- All retry attempts logged

**Testing:**
- Inject deliberate schema errors in test prompts
- Verify retry corrects them
- Check logs for retry statistics

---

## Testing & Validation Strategy

### Unit Tests
```bash
pytest tests/test_json_extraction.py -v
pytest tests/test_normalization.py -v
```

**New test files to create:**
- `tests/test_json_extraction.py` - Test `extract_json_str()` on various malformed inputs
- `tests/test_normalization.py` - Test `normalize_names_vs_timing()` on edge cases

### Integration Tests
```bash
python main.py input/CDISC_Pilot_Study.pdf --model gemini-2.5-pro
```

**Success metrics:**
- Schema validation passes
- No parse errors in logs
- All expected visits present
- Clean visit names (no timing text)

### Regression Tests
Track these metrics before/after improvements:

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Parse success rate | ~85% | >95% | Count parse errors in logs |
| Schema validation pass rate | ~70% | >90% | Run validate_usdm_schema.py |
| Naming rule violations | ~40% | <5% | Grep for "Week\|Day" in Encounter.name |
| Chunk retry rate | N/A | <20% | Log retry statistics |

---

## Rollout Plan

### Step 1: Feature Branch
```bash
git checkout -b feature/schema-anchoring-improvements
```

### Step 2: Implement Phases in Order
- Phase 1 (Schema Anchoring) → Test → Commit
- Phase 2A (Prompt Fences) → Test → Commit
- Phase 2B (Defensive Parser) → Test → Commit
- Phase 3A (Modeling Rules) → Test → Commit
- Phase 3B (Post-Processing) → Test → Commit
- Phase 4 (Validation Retry) → Test → Commit

### Step 3: Full Regression Testing
Run pipeline on all test protocols:
- CDISC Pilot Study
- Any other reference protocols in `input/`

Compare outputs before/after improvements.

### Step 4: Merge to Main
```bash
git checkout main
git merge feature/schema-anchoring-improvements
git push
```

### Step 5: Update Documentation
- Update `README.md` with new capabilities
- Add note in `CHANGELOG.md` about improvements
- Reference `WINDSURF_RULES.md` for ongoing development

---

## Risk Mitigation

### Risk 1: Schema Embedding Increases Token Count
**Likelihood:** High  
**Impact:** Medium  
**Mitigation:**
- Minify schema aggressively (strip whitespace, comments)
- Monitor token usage and truncate if needed
- Consider schema summary instead of full schema for extremely large protocols

### Risk 2: Stricter Parsing Breaks Existing Workarounds
**Likelihood:** Medium  
**Impact:** Low  
**Mitigation:**
- Keep existing `clean_llm_json()` as fallback
- Test on all historical protocols before merging
- Feature flag for new parser (can revert if needed)

### Risk 3: Post-Processing Normalization Too Aggressive
**Likelihood:** Low  
**Impact:** Medium  
**Mitigation:**
- Log all normalization changes for audit
- Implement dry-run mode for testing
- Add override flag to skip normalization if needed

---

## Success Metrics (30-Day Post-Implementation)

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| **Schema validation pass rate** | >90% | Run on 20+ protocols, calculate pass rate |
| **Parse error rate** | <5% | Track parse failures in logs over 100+ runs |
| **Post-processing fixes** | -50% | Count fixes applied in postprocess step |
| **Naming rule violations** | <5% | Automated check for timing in name fields |
| **User-reported issues** | -40% | Track GitHub issues / support tickets |

---

## Maintenance & Continuous Improvement

### Monthly Reviews
- Review logs for new failure patterns
- Update `WINDSURF_RULES.md` with lessons learned
- Add regression tests for any new bug fixes

### Quarterly Updates
- Check for USDM schema updates
- Re-run benchmark tests on new models
- Update prompt templates based on model improvements

### Documentation
- Keep `IMPROVEMENT_PLAN.md` updated with completion status
- Document any deviations from plan
- Share lessons learned in team meetings

---

## Appendix: Quick Command Reference

```bash
# Generate updated prompts
python generate_soa_llm_prompt.py --output output/test_run/1_llm_prompt.txt

# Run full pipeline with new improvements
python main.py input/CDISC_Pilot_Study.pdf --model gemini-2.5-pro

# Validate output
python validate_usdm_schema.py output/CDISC_Pilot_Study/10_reconciled_soa.json

# Run tests
pytest tests/ -v --tb=short

# Check logs for parse/validation errors
grep -i "error\|warning" logs/pipeline_*.log
```

---

## Notes

- All improvements align with `WINDSURF_RULES.md` principles
- Changes are backward-compatible (existing pipelines continue to work)
- Code follows existing style conventions in the project
- All new functions include docstrings and type hints
- Logging added at appropriate levels (INFO/WARNING/ERROR)

---

## Sign-Off

**Plan Author:** AI Assistant  
**Date:** 2025-10-04  
**Reviewed By:** [Pending User Review]  
**Status:** Ready for Implementation
