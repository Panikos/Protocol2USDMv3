# Benchmark-Driven Prompt Optimization - Execution Plan

**Goal:** Measure if optimized prompts actually improve USDM extraction quality  
**Approach:** Data-driven comparison using real protocols and gold standards  
**Timeline:** 3-4 hours total

---

## ⚠️ Critical Point

**Optimization without benchmarking is speculation.**

We've created optimized prompts, but we don't yet know if they:
- ✅ Extract more complete USDM entities
- ✅ Improve linkage accuracy
- ✅ Fill more required fields
- ✅ Reduce validation errors

**We need to measure against project goals: PDF → Valid USDM**

---

## Project Success Metrics (USDM-Specific)

### Primary Metrics
1. **Completeness Score** - % of expected entities extracted
   - Target: >90%
   - Current baseline: Unknown (need to measure)

2. **Linkage Accuracy** - % of cross-references correct
   - Target: >95%
   - Measures: ActivityTimepoint.activityId → Activity, etc.

3. **Field Population Rate** - % of required fields filled
   - Target: >85%
   - Measures: PlannedTimepoint has all 8 required fields

### Secondary Metrics
4. **Schema Validation** - Does output validate against USDM?
   - Target: 100%
   
5. **Visit Extraction** - All visits found?
   - Reference: CDISC Pilot = 14 visits expected

6. **Activity Extraction** - All activities found?
   - Baseline: Need to count in gold standard

---

## Execution Plan

### Phase 1: Create Benchmark Test Set (1 hour)

#### Step 1.1: Prepare Test PDFs
```bash
# Use existing protocols
mkdir -p test_data/medium
cp input/CDISC_Pilot_Study.pdf test_data/medium/
```

#### Step 1.2: Create Gold Standards
```bash
# Run pipeline with ORIGINAL prompts (v2.0)
# First, ensure we're using originals
cp prompts/soa_extraction.yaml prompts/soa_extraction_current.yaml

# Run extraction
python main.py test_data/medium/CDISC_Pilot_Study.pdf --model gemini-2.5-pro

# Copy output as starting point
cp output/CDISC_Pilot_Study/9_reconciled_soa.json \
   test_data/medium/CDISC_Pilot_Study_gold.json
```

#### Step 1.3: Manually Verify Gold Standard
**CRITICAL:** Open `CDISC_Pilot_Study_gold.json` and verify:

✅ All 14 visits present (Visit 1/Week -2 through ET, RT)  
✅ All activities extracted  
✅ All timepoints have correct fields  
✅ All linkages correct (ActivityTimepoint → Activity, etc.)  
✅ Schema validates  

**This is the "perfect" extraction we're aiming for.**

---

### Phase 2: Baseline Benchmark (30 min)

#### Step 2.1: Ensure Original Prompts Active
```bash
# Backup optimized versions
cp prompts/*_optimized.yaml prompts/optimized_backup/

# Ensure originals are in use
ls prompts/*.yaml | grep -v optimized
```

#### Step 2.2: Run Baseline Benchmark
```bash
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro --output-dir benchmark_results
```

**Expected Output:**
```
======================================================================
SUMMARY STATISTICS
======================================================================
Total Test Cases: 1
Schema Validation: 1/1 (100.0%)
Average Completeness: XX.X%        ← BASELINE
Average Linkage Accuracy: XX.X%    ← BASELINE
Average Field Population: XX.X%    ← BASELINE
======================================================================
```

**Save these numbers!** This is our baseline.

---

### Phase 3: Optimized Benchmark (30 min)

#### Step 3.1: Deploy Optimized Prompts
```bash
# Backup originals
mkdir -p prompts/v2.0_baseline
cp prompts/soa_extraction.yaml prompts/v2.0_baseline/
cp prompts/vision_soa_extraction.yaml prompts/v2.0_baseline/
cp prompts/soa_reconciliation.yaml prompts/v2.0_baseline/
cp prompts/find_soa_pages.yaml prompts/v2.0_baseline/

# Deploy optimized versions
cp prompts/soa_extraction_optimized.yaml prompts/soa_extraction.yaml
cp prompts/vision_soa_extraction_optimized.yaml prompts/vision_soa_extraction.yaml
cp prompts/soa_reconciliation_optimized.yaml prompts/soa_reconciliation.yaml
cp prompts/find_soa_pages_optimized.yaml prompts/find_soa_pages.yaml
```

#### Step 3.2: Run Optimized Benchmark
```bash
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro --output-dir benchmark_results
```

**Expected Output:**
```
======================================================================
SUMMARY STATISTICS
======================================================================
Total Test Cases: 1
Schema Validation: 1/1 (100.0%)
Average Completeness: XX.X%        ← OPTIMIZED
Average Linkage Accuracy: XX.X%    ← OPTIMIZED
Average Field Population: XX.X%    ← OPTIMIZED
======================================================================
```

---

### Phase 4: Quantitative Comparison (15 min)

#### Step 4.1: Compare Results
```bash
python compare_benchmark_results.py \
  benchmark_results/benchmark_baseline.json \
  benchmark_results/benchmark_optimized.json
```

**Expected Output:**
```
======================================================================
DECISION RECOMMENDATION:
======================================================================
✅ ACCEPT - Solid improvement
   Average improvement across key metrics: +X.X%
======================================================================
```

#### Step 4.2: Decision Criteria

**ACCEPT if:**
- Completeness improved by ≥2%
- Linkage accuracy improved by ≥1%
- Field population improved by ≥2%
- NO regressions >1% on any metric

**CONSIDER if:**
- Mixed results (some better, some worse)
- Small improvement (<2% overall)
- Need more test cases to decide

**REJECT if:**
- Any metric regressed >2%
- Overall negative change
- Validation rate decreased

---

### Phase 5: Iterate Based on Results (1 hour)

#### If ACCEPTED:
1. ✅ Keep optimized prompts
2. ✅ Update version to v2.1 in main templates
3. ✅ Document improvements
4. ✅ Create more test cases for ongoing tracking

#### If REJECTED or MIXED:
1. 🔍 Analyze specific failures
2. 🔧 Manually adjust problem areas
3. 🧪 Re-benchmark
4. 🔄 Iterate

#### If NEED MORE DATA:
1. 📝 Add 2-3 more test cases
2. 📊 Run full benchmark suite
3. 🎯 Make decision with more confidence

---

## Enhanced Benchmarking Script

We need to enhance `benchmark_prompts.py` to measure USDM-specific metrics:

### Required Enhancements:
1. **Visit Count Accuracy**
   - Expected: Known from protocol
   - Actual: Count in JSON
   - Score: Actual / Expected

2. **Activity Count Accuracy**
   - Expected: From gold standard
   - Actual: Count in JSON
   - Score: Actual / Expected

3. **Linkage Validation**
   - Check all ActivityTimepoint.activityId references exist
   - Check all Encounter.activityTimepoints references exist
   - Score: Valid links / Total links

4. **Required Field Completeness**
   - PlannedTimepoint: 8 required fields
   - Activity: 3 required fields
   - Score: Filled fields / Required fields

5. **Schema Compliance**
   - Validate against USDM v4.0 schema
   - Score: Pass/Fail

---

## Proposed Timeline

### Today (3-4 hours total)

**Hour 1: Test Set Creation**
- ✅ Copy CDISC_Pilot_Study.pdf to test_data/
- ✅ Run pipeline with original prompts
- ✅ Manually create/verify gold standard

**Hour 2: Baseline Benchmark**
- ✅ Run benchmark with original prompts (v2.0)
- ✅ Record baseline metrics
- ✅ Save results

**Hour 3: Optimized Benchmark**
- ✅ Deploy optimized prompts (v2.1)
- ✅ Run benchmark with optimized prompts
- ✅ Record optimized metrics

**Hour 4: Analysis & Decision**
- ✅ Compare results quantitatively
- ✅ Accept/reject based on data
- ✅ Document findings
- ✅ Plan next iteration if needed

---

## Success Criteria

### Minimum Viable Success
- ✅ Test set with 1 gold standard created
- ✅ Baseline metrics measured
- ✅ Optimized metrics measured
- ✅ Data-driven decision made

### Ideal Success
- ✅ Test set with 3 gold standards
- ✅ Optimized prompts show +5% improvement
- ✅ No regressions
- ✅ Deployed with confidence

---

## Risk Mitigation

### Risk 1: Gold Standard Creation is Time-Consuming
**Mitigation:** Start with 1 well-verified case (CDISC Pilot)

### Risk 2: Optimized Prompts May Not Improve
**Mitigation:** That's okay! Data tells us to revert or iterate

### Risk 3: Pipeline Takes Long to Run
**Mitigation:** Use smaller test set initially, expand later

### Risk 4: Results are Inconclusive
**Mitigation:** Add more test cases until confidence is high

---

## Additional Enhancements (Beyond Initial Plan)

### 1. Reproducibility Testing
Run same test 3 times with same prompts to measure variance:
```bash
# Run 3 times
for i in 1 2 3; do
  python main.py test_data/medium/CDISC_Pilot_Study.pdf --model gemini-2.5-pro
  cp output/CDISC_Pilot_Study/9_reconciled_soa.json results/run_$i.json
done

# Measure variance
python measure_reproducibility.py results/run_*.json
```

### 2. Cross-Model Testing
Test if optimized prompts work better across models:
```bash
# Baseline
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro
python benchmark_prompts.py --test-set test_data/ --model gpt-4o

# Compare model performance
```

### 3. Execution Time Analysis
Measure if optimized prompts are faster/slower:
```bash
# Already tracked in benchmark_prompts.py
# Compare: avg_execution_time baseline vs optimized
```

### 4. Cost Analysis
Measure token usage differences:
```bash
# Log token counts
# Compare cost of baseline vs optimized
```

---

## Key Questions to Answer

1. **Do optimized prompts extract more complete USDM?**
   - Measure: Completeness Score

2. **Are cross-references more accurate?**
   - Measure: Linkage Accuracy

3. **Are required fields better populated?**
   - Measure: Field Population Rate

4. **Is schema validation better?**
   - Measure: Validation Pass Rate

5. **Is the improvement worth the longer prompts?**
   - Measure: ROI = Quality Gain / (Cost Increase + Time Increase)

---

## Deliverables

### At End of Execution
1. ✅ Test set with gold standards
2. ✅ Baseline benchmark results
3. ✅ Optimized benchmark results
4. ✅ Quantitative comparison report
5. ✅ Accept/reject decision with reasoning
6. ✅ Next steps documented

---

## Next Steps - Execution Sequence

**Ready to execute?** Here's the order:

1. ✅ **Enhance benchmark_prompts.py** with USDM metrics
2. ✅ **Create gold standard** for CDISC Pilot Study
3. ✅ **Run baseline benchmark** with original prompts
4. ✅ **Run optimized benchmark** with new prompts
5. ✅ **Compare & decide** based on data
6. ✅ **Deploy or iterate** based on results

---

**Status:** 📋 **PLAN READY**  
**Next Action:** Execute Phase 1 - Create test set with gold standard  
**Expected Outcome:** Data-driven decision on prompt optimization effectiveness  

**Shall we proceed with execution?**
