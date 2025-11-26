# Provenance/Traceability System Analysis

## Current State ✅

### What Works
The pipeline **DOES** have provenance tracking, and it's **partially** following your stated preference:

1. **Steps 7 & 8: Separate Provenance Files** ✅
   - `7_postprocessed_text_soa_provenance.json`
   - `8_postprocessed_vision_soa_provenance.json`
   - Clean USDM JSON + separate provenance (matches your preference!)

2. **Structure:**
   ```json
   {
     "plannedTimepoints": {
       "plannedTimepoint-1": "text",
       "plannedTimepoint-2": "text"
     },
     "activities": {
       "activity-1": "text"
     },
     "encounters": {
       "encounter-1": "text"
     }
   }
   ```

3. **Tracking Sources:**
   - `"text"` - Entity from text extraction
   - `"vision"` - Entity from vision extraction

---

## Gap Identified ⚠️

### Step 9 (Reconciliation): Embedded Provenance
**Problem:** The reconciled output (`9_reconciled_soa.json`) currently:
- ✅ Merges provenance from text + vision sources
- ❌ **EMBEDS** it in the JSON as `p2uProvenance` key
- ❌ **NO separate** `9_reconciled_soa_provenance.json` file
- **Violates** your stated preference for separate provenance files

### Missing Functionality
1. **No "both" tag:** When an entity appears in BOTH text AND vision, it's only marked with one source
2. **No quality flags:** No indication of entities needing review or having conflicts
3. **No confidence scores:** Vision might have better quality for tables, text for narratives

---

## Recommended Solution

### 1. **Split Provenance for Step 9** (High Priority)
**Action:** Modify `reconcile_soa_llm.py` to:
- Write clean USDM to `9_reconciled_soa.json` (NO embedded provenance)
- Write provenance to `9_reconciled_soa_provenance.json` (separate file)
- Follow same pattern as Steps 7 & 8

**Benefit:**
- ✅ Downstream systems get pure USDM
- ✅ Consistent with your stated preference
- ✅ Pipeline unchanged (files generated in parallel)

### 2. **Enhanced Provenance Schema** (Medium Priority)
**Current:**
```json
{
  "encounter-1": "text"
}
```

**Enhanced:**
```json
{
  "encounter-1": {
    "source": "both",           // "text" | "vision" | "both" | "llm_reconciled"
    "confidence": "high",        // "high" | "medium" | "low" 
    "needsReview": false,        // Boolean flag
    "textQuality": 0.95,         // Optional: LLM confidence score
    "visionQuality": 0.88,       // Optional: LLM confidence score
    "reconciliationNotes": ""    // Optional: Why LLM chose this version
  }
}
```

**Backward Compatible Option (Simpler):**
```json
{
  "encounter-1": "text",              // Existing format
  "encounter-2": "vision",
  "encounter-3": "both",              // NEW: Found in text AND vision
  "encounter-4": "llm_reconciled",    // NEW: LLM merged conflicting versions
  "encounter-5": "vision (review)"    // NEW: Flagged for review
}
```

### 3. **Quality Flags** (Low Priority - Optional)
Add indicators for common issues:
- **Needs Review:**
  - Conflicting data between text/vision
  - Low LLM confidence
  - Missing required fields
- **Source Conflict:**
  - Text says "Week 1", Vision says "Day 7"
  - Different activity names
- **Partial Data:**
  - Entity exists but missing key attributes

---

## Implementation Plan

### Phase 1: Fix Step 9 Provenance Split (Immediate)
**Files to modify:**
- `reconcile_soa_llm.py` - Add provenance split logic

**Code:**
```python
# After line 127 in reconcile_soa_llm.py
# Extract provenance before saving
provenance = parsed_json.pop('p2uProvenance', {})

# Save clean USDM
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(parsed_json, f, indent=2, ensure_ascii=False)

# Save provenance separately
prov_path = output_path.replace('.json', '_provenance.json')
with open(prov_path, "w", encoding="utf-8") as pf:
    json.dump(provenance, pf, indent=2, ensure_ascii=False)

print(f"[SUCCESS] Reconciled SoA written to {output_path}")
print(f"[SUCCESS] Provenance written to {prov_path}")
```

**Impact:**
- ✅ No pipeline changes
- ✅ Generates file in parallel
- ✅ Consistent with Steps 7 & 8
- ✅ Aligns with your preference

### Phase 2: Add "both" Source Detection (Next)
**Files to modify:**
- `reconcile_soa_llm.py` - Enhance `_merge_prov()` function

**Logic:**
```python
def _merge_prov(dest: dict, src: dict, src_name: str) -> dict:
    """Merge provenance with 'both' detection."""
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(dest.get(key), dict):
            for inner_id, inner_val in val.items():
                if inner_id in dest[key]:
                    # Entity exists in both sources
                    dest[key][inner_id] = "both"
                else:
                    dest[key][inner_id] = inner_val
        else:
            dest[key] = val
    return dest
```

**Output Example:**
```json
{
  "encounters": {
    "encounter-1": "both",      // Found in text AND vision
    "encounter-2": "text",      // Only in text
    "encounter-3": "vision"     // Only in vision
  }
}
```

### Phase 3: Quality Flags (Future Enhancement)
- Add LLM confidence scores
- Flag conflicts for review
- Add reconciliation notes

---

## File Structure After Implementation

```
output/Alexion_Study/
├── 5_raw_text_soa.json
├── 6_raw_vision_soa.json
├── 7_postprocessed_text_soa.json
├── 7_postprocessed_text_soa_provenance.json      ← Already exists
├── 8_postprocessed_vision_soa.json
├── 8_postprocessed_vision_soa_provenance.json    ← Already exists
├── 9_reconciled_soa.json                         ← Clean USDM (no provenance)
└── 9_reconciled_soa_provenance.json              ← NEW! Separate provenance
```

---

## Benefits

1. **Downstream Consumption:**
   - Pure USDM files can be consumed without custom key filtering
   - Provenance available for auditing/review tools
   
2. **Transparency:**
   - Clear visibility of what came from where
   - Easy to spot entities that need review
   
3. **Quality Assurance:**
   - "both" tag indicates high confidence (text + vision agree)
   - Single-source entities may need verification
   
4. **No Pipeline Impact:**
   - Files generated in parallel
   - No performance overhead
   - Backward compatible

---

## Next Steps

**Recommendation:** Implement **Phase 1** immediately (30 min fix)
- Fixes the gap in your existing preference
- Clean, consistent file structure
- No pipeline changes required

**Then consider Phase 2** for enhanced traceability
- Add "both" detection
- More informative provenance
- Better QA support

Would you like me to implement Phase 1 now?
