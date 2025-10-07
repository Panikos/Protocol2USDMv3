# Prompt Optimization - Quick Start Guide

**Get started with systematic prompt improvement in 30 minutes.**

---

## Step 1: Set Up Test Data (15 min)

### Create Test Directory Structure

```bash
mkdir -p test_data/simple
mkdir -p test_data/medium
mkdir -p test_data/complex
```

### Add Test PDFs

1. **Simple case** - Copy 1-2 basic protocols
   ```bash
   cp input/simple_protocol.pdf test_data/simple/
   ```

2. **Medium case** - Use CDISC Pilot Study
   ```bash
   cp input/CDISC_Pilot_Study.pdf test_data/medium/
   ```

3. **Complex case** - Use Alexion study
   ```bash
   cp input/Alexion_NCT04573309_Wilsons.pdf test_data/complex/
   ```

### Create Gold Standards

For each PDF, create a `<name>_gold.json`:

```bash
# Run pipeline manually to get baseline
python main.py test_data/simple/simple_protocol.pdf

# Copy output as gold standard (review and correct manually!)
cp output/simple_protocol/9_reconciled_soa.json \
   test_data/simple/simple_protocol_gold.json

# Manually review and fix any errors in the gold standard
```

**Critical:** Gold standards must be **manually verified** by domain expert!

---

## Step 2: Run Baseline Benchmark (10 min)

```bash
# Run benchmark on test set
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro
```

**Output:**
```
======================================================================
RUNNING BENCHMARK: 3 test cases
======================================================================

[TEST] simple_protocol.pdf
----------------------------------------------------------------------
✅ Validation: PASS
📊 Completeness: 87.5%
🔗 Linkage Accuracy: 95.0%
📝 Field Population: 82.3%
⏱️  Time: 45.2s

[TEST] CDISC_Pilot_Study.pdf
----------------------------------------------------------------------
✅ Validation: PASS
📊 Completeness: 78.2%
🔗 Linkage Accuracy: 91.0%
📝 Field Population: 75.8%
⏱️  Time: 89.7s

[TEST] Alexion_NCT04573309_Wilsons.pdf
----------------------------------------------------------------------
✅ Validation: PASS
📊 Completeness: 82.1%
🔗 Linkage Accuracy: 88.5%
📝 Field Population: 79.2%
⏱️  Time: 112.3s

======================================================================
SUMMARY STATISTICS
======================================================================
Total Test Cases: 3
Schema Validation: 3/3 (100.0%)
Average Completeness: 82.6%
Average Linkage Accuracy: 91.5%
Average Field Population: 79.1%
Average Execution Time: 82.4s
Errors: 0/3
======================================================================

RESULTS SAVED: benchmark_results/benchmark_20251005_233600.json
```

**Save this as your baseline!**

---

## Step 3: Identify Top Issue (5 min)

Look at the results:
- ❌ Field Population: 79.1% (lowest score)
- 🤔 Completeness: 82.6% (could be better)
- ✅ Linkage Accuracy: 91.5% (good)

**Top issue:** Field population rate is low  
**Why:** PlannedTimepoint fields are probably incomplete  
**Hypothesis:** Need better guidance on required fields

---

## Step 4: Make Improvement (Next session)

### Edit the Template

```bash
# Open the relevant template
vim prompts/vision_soa_extraction.yaml
```

**Add more specific field guidance:**

```yaml
metadata:
  version: "2.1"  # ← INCREMENT VERSION!
  changelog:
    - version: "2.1"
      date: "2025-10-06"
      changes: "Added explicit required fields checklist for PlannedTimepoint"

system_prompt: |
  ...existing content...
  
  **PlannedTimepoint Required Fields Checklist:**
  Before marking a PlannedTimepoint complete, ensure ALL these fields are present:
  - [ ] id (string)
  - [ ] name (string) - MUST match Encounter.name
  - [ ] instanceType (always "PlannedTimepoint")
  - [ ] encounterId (string reference)
  - [ ] value (number - e.g., -7, 0, 14)
  - [ ] valueLabel (string - e.g., "Day -7", "Week 2")
  - [ ] type (Code object with code & decode)
  - [ ] relativeToFrom (Code object)
  
  Missing any field? The output is INCOMPLETE.
```

### Re-run Benchmark

```bash
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro
```

### Compare Results

```bash
# Compare v2.0 vs v2.1
python compare_benchmark_results.py \
  benchmark_results/benchmark_20251005_233600.json \
  benchmark_results/benchmark_20251006_104500.json
```

**Expected output:**
```
COMPARISON: v2.0 → v2.1

Field Population: 79.1% → 86.3% (+7.2%) ✅ IMPROVED
Completeness: 82.6% → 83.1% (+0.5%) ✅ IMPROVED
Linkage Accuracy: 91.5% → 91.8% (+0.3%) ✅ MAINTAINED
Execution Time: 82.4s → 85.1s (+2.7s) ⚠️ SLIGHTLY SLOWER

DECISION: ✅ ACCEPT v2.1 (significant field population improvement)
```

---

## Quick Reference: Improvement Patterns

### Pattern 1: Add Explicit Constraints

**Problem:** LLM ignores rules  
**Solution:** Make rules VERY explicit

```yaml
# Before
system_prompt: "Extract the PlannedTimepoint fields"

# After
system_prompt: |
  CRITICAL RULES (DO NOT VIOLATE):
  1. PlannedTimepoint.name MUST equal Encounter.name (character-for-character match)
  2. value MUST be a number (use -7 for "Day -7", not the string "Day -7")
  3. type MUST be Code object: {"code": "C99073", "decode": "Fixed Reference"}
```

### Pattern 2: Add More Examples

**Problem:** LLM doesn't understand edge case  
**Solution:** Add example of that specific case

```yaml
user_prompt: |
  Example - Edge case with visit ranges:
  
  Input: "Day 2-3 Visit"
  
  Correct output:
  {
    "plannedTimepoints": [
      {"id": "pt_day2", "name": "Day 2-3 Visit", "value": 2, ...},
      {"id": "pt_day3", "name": "Day 2-3 Visit", "value": 3, ...}
    ]
  }
```

### Pattern 3: Add Validation Checklist

**Problem:** LLM forgets required fields  
**Solution:** Add explicit checklist

```yaml
system_prompt: |
  Before finalizing output, verify:
  - [ ] All PlannedTimepoints have: id, name, value, valueLabel, type
  - [ ] All names match between PlannedTimepoint and Encounter
  - [ ] All IDs are referenced correctly
  - [ ] No duplicate IDs exist
```

### Pattern 4: Reorder Instructions

**Problem:** LLM focuses on wrong thing  
**Solution:** Put most important rules FIRST

```yaml
# Before
system_prompt: |
  Extract the SoA table.
  Make sure to include all timepoints.
  CRITICAL: PlannedTimepoint.name must match Encounter.name.

# After  
system_prompt: |
  CRITICAL RULE #1: PlannedTimepoint.name MUST match Encounter.name exactly.
  
  Now extract the SoA table, ensuring:
  - All timepoints are included
  - All required fields are populated
```

---

## Metrics to Track

### Must Track
1. **Completeness Score** - Are all entities extracted?
2. **Field Population Rate** - Are required fields filled?
3. **Linkage Accuracy** - Are cross-references correct?

### Should Track
4. **Schema Validation** - Does output validate?
5. **Execution Time** - How long does it take?
6. **Error Rate** - How often does it fail?

### Nice to Track
7. **Token Usage** - What's the cost?
8. **Reproducibility** - Same input → same output?
9. **Provider Consistency** - Gemini ≈ OpenAI?

---

## Decision Framework

### When to ACCEPT a new version:

✅ **Major improvement** (>5%) in any primary metric  
✅ **No regression** (>2%) in other metrics  
✅ **Cost increase** <20%

### When to REJECT a new version:

❌ **No improvement** in primary metrics  
❌ **Regression** (>2%) in any metric  
❌ **Cost increase** >50% with <10% improvement

### When to ITERATE:

🔄 **Small improvement** (2-5%) but also small regression  
🔄 **Promising direction** but needs refinement  
🔄 **Mixed results** across test cases

---

## Troubleshooting

### "Benchmark takes too long"
- Use smaller test set for quick iterations
- Full test set for final validation only

### "Results are inconsistent"
- Set temperature=0 for reproducibility
- Run multiple times and average

### "Can't improve beyond 90%"
- Check if gold standards are actually correct
- May have hit model capability limit
- Consider fine-tuning or different model

### "Version changes break things"
- Use git branches for experiments
- Always keep baseline version as fallback
- Test on simple cases first

---

## Next Steps

1. ✅ **Run baseline** (done above)
2. 📊 **Analyze results** - What's the weakest area?
3. 💡 **Form hypothesis** - What change might help?
4. ✏️ **Edit template** - Implement change (increment version!)
5. 🧪 **Test** - Re-run benchmark
6. 📈 **Compare** - Better, worse, or same?
7. ✅ **Decide** - Accept, reject, or iterate
8. 🔄 **Repeat** - Every 2 weeks

---

## Resources

- **Full Strategy:** `PROMPT_OPTIMIZATION_STRATEGY.md`
- **Benchmark Tool:** `benchmark_prompts.py`
- **Templates:** `prompts/*.yaml`
- **Version History:** `prompts/VERSION_HISTORY.md` (create as needed)

---

**Goal:** Improve primary metrics to >95% within 6 months through systematic iteration.

**Remember:** Measure → Hypothesize → Change → Test → Decide → Repeat
