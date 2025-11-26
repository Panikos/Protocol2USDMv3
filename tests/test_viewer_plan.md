# Streamlit Viewer Testing Plan

## Overview

This document outlines a step-by-step testing plan for the SoA Streamlit Viewer (`soa_streamlit_viewer.py`) to ensure it correctly represents USDM output and has no redundant functionality.

## Current Issues Identified

### 1. Duplicate Code
- **`get_timeline()`** is defined TWICE (lines 13-22 and 269-278)
- Both functions do the same thing - extract timeline from USDM structure

### 2. Hardcoded File Names
- File inventory looks for `9_reconciled_soa.json` (old pipeline)
- New pipeline outputs `9_final_soa.json`
- Will fail to load new pipeline outputs

### 3. Unused/Legacy Functions
- `render_soa_table()` expects `isPerformed` field - not present in new outputs
- `style_provenance()` function (line 827) appears unused
- `get_timepoints()` function (line 310) is incomplete (cut off at line 323)

### 4. Potential Functionality Overlap
- Multiple tabs show similar content (Raw vs Post-processed)
- Both `render_flexible_soa()` and `render_soa_table()` do similar things

---

## Testing Plan

### Phase 1: Data Loading Tests

#### Test 1.1: Timeline Extraction
**Component:** `get_timeline()`
**Test:** Load both old and new format USDM JSON files
**Expected:** Correctly extracts timeline from:
- Standard USDM: `study.versions[0].timeline`
- Legacy format: `study.studyVersions[0].timeline`
- Flat format: `timeline`

```bash
# Test command
python -c "
from soa_streamlit_viewer import get_timeline
import json

# Test with new pipeline output
data = json.load(open('output/EliLilly_GPT51_test/step6_final_soa.json'))
timeline = get_timeline(data)
print('Timeline found:', timeline is not None)
print('Activities:', len(timeline.get('activities', [])))
"
```

#### Test 1.2: File Inventory
**Component:** `get_file_inventory()`
**Test:** Verify all expected files are found
**Issue:** Currently looks for `9_reconciled_soa.json` but new pipeline creates `9_final_soa.json`

```bash
# Test that file inventory works with new outputs
```

---

### Phase 2: Metrics Computation Tests

#### Test 2.1: Entity Counts
**Component:** `compute_usdm_metrics()`
**Test:** Verify counts match actual data
```python
# Expected metrics for EliLilly GPT-5.1 test:
# - activities: 33
# - plannedTimepoints: 7
# - encounters: 7
# - activityTimepoints: 60
```

#### Test 2.2: Linkage Accuracy
**Component:** `compute_usdm_metrics()` linkage calculation
**Test:** Verify linkages are correctly validated
- PlannedTimepoint → Encounter links
- ActivityTimepoint → Activity links
- ActivityTimepoint → PlannedTimepoint links

#### Test 2.3: Field Population
**Component:** `compute_usdm_metrics()` field_population_rate
**Test:** Verify required field checks are accurate

---

### Phase 3: Rendering Tests

#### Test 3.1: Flexible Renderer
**Component:** `render_flexible_soa()`
**Test:** Visually verify SoA table renders correctly
**Checkpoints:**
- [ ] Activities shown in rows
- [ ] Timepoints/Encounters shown in columns
- [ ] Tick marks (X) in correct cells
- [ ] Activity groups shown as row hierarchy
- [ ] Epoch → Encounter hierarchy in columns

#### Test 3.2: Provenance Styling
**Component:** Provenance color coding
**Test:** Verify colors match provenance data
- Blue (#60a5fa) = Text only
- Yellow (#facc15) = Vision only
- Green (#4ade80) = Both

#### Test 3.3: Row Filtering
**Test:** Verify checkbox filters work
- [ ] "Hide rows where all timepoints are ticked"
- [ ] "Show only rows with vision-contributed ticks"
- [ ] "Show only rows with ticks from both text and vision"

---

### Phase 4: UI Component Tests

#### Test 4.1: Sidebar
- [ ] Run selection dropdown populates
- [ ] Metrics dashboard shows correct values
- [ ] Linkage/Field population color coding correct

#### Test 4.2: Main SoA Display
- [ ] Final SoA table renders
- [ ] JSON expander works
- [ ] Table is scrollable

#### Test 4.3: Tabs
- [ ] Raw Outputs tab loads and renders
- [ ] Post-Processed tab loads and renders
- [ ] Data Files tab shows intermediate JSON
- [ ] Config Files tab shows prompts
- [ ] Images tab displays SoA page images
- [ ] Completeness Report shows metrics table
- [ ] USDM Metrics shows quality scores

---

### Phase 5: Redundancy Analysis

#### Functions to Review

| Function | Used? | Redundant? | Action |
|----------|-------|------------|--------|
| `get_timeline()` (line 13) | Yes | DUPLICATE | Remove one |
| `get_timeline()` (line 269) | Yes | DUPLICATE | Keep this one |
| `get_timepoints()` (line 310) | No | INCOMPLETE | Remove |
| `render_soa_table()` | No | LEGACY | Archive |
| `style_provenance()` | No | UNUSED | Remove |

#### Tabs to Review

| Tab | Purpose | Redundant? |
|-----|---------|------------|
| Raw Outputs | Show raw LLM output | Keep |
| Post-Processed | Show processed output | Keep |
| Data Files | Show intermediate JSON | Keep |
| Config Files | Show prompts | Keep |
| SoA Images | Show extracted pages | Keep |
| Completeness Report | Show field coverage | Maybe merge with USDM Metrics |
| USDM Metrics | Show quality scores | Keep |

---

## Test Execution Checklist

### Manual Testing Steps (User Completed Visual Testing)

1. **Load Viewer** ✅
   ```bash
   streamlit run soa_streamlit_viewer.py
   ```

2. **Select Test Run** ✅
   - Select `EliLilly_GPT51_test` or `EliLilly_Gemini_test` from sidebar

3. **Verify Main SoA Table** ✅
   - [x] Table renders without errors
   - [x] 33 activities displayed
   - [x] 7 timepoint columns
   - [x] 60 tick marks visible (GPT-5.1) / 78 (Gemini)
   - [x] Activity groups shown

4. **Verify Sidebar Metrics** ✅
   - [x] Entity counts match expected
   - [x] Linkage accuracy displays
   - [x] Field population displays

5. **Test Each Tab** ✅
   - [x] Raw Outputs tab - loads text extraction data
   - [x] Post-Processed tab - loads if data available
   - [x] Data Files tab - shows header structure
   - [x] Config Files tab - shows entity mapping
   - [x] SoA Images tab - displays 8 page images
   - [x] Completeness Report tab - shows metrics table
   - [x] USDM Metrics tab - shows quality scores

6. **Test Filtering** ✅
   - [x] Row hiding works (if all-ticked rows present)
   - [x] Vision filter available (provenance attached)

---

## Fixes Completed ✅

### Priority 1: Critical
1. ✅ Update file inventory to support `9_final_soa.json` and `step6_*.json`
2. ✅ Remove duplicate `get_timeline()` function
3. ✅ Support new provenance file format (`_provenance.json`)
4. ✅ Support `step2_images` directory

### Priority 2: Cleanup
1. ✅ Remove incomplete `get_timepoints()` function (never returned anything)
2. ✅ Remove unused `style_provenance()` function (46 lines)
3. ✅ Remove unused `render_soa_table()` function (117 lines)

**Line count reduction: 1231 → 977 lines (-20%)**

### Priority 3: Enhancement (Future)
1. Consider merging Completeness Report and USDM Metrics tabs
2. Add gold standard comparison for new test outputs
