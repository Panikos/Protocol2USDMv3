#!/usr/bin/env python3
"""
Compare Benchmark Results

Compare two benchmark runs to see improvements or regressions.

Usage:
    python compare_benchmark_results.py baseline.json optimized.json
    python compare_benchmark_results.py benchmark_results/benchmark_*.json --latest 2
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure UTF-8 output
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def load_results(filepath: str) -> Dict:
    """Load benchmark results from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_aggregate_metrics(results: Dict) -> Dict:
    """Calculate aggregate metrics from test cases including USDM-specific metrics."""
    test_cases = results.get("test_cases", {})
    
    if not test_cases:
        return {}
    
    total = len(test_cases)
    
    metrics = {
        "total_cases": total,
        "validation_rate": sum(1 for m in test_cases.values() if m.get("validation_pass", False)) / total * 100,
        "avg_completeness": sum(m.get("completeness_score", 0) for m in test_cases.values()) / total,
        "avg_linkage_accuracy": sum(m.get("linkage_accuracy", 0) for m in test_cases.values()) / total,
        "avg_field_population": sum(m.get("field_population_rate", 0) for m in test_cases.values()) / total,
        "avg_execution_time": sum(m.get("execution_time_seconds", 0) for m in test_cases.values()) / total,
        "error_rate": sum(1 for m in test_cases.values() if m.get("error_occurred", False)) / total * 100,
        # USDM-specific metrics
        "avg_visit_accuracy": sum(m.get("usdm_metrics", {}).get("visit_count_accuracy", 0) for m in test_cases.values()) / total,
        "avg_activity_accuracy": sum(m.get("usdm_metrics", {}).get("activity_count_accuracy", 0) for m in test_cases.values()) / total,
        "avg_at_completeness": sum(m.get("usdm_metrics", {}).get("activitytimepoint_completeness", 0) for m in test_cases.values()) / total,
    }
    
    return metrics


def compare_metrics(baseline: Dict, optimized: Dict) -> Dict:
    """Compare two sets of metrics."""
    comparison = {}
    
    for key in baseline.keys():
        if key == "total_cases":
            comparison[key] = {
                "baseline": baseline[key],
                "optimized": optimized.get(key, 0),
                "change": 0,
                "change_pct": 0
            }
            continue
        
        baseline_val = baseline[key]
        optimized_val = optimized.get(key, 0)
        change = optimized_val - baseline_val
        change_pct = (change / baseline_val * 100) if baseline_val != 0 else 0
        
        comparison[key] = {
            "baseline": baseline_val,
            "optimized": optimized_val,
            "change": change,
            "change_pct": change_pct
        }
    
    return comparison


def print_comparison(comparison: Dict, baseline_file: str, optimized_file: str):
    """Print formatted comparison."""
    print("\n" + "="*70)
    print("BENCHMARK COMPARISON")
    print("="*70)
    print(f"Baseline:  {Path(baseline_file).name}")
    print(f"Optimized: {Path(optimized_file).name}")
    print("="*70 + "\n")
    
    # Define metric display names and whether higher is better
    metrics_info = {
        "validation_rate": ("Schema Validation Rate", True, "%"),
        "avg_completeness": ("Average Completeness", True, "%"),
        "avg_linkage_accuracy": ("Average Linkage Accuracy", True, "%"),
        "avg_field_population": ("Average Field Population", True, "%"),
        "avg_visit_accuracy": ("Visit Count Accuracy (USDM)", True, "%"),
        "avg_activity_accuracy": ("Activity Count Accuracy (USDM)", True, "%"),
        "avg_at_completeness": ("ActivityTimepoint Completeness (USDM)", True, "%"),
        "avg_execution_time": ("Average Execution Time", False, "s"),
        "error_rate": ("Error Rate", False, "%"),
    }
    
    print("📊 METRIC CHANGES:\n")
    
    for key, info in metrics_info.items():
        if key not in comparison:
            continue
        
        name, higher_is_better, unit = info
        data = comparison[key]
        
        baseline_val = data["baseline"]
        optimized_val = data["optimized"]
        change = data["change"]
        change_pct = data["change_pct"]
        
        # Determine if this is an improvement
        if higher_is_better:
            is_improvement = change > 0
            is_regression = change < 0
        else:
            is_improvement = change < 0
            is_regression = change > 0
        
        # Format values
        if unit == "%":
            baseline_str = f"{baseline_val:.1f}%"
            optimized_str = f"{optimized_val:.1f}%"
        else:
            baseline_str = f"{baseline_val:.1f}{unit}"
            optimized_str = f"{optimized_val:.1f}{unit}"
        
        change_str = f"{change:+.1f}{unit}" if unit != "%" else f"{change:+.1f}%"
        change_pct_str = f"({change_pct:+.1f}%)"
        
        # Status emoji
        if abs(change_pct) < 0.5:
            status = "➖"  # No significant change
            verdict = "UNCHANGED"
        elif is_improvement:
            if abs(change_pct) > 5:
                status = "✅"
                verdict = "IMPROVED"
            else:
                status = "✅"
                verdict = "IMPROVED"
        else:
            if abs(change_pct) > 2:
                status = "❌"
                verdict = "REGRESSED"
            else:
                status = "⚠️ "
                verdict = "SLIGHT REGRESSION"
        
        print(f"{status} {name}:")
        print(f"    Baseline:  {baseline_str}")
        print(f"    Optimized: {optimized_str}")
        print(f"    Change:    {change_str} {change_pct_str} - {verdict}")
        print()
    
    # Overall decision
    print("="*70)
    print("DECISION RECOMMENDATION:")
    print("="*70)
    
    # Calculate overall score change (including USDM metrics)
    key_metrics = [
        "avg_completeness", "avg_linkage_accuracy", "avg_field_population",
        "avg_visit_accuracy", "avg_activity_accuracy", "avg_at_completeness"
    ]
    available_metrics = [k for k in key_metrics if k in comparison]
    total_improvement = sum(comparison[k]["change"] for k in available_metrics)
    avg_improvement = total_improvement / len(available_metrics) if available_metrics else 0
    
    # Check for regressions
    significant_regressions = []
    for key in available_metrics:
        if comparison[key]["change"] < -2:
            significant_regressions.append(key)
    
    if significant_regressions:
        print("❌ REJECT - Significant regressions detected:")
        for key in significant_regressions:
            print(f"   - {metrics_info[key][0]}: {comparison[key]['change']:.1f}%")
    elif avg_improvement > 5:
        print("✅ ACCEPT - Major improvement!")
        print(f"   Average improvement across key metrics: +{avg_improvement:.1f}%")
    elif avg_improvement > 2:
        print("✅ ACCEPT - Solid improvement")
        print(f"   Average improvement across key metrics: +{avg_improvement:.1f}%")
    elif avg_improvement > 0.5:
        print("🔄 CONSIDER - Minor improvement")
        print(f"   Average improvement across key metrics: +{avg_improvement:.1f}%")
        print("   Test on more cases before deciding")
    elif avg_improvement > -0.5:
        print("➖ NEUTRAL - No significant change")
        print("   Consider other factors or try different optimization")
    else:
        print("❌ REJECT - Overall regression")
        print(f"   Average change across key metrics: {avg_improvement:.1f}%")
    
    print("="*70 + "\n")


def compare_per_test_case(baseline_results: Dict, optimized_results: Dict):
    """Compare results per test case."""
    baseline_cases = baseline_results.get("test_cases", {})
    optimized_cases = optimized_results.get("test_cases", {})
    
    common_cases = set(baseline_cases.keys()) & set(optimized_cases.keys())
    
    if not common_cases:
        print("⚠️  No common test cases found for comparison")
        return
    
    print("\n" + "="*70)
    print("PER-TEST-CASE ANALYSIS")
    print("="*70 + "\n")
    
    for case_name in sorted(common_cases):
        baseline = baseline_cases[case_name]
        optimized = optimized_cases[case_name]
        
        print(f"📄 {case_name}")
        
        # Completeness
        b_comp = baseline.get("completeness_score", 0)
        o_comp = optimized.get("completeness_score", 0)
        comp_change = o_comp - b_comp
        
        if abs(comp_change) > 5:
            status = "✅" if comp_change > 0 else "❌"
            print(f"   {status} Completeness: {b_comp:.1f}% → {o_comp:.1f}% ({comp_change:+.1f}%)")
        
        # Field population
        b_field = baseline.get("field_population_rate", 0)
        o_field = optimized.get("field_population_rate", 0)
        field_change = o_field - b_field
        
        if abs(field_change) > 5:
            status = "✅" if field_change > 0 else "❌"
            print(f"   {status} Field Population: {b_field:.1f}% → {o_field:.1f}% ({field_change:+.1f}%)")
        
        print()


def main():
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument("baseline", help="Baseline results JSON file")
    parser.add_argument("optimized", nargs="?", help="Optimized results JSON file")
    parser.add_argument("--latest", type=int, help="Compare latest N results")
    parser.add_argument("--detailed", action="store_true", help="Show per-test-case comparison")
    
    args = parser.parse_args()
    
    # Handle --latest flag
    if args.latest:
        results_dir = Path(args.baseline).parent if Path(args.baseline).is_file() else Path(args.baseline)
        all_results = sorted(results_dir.glob("benchmark_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if len(all_results) < args.latest:
            print(f"❌ Only {len(all_results)} results found, need {args.latest}")
            return 1
        
        files_to_compare = all_results[:args.latest]
        baseline_file = str(files_to_compare[1])  # Older
        optimized_file = str(files_to_compare[0])  # Newer
    else:
        if not args.optimized:
            print("❌ Must provide both baseline and optimized files, or use --latest")
            return 1
        
        baseline_file = args.baseline
        optimized_file = args.optimized
    
    # Load results
    try:
        baseline_results = load_results(baseline_file)
        optimized_results = load_results(optimized_file)
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return 1
    
    # Calculate aggregate metrics
    baseline_metrics = calculate_aggregate_metrics(baseline_results)
    optimized_metrics = calculate_aggregate_metrics(optimized_results)
    
    if not baseline_metrics or not optimized_metrics:
        print("❌ Could not calculate metrics from results")
        return 1
    
    # Compare
    comparison = compare_metrics(baseline_metrics, optimized_metrics)
    
    # Print comparison
    print_comparison(comparison, baseline_file, optimized_file)
    
    # Detailed per-case comparison
    if args.detailed:
        compare_per_test_case(baseline_results, optimized_results)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
