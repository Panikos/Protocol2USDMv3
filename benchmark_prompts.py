#!/usr/bin/env python3
"""
Automated Prompt Benchmarking System

Systematically test prompt versions and measure quality improvements.

Usage:
    # Run baseline
    python benchmark_prompts.py --test-set test_data/ --output baseline.json
    
    # Compare versions
    python benchmark_prompts.py --test-set test_data/ --compare-versions 2.0 2.1
    
    # Full report
    python benchmark_prompts.py --test-set test_data/ --report-only
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import subprocess

# Prompt optimization integration
try:
    from prompt_optimizer import PromptOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    print("[WARNING] prompt_optimizer not available")
    OPTIMIZER_AVAILABLE = False

class PromptBenchmark:
    """Benchmark prompt versions systematically."""
    
    def __init__(self, test_set_dir: str, output_dir: str = "benchmark_results"):
        self.test_set_dir = Path(test_set_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Ensure UTF-8 output
        if sys.platform == 'win32':
            sys.stdout.reconfigure(encoding='utf-8')
    
    def load_test_set(self) -> List[Tuple[Path, Path]]:
        """Load all PDFs and their gold standard JSONs."""
        test_cases = []
        
        for pdf_path in self.test_set_dir.rglob("*.pdf"):
            # Look for corresponding gold standard
            gold_path = pdf_path.with_name(pdf_path.stem + "_gold.json")
            
            if gold_path.exists():
                test_cases.append((pdf_path, gold_path))
                print(f"✅ Found test case: {pdf_path.name}")
            else:
                print(f"⚠️  No gold standard for: {pdf_path.name}")
        
        if not test_cases:
            print(f"❌ No test cases found in {self.test_set_dir}")
            print("Expected: <name>.pdf + <name>_gold.json")
        
        return test_cases
    
    def run_pipeline(self, pdf_path: Path, model: str = "gemini-2.5-pro") -> Dict:
        """Run the full extraction pipeline on a PDF."""
        print(f"[INFO] Running pipeline on {pdf_path.name} with {model}...")
        
        try:
            # Run main pipeline
            result = subprocess.run(
                ["python", "main.py", str(pdf_path), "--model", model],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600  # 10 minute timeout
            )
            
            # Load output (check for file existence first, regardless of return code)
            output_dir = Path("output") / pdf_path.stem
            reconciled_path = output_dir / "9_reconciled_soa.json"
            
            if reconciled_path.exists():
                with open(reconciled_path, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)
                    # Validate it's not empty
                    if output_data and "study" in output_data:
                        print(f"✅ Pipeline completed successfully")
                        return output_data
                    else:
                        return {"error": "Output file is empty or invalid"}
            else:
                # File doesn't exist - check return code for error details
                if result.returncode != 0:
                    print(f"❌ Pipeline failed with return code {result.returncode}")
                    return {"error": f"Return code {result.returncode}: {result.stderr[:500]}"}
                else:
                    return {"error": "Output file not found despite success code"}
        
        except subprocess.TimeoutExpired:
            return {"error": "Pipeline timeout (>10 minutes)"}
        except Exception as e:
            return {"error": str(e)}
    
    def calculate_completeness(self, output: Dict, gold: Dict) -> float:
        """Calculate entity completeness score (USDM-specific)."""
        try:
            timeline = output.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            gold_timeline = gold.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            
            scores = []
            
            # Check each entity type with weights based on importance
            entity_weights = {
                "activities": 1.5,  # Most important
                "plannedTimepoints": 1.5,  # Most important (visits)
                "activityTimepoints": 1.0,  # Important for mapping
                "encounters": 0.8,
                "epochs": 0.5
            }
            
            for entity_type, weight in entity_weights.items():
                output_count = len(timeline.get(entity_type, []))
                gold_count = len(gold_timeline.get(entity_type, []))
                
                if gold_count > 0:
                    # Calculate score (penalize both under and over extraction)
                    if output_count <= gold_count:
                        score = (output_count / gold_count) * 100
                    else:
                        # Penalty for over-extraction (hallucination)
                        score = 100 - ((output_count - gold_count) / gold_count) * 10
                        score = max(score, 0)
                    
                    scores.append(score * weight)
            
            return sum(scores) / sum(entity_weights.values()) if scores else 0.0
        
        except Exception as e:
            print(f"⚠️  Completeness calculation error: {e}")
            return 0.0
    
    def check_schema_validation(self, output: Dict) -> bool:
        """Check if output validates against USDM schema."""
        try:
            # Run validator
            result = subprocess.run(
                ["python", "validate_schema.py", "--json-str", json.dumps(output)],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return result.returncode == 0
        except:
            return False
    
    def check_linkages(self, output: Dict, gold: Dict) -> float:
        """Check accuracy of cross-references (comprehensive USDM linkages)."""
        try:
            timeline = output.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            
            # Build ID indexes
            activities = {a["id"]: a for a in timeline.get("activities", [])}
            planned_timepoints = {pt["id"]: pt for pt in timeline.get("plannedTimepoints", [])}
            encounters = {e["id"]: e for e in timeline.get("encounters", [])}
            
            correct_linkages = 0
            total_linkages = 0
            
            # Check 1: PlannedTimepoint → Encounter linkages
            for pt in timeline.get("plannedTimepoints", []):
                enc_id = pt.get("encounterId")
                if enc_id:
                    total_linkages += 1
                    if enc_id in encounters:
                        correct_linkages += 1
            
            # Check 2: ActivityTimepoint → Activity linkages (CRITICAL)
            for at in timeline.get("activityTimepoints", []):
                act_id = at.get("activityId")
                if act_id:
                    total_linkages += 1
                    if act_id in activities:
                        correct_linkages += 1
            
            # Check 3: ActivityTimepoint → PlannedTimepoint linkages
            for at in timeline.get("activityTimepoints", []):
                pt_id = at.get("timepointId")
                if pt_id:
                    total_linkages += 1
                    if pt_id in planned_timepoints:
                        correct_linkages += 1
            
            # Check 4: Encounter → ActivityTimepoint linkages
            for enc in timeline.get("encounters", []):
                for at_id in enc.get("activityTimepoints", []):
                    total_linkages += 1
                    # Check if this AT exists
                    at_exists = any(at["id"] == at_id for at in timeline.get("activityTimepoints", []))
                    if at_exists:
                        correct_linkages += 1
            
            if total_linkages == 0:
                return 100.0  # No linkages to check
            
            return (correct_linkages / total_linkages) * 100
        
        except Exception as e:
            print(f"⚠️  Linkage check error: {e}")
            return 0.0
    
    def calculate_usdm_specific_metrics(self, output: Dict, gold: Dict) -> Dict:
        """Calculate USDM-specific metrics for SoA extraction."""
        try:
            timeline = output.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            gold_timeline = gold.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            
            # Visit count accuracy (CDISC Pilot = 14 expected)
            output_visits = len(timeline.get("plannedTimepoints", []))
            gold_visits = len(gold_timeline.get("plannedTimepoints", []))
            visit_accuracy = (min(output_visits, gold_visits) / gold_visits * 100) if gold_visits > 0 else 0
            
            # Activity count accuracy
            output_activities = len(timeline.get("activities", []))
            gold_activities = len(gold_timeline.get("activities", []))
            activity_accuracy = (min(output_activities, gold_activities) / gold_activities * 100) if gold_activities > 0 else 0
            
            # ActivityTimepoint mapping completeness (critical for USDM)
            output_at = len(timeline.get("activityTimepoints", []))
            gold_at = len(gold_timeline.get("activityTimepoints", []))
            at_completeness = (min(output_at, gold_at) / gold_at * 100) if gold_at > 0 else 0
            
            return {
                "visit_count_accuracy": visit_accuracy,
                "activity_count_accuracy": activity_accuracy,
                "activitytimepoint_completeness": at_completeness,
                "actual_visits": output_visits,
                "expected_visits": gold_visits,
                "actual_activities": output_activities,
                "expected_activities": gold_activities
            }
        except Exception as e:
            print(f"⚠️  USDM metric calculation error: {e}")
            return {
                "visit_count_accuracy": 0.0,
                "activity_count_accuracy": 0.0,
                "activitytimepoint_completeness": 0.0
            }
    
    def calculate_metrics(self, output: Dict, gold: Dict, execution_time: float) -> Dict:
        """Calculate all benchmark metrics (enhanced with USDM-specific metrics)."""
        if "error" in output:
            return {
                "validation_pass": False,
                "completeness_score": 0.0,
                "linkage_accuracy": 0.0,
                "field_population_rate": 0.0,
                "execution_time_seconds": execution_time,
                "error_occurred": True,
                "error_message": output["error"],
                "usdm_metrics": {}
            }
        
        base_metrics = {
            "validation_pass": self.check_schema_validation(output),
            "completeness_score": self.calculate_completeness(output, gold),
            "linkage_accuracy": self.check_linkages(output, gold),
            "field_population_rate": self.check_field_population(output),
            "execution_time_seconds": execution_time,
            "error_occurred": False
        }
        
        # Add USDM-specific metrics
        base_metrics["usdm_metrics"] = self.calculate_usdm_specific_metrics(output, gold)
        
        return base_metrics
    
    def check_field_population(self, output: Dict) -> float:
        """Check what % of required fields are populated (comprehensive USDM fields)."""
        try:
            timeline = output.get("study", {}).get("versions", [{}])[0].get("timeline", {})
            
            # Required fields per entity type (USDM v4.0 spec)
            required_fields = {
                "PlannedTimepoint": [
                    "id", "name", "instanceType", "encounterId", 
                    "value", "unit", "relativeToId", "relativeToType"
                ],  # All 8 required fields
                "Activity": ["id", "name", "instanceType"],
                "ActivityTimepoint": ["id", "activityId", "timepointId", "instanceType"],
                "Encounter": ["id", "name", "type", "instanceType"],
                "Epoch": ["id", "name", "instanceType"]
            }
            
            total_required = 0
            total_present = 0
            
            # Check each entity type
            for entity_type, fields in required_fields.items():
                # Convert to snake_case key for timeline access
                timeline_key = entity_type[0].lower() + entity_type[1:] + "s" if not entity_type.endswith("s") else entity_type[0].lower() + entity_type[1:]
                
                for entity in timeline.get(timeline_key, []):
                    for field in fields:
                        total_required += 1
                        if field in entity and entity[field] is not None and entity[field] != "":
                            total_present += 1
            
            if total_required == 0:
                return 100.0
            
            return (total_present / total_required) * 100
        
        except Exception as e:
            print(f"⚠️  Field population check error: {e}")
            return 0.0
    
    def run_benchmark(self, model: str = "gemini-2.5-pro") -> Dict:
        """Run full benchmark on test set."""
        test_cases = self.load_test_set()
        
        if not test_cases:
            print("❌ No test cases found. Exiting.")
            return {}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "test_cases": {}
        }
        
        print(f"\n{'='*70}")
        print(f"RUNNING BENCHMARK: {len(test_cases)} test cases")
        print(f"{'='*70}\n")
        
        for pdf_path, gold_path in test_cases:
            print(f"\n[TEST] {pdf_path.name}")
            print("-" * 70)
            
            # Load gold standard
            with open(gold_path, 'r', encoding='utf-8') as f:
                gold_standard = json.load(f)
            
            # Run pipeline with timing
            start_time = datetime.now()
            output = self.run_pipeline(pdf_path, model)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Calculate metrics
            metrics = self.calculate_metrics(output, gold_standard, execution_time)
            
            # Store results
            results["test_cases"][pdf_path.stem] = metrics
            
            # Print summary
            if metrics["error_occurred"]:
                print(f"❌ FAILED: {metrics.get('error_message', 'Unknown error')}")
            else:
                print(f"✅ Validation: {'PASS' if metrics['validation_pass'] else 'FAIL'}")
                print(f"📊 Completeness: {metrics['completeness_score']:.1f}%")
                print(f"🔗 Linkage Accuracy: {metrics['linkage_accuracy']:.1f}%")
                print(f"📝 Field Population: {metrics['field_population_rate']:.1f}%")
                print(f"⏱️  Time: {metrics['execution_time_seconds']:.1f}s")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"benchmark_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*70}")
        print(f"RESULTS SAVED: {output_file}")
        print(f"{'='*70}\n")
        
        # Generate summary
        self.generate_summary(results)
        
        return results
    
    def generate_summary(self, results: Dict):
        """Generate summary statistics with USDM-specific metrics."""
        test_cases = results["test_cases"]
        
        if not test_cases:
            return
        
        # Aggregate metrics
        total = len(test_cases)
        passed_validation = sum(1 for m in test_cases.values() if m.get("validation_pass", False))
        avg_completeness = sum(m.get("completeness_score", 0) for m in test_cases.values()) / total
        avg_linkage = sum(m.get("linkage_accuracy", 0) for m in test_cases.values()) / total
        avg_field_pop = sum(m.get("field_population_rate", 0) for m in test_cases.values()) / total
        avg_time = sum(m.get("execution_time_seconds", 0) for m in test_cases.values()) / total
        errors = sum(1 for m in test_cases.values() if m.get("error_occurred", False))
        
        # USDM-specific aggregates
        avg_visit_accuracy = sum(m.get("usdm_metrics", {}).get("visit_count_accuracy", 0) for m in test_cases.values()) / total
        avg_activity_accuracy = sum(m.get("usdm_metrics", {}).get("activity_count_accuracy", 0) for m in test_cases.values()) / total
        avg_at_completeness = sum(m.get("usdm_metrics", {}).get("activitytimepoint_completeness", 0) for m in test_cases.values()) / total
        
        print("\n" + "="*70)
        print("BENCHMARK SUMMARY - USDM EXTRACTION QUALITY")
        print("="*70)
        print(f"Total Test Cases: {total}")
        print(f"Schema Validation: {passed_validation}/{total} ({passed_validation/total*100:.1f}%)")
        print(f"Errors: {errors}/{total}")
        print()
        print("CORE METRICS (Overall Quality):")
        print(f"  • Completeness Score:      {avg_completeness:.1f}%")
        print(f"  • Linkage Accuracy:        {avg_linkage:.1f}%")
        print(f"  • Field Population:        {avg_field_pop:.1f}%")
        print()
        print("USDM-SPECIFIC METRICS (Entity-Level Accuracy):")
        print(f"  • Visit Count Accuracy:    {avg_visit_accuracy:.1f}%")
        print(f"  • Activity Count Accuracy: {avg_activity_accuracy:.1f}%")
        print(f"  • ActivityTimepoint Map:   {avg_at_completeness:.1f}%")
        print()
        print(f"Average Execution Time: {avg_time:.1f}s")
        print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Benchmark prompt versions")
    parser.add_argument("--test-set", default="test_data", help="Directory containing test PDFs")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory")
    parser.add_argument("--model", default="gemini-2.5-pro", help="Model to use")
    parser.add_argument("--auto-optimize", action="store_true", 
                       help="Auto-optimize prompts before benchmarking")
    parser.add_argument("--optimization-method", default="google-zeroshot",
                       choices=["google-zeroshot", "google-datadriven", "openai-multiagent", "none"],
                       help="Optimization method to use")
    
    args = parser.parse_args()
    
    # Optimize prompts if requested
    if args.auto_optimize and OPTIMIZER_AVAILABLE:
        print("\n" + "="*70)
        print("AUTO-OPTIMIZING PROMPTS")
        print("="*70 + "\n")
        
        optimizer = PromptOptimizer()
        
        # Optimize each template file
        from prompt_templates import PromptTemplate
        templates_dir = Path("prompts")
        
        for template_file in templates_dir.glob("*.yaml"):
            if template_file.stem.endswith("_optimized"):
                continue  # Skip already optimized files
            
            print(f"\n[OPTIMIZE] {template_file.name}...")
            
            try:
                from prompt_optimizer import optimize_template_file
                optimize_template_file(
                    str(template_file),
                    method=args.optimization_method
                )
            except Exception as e:
                print(f"[WARNING] Could not optimize {template_file.name}: {e}")
        
        print("\n" + "="*70)
        print("OPTIMIZATION COMPLETE - Now running benchmark")
        print("="*70 + "\n")
    
    benchmark = PromptBenchmark(args.test_set, args.output_dir)
    results = benchmark.run_benchmark(args.model)
    
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
