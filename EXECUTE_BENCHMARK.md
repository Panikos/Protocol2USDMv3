# Execute Benchmark-Driven Optimization - Quick Guide

**Status:** ✅ Ready to Execute  
**Time Required:** 3-4 hours  
**Goal:** Measure if optimized prompts improve USDM extraction quality

---

## What Was Enhanced

### ✅ Benchmark Script Enhanced with USDM Metrics

**New Metrics Added:**
1. **Visit Count Accuracy** - Measures if all 14 visits extracted (CDISC Pilot)
2. **Activity Count Accuracy** - Measures if all activities extracted
3. **ActivityTimepoint Completeness** - Critical USDM mapping metric
4. **Comprehensive Linkage Validation** - Checks all 4 types of cross-references
5. **All 8 PlannedTimepoint Fields** - Complete field population check
6. **Weighted Completeness** - Prioritizes critical entities (Activities, Timepoints)

---

## Execution Steps

### Phase 1: Create Gold Standard (1 hour)

#### Step 1.1: Ensure Using Original Prompts
```powershell
# Check if optimized versions are active
ls prompts\*.yaml | Select-String "optimized"

# If optimized versions exist in main directory, restore originals
if (Test-Path prompts\v2.0_baseline) {
    cp prompts\v2.0_baseline\*.yaml prompts\
}
```

#### Step 1.2: Run Pipeline to Create Initial Gold Standard
```powershell
# Ensure CDISC Pilot is in test_data
if (!(Test-Path test_data\medium\CDISC_Pilot_Study.pdf)) {
    mkdir -p test_data\medium
    cp input\CDISC_Pilot_Study.pdf test_data\medium\
}

# Run extraction with original prompts
python main.py test_data\medium\CDISC_Pilot_Study.pdf --model gemini-2.5-pro
```

**⚠️ IMPORTANT:** This will take 5-10 minutes. Do not interrupt!

#### Step 1.3: Copy Output as Gold Standard Starting Point
```powershell
cp output\CDISC_Pilot_Study\9_reconciled_soa.json `
   test_data\medium\CDISC_Pilot_Study_gold.json
```

#### Step 1.4: Manually Verify Gold Standard ⭐ CRITICAL

Open `test_data\medium\CDISC_Pilot_Study_gold.json` and verify:

**Required Checks:**
- [ ] All 14 visits present: Visit 1/Week -2 through ET, RT
- [ ] All activities extracted (compare against PDF pages 52-54)
- [ ] All PlannedTimepoints have 8 required fields
- [ ] All ActivityTimepoint mappings correct
- [ ] All linkages valid (IDs reference existing entities)
- [ ] Schema validates

**How to validate:**
```powershell
python validate_schema.py test_data\medium\CDISC_Pilot_Study_gold.json
```

**Expected:** Should pass validation or have only minor issues you can fix.

**Fix any errors manually** - this is your "perfect" reference!

---

### Phase 2: Baseline Benchmark (30 min)

#### Step 2.1: Confirm Original Prompts Active
```powershell
# Check versions in prompts
Get-Content prompts\soa_extraction.yaml | Select-String "version"
# Should show: version: 2.0
```

#### Step 2.2: Run Baseline Benchmark
```powershell
python benchmark_prompts.py `
  --test-set test_data\ `
  --model gemini-2.5-pro `
  --output-dir benchmark_results
```

**Output Example:**
```
======================================================================
BENCHMARK SUMMARY - USDM EXTRACTION QUALITY
======================================================================
Total Test Cases: 1
Schema Validation: 1/1 (100.0%)

CORE METRICS (Overall Quality):
  • Completeness Score:      85.2%   ← BASELINE
  • Linkage Accuracy:        92.1%   ← BASELINE
  • Field Population:        78.5%   ← BASELINE

USDM-SPECIFIC METRICS (Entity-Level Accuracy):
  • Visit Count Accuracy:    92.9%   ← BASELINE
  • Activity Count Accuracy: 88.3%   ← BASELINE
  • ActivityTimepoint Map:   85.7%   ← BASELINE
======================================================================
```

**Save these numbers!** This is your baseline.

Results saved to: `benchmark_results/benchmark_YYYYMMDD_HHMMSS.json`

---

### Phase 3: Deploy Optimized Prompts (5 min)

#### Step 3.1: Backup Originals
```powershell
mkdir -p prompts\v2.0_baseline
cp prompts\soa_extraction.yaml prompts\v2.0_baseline\
cp prompts\vision_soa_extraction.yaml prompts\v2.0_baseline\
cp prompts\soa_reconciliation.yaml prompts\v2.0_baseline\
cp prompts\find_soa_pages.yaml prompts\v2.0_baseline\
```

#### Step 3.2: Deploy Optimized Versions
```powershell
cp prompts\soa_extraction_optimized.yaml prompts\soa_extraction.yaml
cp prompts\vision_soa_extraction_optimized.yaml prompts\vision_soa_extraction.yaml
cp prompts\soa_reconciliation_optimized.yaml prompts\soa_reconciliation.yaml
cp prompts\find_soa_pages_optimized.yaml prompts\find_soa_pages.yaml
```

#### Step 3.3: Verify Optimized Versions Active
```powershell
Get-Content prompts\soa_extraction.yaml | Select-String "version"
# Should show: version: 2.1 or mention "Auto-optimized"
```

---

### Phase 4: Optimized Benchmark (30 min)

#### Step 4.1: Run Optimized Benchmark
```powershell
python benchmark_prompts.py `
  --test-set test_data\ `
  --model gemini-2.5-pro `
  --output-dir benchmark_results
```

**Output Example:**
```
======================================================================
BENCHMARK SUMMARY - USDM EXTRACTION QUALITY
======================================================================
Total Test Cases: 1
Schema Validation: 1/1 (100.0%)

CORE METRICS (Overall Quality):
  • Completeness Score:      88.7%   ← OPTIMIZED (+3.5%)
  • Linkage Accuracy:        94.8%   ← OPTIMIZED (+2.7%)
  • Field Population:        82.3%   ← OPTIMIZED (+3.8%)

USDM-SPECIFIC METRICS (Entity-Level Accuracy):
  • Visit Count Accuracy:    100.0%  ← OPTIMIZED (+7.1%)
  • Activity Count Accuracy: 95.2%   ← OPTIMIZED (+6.9%)
  • ActivityTimepoint Map:   91.4%   ← OPTIMIZED (+5.7%)
======================================================================
```

Results saved to: `benchmark_results/benchmark_YYYYMMDD_HHMMSS.json`

---

### Phase 5: Compare & Decide (15 min)

#### Step 5.1: Compare Results
```powershell
# Find the two latest benchmarks
$files = Get-ChildItem benchmark_results\benchmark_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 2

python compare_benchmark_results.py $files[1].FullName $files[0].FullName
```

**Or specify manually:**
```powershell
python compare_benchmark_results.py `
  benchmark_results\benchmark_20251006_010000.json `
  benchmark_results\benchmark_20251006_020000.json
```

#### Step 5.2: Review Comparison Output

**Example Output:**
```
======================================================================
BENCHMARK COMPARISON
======================================================================
Baseline:  benchmark_20251006_010000.json (v2.0)
Optimized: benchmark_20251006_020000.json (v2.1)
======================================================================

📊 METRIC CHANGES:

✅ Average Completeness:
    Baseline:  85.2%
    Optimized: 88.7%
    Change:    +3.5% (+4.1%) - IMPROVED

✅ Visit Count Accuracy (USDM):
    Baseline:  92.9%
    Optimized: 100.0%
    Change:    +7.1% (+7.6%) - IMPROVED

======================================================================
DECISION RECOMMENDATION:
======================================================================
✅ ACCEPT - Solid improvement
   Average improvement across key metrics: +5.1%
======================================================================
```

#### Step 5.3: Make Decision

**ACCEPT if:**
- Average improvement ≥ +2%
- No regressions > -2% on any metric
- USDM-specific metrics improved

**REJECT if:**
- Any significant regression (> -2%)
- Overall negative change
- Validation rate decreased

**NEED MORE DATA if:**
- Results inconclusive (< ±2%)
- Large variance between runs

---

### Phase 6: Deploy or Rollback (5 min)

#### If ACCEPTED ✅

```powershell
# Keep optimized prompts
# They're already active!

# Document the improvement
Add-Content OPTIMIZATION_LOG.md @"
## Optimization: 2025-10-06
- **Prompts:** All 4 templates optimized to v2.1
- **Method:** Google Gemini meta-prompt optimization
- **Result:** +5.1% average improvement across USDM metrics
- **Status:** ✅ ACCEPTED and deployed
"@
```

#### If REJECTED ❌

```powershell
# Restore original prompts
cp prompts\v2.0_baseline\*.yaml prompts\

# Document the finding
Add-Content OPTIMIZATION_LOG.md @"
## Optimization Attempt: 2025-10-06
- **Prompts:** All 4 templates tested with v2.1
- **Method:** Google Gemini meta-prompt optimization
- **Result:** No improvement / Regression detected
- **Status:** ❌ REJECTED - Reverted to v2.0
"@
```

#### If NEED MORE DATA 🔍

```powershell
# Add more test cases
# Then re-run both baselines and optimized benchmarks
# Make decision with higher confidence
```

---

## Expected Results

### Likely Outcomes:

**Best Case (60% probability):**
- +3-7% improvement across metrics
- Especially strong on Visit/Activity accuracy
- Clear accept decision

**Mixed Results (30% probability):**
- Some metrics improve, some regress
- Overall small positive (+1-2%)
- Need more test cases to decide

**No Improvement (10% probability):**
- Minimal change (±1%)
- Prompts already well-optimized
- Learn what works, iterate differently

---

## Troubleshooting

### Gold Standard Creation Fails
**Solution:** Fix JSON errors manually, ensure all required USDM fields present

### Benchmark Takes Too Long
**Solution:** Expected! 10-15 minutes per test case. Be patient.

### Comparison Shows No Data
**Solution:** Check JSON files exist and have correct format

### Results are Identical
**Solution:** Verify optimized prompts are actually active in `prompts/` directory

---

## Success Criteria

**Minimum Success:**
- [ ] Gold standard created and verified
- [ ] Baseline benchmark completed
- [ ] Optimized benchmark completed
- [ ] Quantitative comparison made
- [ ] Data-driven decision documented

**Ideal Success:**
- [ ] +5% improvement on core metrics
- [ ] +7% improvement on USDM-specific metrics
- [ ] No regressions
- [ ] Optimized prompts accepted and deployed

---

## Next Steps After Execution

### If ACCEPTED:
1. Add 2-3 more test cases
2. Re-benchmark to confirm improvements hold
3. Create v2.2 with targeted improvements
4. Track metrics over time

### If REJECTED:
1. Analyze specific failures
2. Manually improve problem areas
3. Re-optimize with focused changes
4. Test again

### If INCONCLUSIVE:
1. Add more test cases immediately
2. Re-run full benchmark suite
3. Achieve statistical significance
4. Then decide

---

## Time Estimates

| Phase | Activity | Time |
|-------|----------|------|
| 1 | Create gold standard | 1 hour |
| 2 | Baseline benchmark | 30 min |
| 3 | Deploy optimized | 5 min |
| 4 | Optimized benchmark | 30 min |
| 5 | Compare & decide | 15 min |
| 6 | Deploy/rollback | 5 min |
| **Total** | **Complete execution** | **~3 hours** |

---

## Commands Summary

```powershell
# Phase 1: Create gold standard
python main.py test_data\medium\CDISC_Pilot_Study.pdf --model gemini-2.5-pro
cp output\CDISC_Pilot_Study\9_reconciled_soa.json test_data\medium\CDISC_Pilot_Study_gold.json
# Manually verify and fix gold standard

# Phase 2: Baseline
python benchmark_prompts.py --test-set test_data\ --model gemini-2.5-pro

# Phase 3: Deploy optimized
cp prompts\*_optimized.yaml prompts\

# Phase 4: Optimized benchmark
python benchmark_prompts.py --test-set test_data\ --model gemini-2.5-pro

# Phase 5: Compare
python compare_benchmark_results.py benchmark_results\*.json --latest 2

# Phase 6: Accept or Reject based on data
```

---

**Status:** ✅ **READY TO EXECUTE**  
**Tools:** All enhanced with USDM-specific metrics  
**Goal:** Data-driven decision on prompt optimization  

**Start with Phase 1!**
