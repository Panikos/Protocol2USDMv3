# Prompt Optimization Strategy - Systematic Improvement Framework

**Date:** 2025-10-05  
**Status:** Implementation Ready  
**Goal:** Maximize quality, accuracy, and completeness through data-driven iteration

---

## Executive Summary

This strategy provides a systematic framework for iteratively improving all LLM prompts in the pipeline. By leveraging the newly implemented version tracking system, we can:

1. **Establish baselines** - Know current performance
2. **Make targeted changes** - Optimize specific aspects
3. **Measure impact** - Quantify improvements
4. **Track progress** - See trends over time
5. **Make data-driven decisions** - Choose what works best

---

## Phase 1: Establish Baseline Metrics (Week 1)

### Objective
Create a quantitative snapshot of current prompt performance to measure future improvements against.

### 1.1 Define Success Metrics

#### Primary Metrics (Quality)
1. **Schema Validation Rate**
   - % of outputs that pass USDM schema validation
   - Target: 100%
   - Current: Unknown (establish baseline)

2. **Entity Completeness Score**
   - % of expected entities extracted
   - Measured per entity type (Activities, Timepoints, Encounters, etc.)
   - Formula: `(Extracted / Expected) * 100`

3. **Linkage Accuracy**
   - % of cross-references that are correct
   - Examples: PlannedTimepoint → Encounter, Activity → Timepoint
   - Target: 100%

4. **Field Population Rate**
   - % of required fields populated correctly
   - Per entity type
   - Target: 100%

#### Secondary Metrics (Efficiency)
5. **Token Usage**
   - Average tokens per extraction
   - Cost per extraction
   - Track trends (want: stable or decreasing)

6. **Execution Time**
   - Average seconds per step
   - End-to-end pipeline time
   - Track trends

7. **Error Rate**
   - % of runs that fail
   - Error types and frequencies
   - Target: <5%

#### Tertiary Metrics (Consistency)
8. **Reproducibility Score**
   - Run same input 3x, compare outputs
   - Measure similarity between runs
   - Target: >95% similarity

9. **Provider Consistency**
   - Compare Gemini vs OpenAI on same input
   - Should be similar now that prompts are unified
   - Target: >90% similarity

### 1.2 Create Test Set

**Curate Representative PDFs:**
```
test_data/
├── simple/              # 2-3 visits, basic table
│   ├── example1.pdf
│   └── example1_gold.json  # Manual gold standard
├── medium/              # 5-10 visits, standard complexity
│   ├── CDISC_Pilot_Study.pdf
│   └── CDISC_Pilot_Study_gold.json
├── complex/             # 10+ visits, nested groups
│   ├── Alexion_NCT04573309.pdf
│   └── Alexion_NCT04573309_gold.json
└── edge_cases/          # Unusual formatting
    ├── multipage_table.pdf
    └── footnotes_heavy.pdf
```

**Gold Standard Requirements:**
- Manually verified by domain expert
- Complete and accurate
- Represents "perfect" extraction
- Use for comparison

### 1.3 Run Baseline Tests

**Command:**
```bash
# Run entire test set with current prompts
python benchmark_prompts.py --test-set test_data/ --output baseline_results.json
```

**Collect:**
- All 9 metrics per prompt
- Per PDF and aggregated
- Current prompt versions used
- Timestamp and model info

### 1.4 Baseline Report

**Generate:**
```
BASELINE_REPORT_2025_10_05.md
├── Overall Performance
│   ├── Validation rate: 87%
│   ├── Completeness: 82%
│   └── Linkage accuracy: 91%
├── Per-Prompt Breakdown
│   ├── Vision extraction: 78% completeness
│   ├── Text extraction: 85% completeness
│   ├── Reconciliation: 95% accuracy
│   └── Find SoA: 100% accuracy
└── Problem Areas Identified
    ├── PlannedTimepoint fields often incomplete
    ├── ActivityGroups sometimes missing
    └── Epoch linkages occasionally wrong
```

---

## Phase 2: Systematic Improvement (Weeks 2-6)

### 2.1 Prioritization Framework

**Priority Score = Impact × Frequency × Ease**

| Issue | Impact | Frequency | Ease | Score | Priority |
|-------|--------|-----------|------|-------|----------|
| Missing PlannedTimepoint.value | High (10) | High (9) | Medium (6) | 540 | 🔴 P0 |
| Incomplete ActivityGroups | Med (7) | Med (5) | Easy (8) | 280 | 🟡 P1 |
| Wrong Epoch linkages | High (9) | Low (3) | Hard (4) | 108 | 🟢 P2 |

**Focus on P0 issues first, then P1, then P2.**

### 2.2 Improvement Cycle (2-Week Sprints)

#### Sprint Structure

**Week 1: Hypothesis & Implementation**
1. **Monday: Analyze**
   - Review baseline report
   - Identify top issue (highest priority score)
   - Form hypothesis: "If we change X, Y will improve"

2. **Tuesday-Wednesday: Design**
   - Draft improved prompt (v2.1)
   - Peer review with team
   - Document changes in YAML changelog

3. **Thursday: Implement**
   - Update YAML template
   - Increment version number
   - Commit: `git commit -m "feat: improve PlannedTimepoint guidance (v2.1)"`

4. **Friday: Test**
   - Run on test set
   - Compare to baseline
   - Quick validation

**Week 2: Validation & Decision**
5. **Monday: Extended Testing**
   - Run on additional PDFs
   - Test edge cases
   - Collect full metrics

6. **Tuesday: Analysis**
   - Compare v2.1 vs v2.0
   - Statistical significance testing
   - Cost/benefit analysis

7. **Wednesday: Decision**
   - ✅ **Accept:** Merge if improved
   - ❌ **Reject:** Revert if worse
   - 🤔 **Iterate:** Refine if promising

8. **Thursday-Friday: Documentation**
   - Update metrics dashboard
   - Document learnings
   - Plan next sprint

### 2.3 Improvement Techniques Library

**Technique Catalog:**

#### A. Structural Improvements
```yaml
# Before: Generic instruction
system_prompt: |
  Extract the Schedule of Activities.

# After: Specific step-by-step
system_prompt: |
  Extract the Schedule of Activities following these steps:
  1. Identify all visit columns
  2. Extract activity rows
  3. Map checkmarks to ActivityTimepoints
  4. Link to appropriate Encounter
```

#### B. Example Enhancement
```yaml
# Add more examples for problematic patterns
user_prompt: |
  Example of correct PlannedTimepoint:
  {correct_example}
  
  Example of incorrect PlannedTimepoint (DO NOT DO THIS):
  {incorrect_example}
```

#### C. Constraint Clarification
```yaml
# Add explicit constraints
system_prompt: |
  CRITICAL RULES:
  1. PlannedTimepoint.name MUST match Encounter.name exactly
  2. value field MUST be numeric (use -7 for "Day -7")
  3. type MUST use Code object: {"code": "...", "decode": "..."}
```

#### D. Output Format Guidance
```yaml
# Add schema snippets
user_prompt: |
  Your output must match this structure:
  ```json
  {
    "plannedTimepoints": [{
      "id": "string",
      "name": "string",     # MUST match encounter name
      "value": -7,          # MUST be number
      ...
    }]
  }
  ```
```

#### E. Context Enrichment
```yaml
# Provide more background
system_prompt: |
  Background: In clinical trials, PlannedTimepoints represent
  specific moments when activities occur. They link to Encounters
  (visit windows) and have numeric values for scheduling.
```

---

## Phase 3: A/B Testing Framework (Ongoing)

### 3.1 Controlled Experiments

**Setup:**
```python
# benchmark_prompts.py
def ab_test(pdf_path, prompt_a, prompt_b, n_runs=5):
    """Compare two prompt versions on same input."""
    results_a = []
    results_b = []
    
    for i in range(n_runs):
        # Test prompt A
        output_a = run_pipeline(pdf_path, template_version=prompt_a)
        results_a.append(evaluate(output_a))
        
        # Test prompt B
        output_b = run_pipeline(pdf_path, template_version=prompt_b)
        results_b.append(evaluate(output_b))
    
    return compare_results(results_a, results_b)
```

**Statistical Testing:**
```python
from scipy import stats

# Check if improvement is significant
t_stat, p_value = stats.ttest_ind(results_a, results_b)
is_significant = p_value < 0.05
```

### 3.2 Champion/Challenger Pattern

**Strategy:**
1. **Champion:** Current best version (v2.0)
2. **Challenger:** New experimental version (v2.1)
3. **Split traffic:** 80% Champion, 20% Challenger
4. **Monitor:** Track metrics for both
5. **Promote:** Challenger → Champion if better

**Implementation:**
```python
def select_template(prompt_name, experiment_mode=True):
    """Randomly select champion or challenger."""
    if not experiment_mode:
        return load_champion(prompt_name)
    
    # 80/20 split
    if random.random() < 0.8:
        return load_champion(prompt_name)  # v2.0
    else:
        return load_challenger(prompt_name)  # v2.1
```

---

## Phase 4: Automation & Tooling (Week 7)

### 4.1 Automated Benchmarking Pipeline

**Create:** `benchmark_prompts.py`

```python
#!/usr/bin/env python3
"""
Automated prompt benchmarking system.

Usage:
    python benchmark_prompts.py --test-set test_data/ --compare-versions 2.0 2.1
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

class PromptBenchmark:
    def __init__(self, test_set_dir, output_dir="benchmark_results"):
        self.test_set = self.load_test_set(test_set_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def run_full_benchmark(self, prompt_versions):
        """Run complete benchmark across all prompts and versions."""
        results = {}
        
        for pdf_path, gold_standard in self.test_set:
            for version in prompt_versions:
                print(f"Testing {pdf_path.name} with prompts v{version}...")
                
                # Run pipeline
                output = self.run_pipeline(pdf_path, version)
                
                # Calculate metrics
                metrics = self.calculate_metrics(output, gold_standard)
                
                # Store results
                key = f"{pdf_path.stem}_v{version}"
                results[key] = metrics
        
        # Generate report
        self.generate_report(results)
        return results
    
    def calculate_metrics(self, output, gold_standard):
        """Calculate all 9 core metrics."""
        return {
            "validation_pass": self.check_schema_validation(output),
            "completeness_score": self.calculate_completeness(output, gold_standard),
            "linkage_accuracy": self.check_linkages(output, gold_standard),
            "field_population": self.check_field_population(output),
            "token_usage": self.get_token_count(output),
            "execution_time": self.get_execution_time(),
            "error_occurred": self.check_errors(),
            "reproducibility": self.test_reproducibility(output),
            "provider_consistency": self.test_providers(output),
        }
    
    def generate_report(self, results):
        """Generate markdown report with visualizations."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"benchmark_report_{timestamp}.md"
        
        with open(report_path, "w") as f:
            f.write("# Prompt Benchmark Report\n\n")
            f.write(f"**Date:** {datetime.now()}\n\n")
            
            # Overall statistics
            f.write("## Overall Performance\n\n")
            f.write(self.format_statistics(results))
            
            # Per-prompt breakdown
            f.write("## Per-Prompt Analysis\n\n")
            f.write(self.format_per_prompt_analysis(results))
            
            # Improvements/regressions
            f.write("## Changes from Baseline\n\n")
            f.write(self.format_deltas(results))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-set", required=True)
    parser.add_argument("--compare-versions", nargs="+", default=["2.0"])
    args = parser.parse_args()
    
    benchmark = PromptBenchmark(args.test_set)
    results = benchmark.run_full_benchmark(args.compare_versions)
```

### 4.2 Metrics Dashboard

**Create:** `metrics_dashboard.py` (Streamlit app)

```python
import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Prompt Optimization Dashboard")

# Load all benchmark results
results = load_all_results("benchmark_results/")

# Metrics over time
st.header("Metrics Trends")
fig = px.line(results, x="date", y="completeness_score", color="prompt_name")
st.plotly_chart(fig)

# Version comparison
st.header("Version Comparison")
comparison = compare_versions(results, ["2.0", "2.1", "2.2"])
st.dataframe(comparison)

# Detailed drill-down
st.header("Detailed Analysis")
selected_prompt = st.selectbox("Select prompt", ["vision", "text", "reconciliation"])
st.write(get_detailed_metrics(results, selected_prompt))
```

### 4.3 Continuous Integration Checks

**Add to CI/CD:** `.github/workflows/prompt_validation.yml`

```yaml
name: Validate Prompts

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Validate YAML templates
        run: python verify_prompt_migration.py
      
      - name: Run mini benchmark
        run: |
          python benchmark_prompts.py \
            --test-set test_data/simple/ \
            --compare-versions latest
      
      - name: Check for regressions
        run: python check_regressions.py
```

---

## Phase 5: Advanced Techniques (Weeks 8+)

### 5.1 Chain-of-Thought Prompting

**Technique:** Ask LLM to show reasoning before answering.

```yaml
system_prompt: |
  Before generating the final JSON, first think through:
  1. What visits are mentioned?
  2. What activities are listed?
  3. How do they map to timepoints?
  
  Output your reasoning in <thinking> tags, then output JSON.
```

**Benefit:** Often improves accuracy, helps debug issues.

### 5.2 Few-Shot Learning Enhancement

**Current:** 1 example in prompt  
**Improved:** 3-5 diverse examples

```yaml
user_prompt: |
  Example 1 - Simple case:
  {simple_example}
  
  Example 2 - With visit windows:
  {windowed_example}
  
  Example 3 - Multiple epochs:
  {complex_example}
```

### 5.3 Self-Consistency Voting

**Technique:** Generate N outputs, choose most common.

```python
def self_consistency(pdf_path, n=5):
    """Generate N extractions, vote on best."""
    outputs = []
    for i in range(n):
        output = run_extraction(pdf_path, temperature=0.7)  # Higher temp for diversity
        outputs.append(output)
    
    # Vote on each field
    final_output = vote_on_outputs(outputs)
    return final_output
```

### 5.4 Active Learning Loop

**Concept:** Focus efforts where model struggles most.

1. **Identify failure patterns**
   - Which PDFs consistently fail?
   - Which entity types are hardest?

2. **Create targeted examples**
   - Add examples that address failures
   - Put in prompt or fine-tuning data

3. **Iterative refinement**
   - Test → Identify failures → Add examples → Repeat

### 5.5 Prompt Compression

**Goal:** Reduce tokens without losing quality.

**Techniques:**
- Remove redundant instructions
- Use abbreviations in schema
- Compress examples

**Validation:** Ensure metrics don't regress.

---

## Phase 6: Long-Term Tracking (Ongoing)

### 6.1 Metrics Database

**Schema:**
```sql
CREATE TABLE benchmark_runs (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    prompt_name TEXT,
    prompt_version TEXT,
    model_name TEXT,
    pdf_name TEXT,
    
    -- Primary metrics
    validation_pass BOOLEAN,
    completeness_score FLOAT,
    linkage_accuracy FLOAT,
    field_population_rate FLOAT,
    
    -- Secondary metrics
    token_usage INTEGER,
    execution_time_seconds FLOAT,
    error_occurred BOOLEAN,
    
    -- Tertiary metrics
    reproducibility_score FLOAT,
    provider_consistency_score FLOAT,
    
    -- Metadata
    git_commit TEXT,
    notes TEXT
);
```

### 6.2 Monthly Reports

**Automated generation:** 1st of each month

```markdown
# Monthly Prompt Performance Report - November 2025

## Summary
- Overall completeness: 94% (+7% vs Oct)
- Vision extraction: 92% (+5% vs Oct)
- Text extraction: 96% (+9% vs Oct)
- Reconciliation: 98% (+2% vs Oct)

## Improvements Made
- v2.2: Enhanced PlannedTimepoint guidance → +5% completeness
- v2.3: Added ActivityGroup examples → +3% completeness
- v2.4: Improved error handling → -40% error rate

## Next Month Focus
- Address remaining PlannedTimepoint edge cases
- Improve Epoch linkage accuracy
- Reduce token usage by 10%
```

### 6.3 Version History Tracking

**Maintain:** `prompts/VERSION_HISTORY.md`

```markdown
# Prompt Version History

## vision_soa_extraction.yaml

### v2.4 (2025-11-15)
- **Change:** Added explicit note about footnote markers
- **Reason:** 12% of runs had footnote-related errors
- **Impact:** Error rate: 5% → 2% (-60%)
- **Metrics:** Completeness 91% → 94% (+3%)

### v2.3 (2025-11-01)
- **Change:** Enhanced ActivityGroup examples
- **Reason:** 23% of runs missing groups
- **Impact:** Group detection: 77% → 92% (+15%)
- **Metrics:** Completeness 88% → 91% (+3%)

### v2.2 (2025-10-15)
...
```

---

## Implementation Timeline

### Weeks 1-2: Foundation
- [ ] Create test set with gold standards
- [ ] Implement benchmark_prompts.py
- [ ] Run baseline tests
- [ ] Generate baseline report

### Weeks 3-4: Sprint 1
- [ ] Identify top issue (P0)
- [ ] Draft improved prompt (v2.1)
- [ ] Test and compare
- [ ] Make go/no-go decision

### Weeks 5-6: Sprint 2
- [ ] Address next issue (P1)
- [ ] Draft improved prompt (v2.2)
- [ ] Test and compare
- [ ] Make go/no-go decision

### Week 7: Automation
- [ ] Build metrics dashboard
- [ ] Set up CI/CD checks
- [ ] Automate monthly reports

### Weeks 8+: Continuous Improvement
- [ ] Monthly sprints
- [ ] Quarterly reviews
- [ ] Advanced techniques as needed

---

## Success Criteria

### Short-term (3 months)
- [x] Version tracking system in place ✅
- [ ] Baseline established
- [ ] 3+ improvement sprints completed
- [ ] Metrics improved by 10%+

### Medium-term (6 months)
- [ ] All primary metrics >90%
- [ ] Automated benchmarking in place
- [ ] 10+ version iterations per prompt
- [ ] Documented best practices library

### Long-term (12 months)
- [ ] All primary metrics >95%
- [ ] <2% error rate
- [ ] Consistent high quality
- [ ] Industry-leading performance

---

## Key Principles

### 1. Data-Driven
✅ **Always measure** before and after changes  
✅ **Use statistics** to confirm improvements  
✅ **Track trends** over time

### 2. Iterative
✅ **Small changes** are easier to validate  
✅ **Quick cycles** enable faster learning  
✅ **Continuous improvement** never ends

### 3. Scientific
✅ **Form hypotheses** before changing  
✅ **Control variables** in experiments  
✅ **Document everything** for reproducibility

### 4. User-Focused
✅ **Quality matters** more than speed  
✅ **Accuracy is critical** in healthcare  
✅ **Completeness prevents** downstream issues

---

## Tools & Resources Needed

### Infrastructure
- [ ] Test PDF collection (diverse, representative)
- [ ] Gold standard JSONs (manually verified)
- [ ] Benchmark script (benchmark_prompts.py)
- [ ] Metrics dashboard (Streamlit or similar)
- [ ] Version control (Git + GitHub)

### Skills
- [ ] Prompt engineering best practices
- [ ] Statistical analysis (Python/R)
- [ ] Domain expertise (clinical trials)
- [ ] Software development

### Time Commitment
- **Initial setup:** 2 weeks
- **Per sprint:** 1-2 weeks
- **Ongoing monitoring:** 2 hours/week
- **Monthly reviews:** 4 hours/month

---

## Conclusion

This strategy provides a **systematic, data-driven approach** to prompt optimization. By:

1. ✅ **Establishing baselines** - Know where you are
2. ✅ **Measuring everything** - Track what matters
3. ✅ **Iterating carefully** - Make incremental improvements
4. ✅ **Testing rigorously** - Validate before deploying
5. ✅ **Tracking long-term** - See the big picture

You can **continuously improve prompt quality** while maintaining production stability.

**Next Step:** Begin Phase 1 - Establish baseline metrics.

---

**Framework Status:** ✅ Ready for Implementation  
**Estimated ROI:** 20-30% quality improvement in 6 months  
**Risk:** Low (all changes version-tracked and reversible)
