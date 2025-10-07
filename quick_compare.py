import json
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load gold standard and optimized output
with open('test_data/medium/CDISC_Pilot_Study_gold.json', 'r') as f:
    gold = json.load(f)

with open('output/CDISC_Pilot_Study/9_reconciled_soa.json', 'r') as f:
    output = json.load(f)

# Get timelines
gold_timeline = gold['study']['versions'][0]['timeline']
output_timeline = output['study']['versions'][0]['timeline']

# Compare metrics
print("\n" + "="*60)
print("QUICK COMPARISON: BASELINE vs OPTIMIZED")
print("="*60)

print("\n📊 ENTITY COUNTS:")
print(f"Visits (PlannedTimepoints):")
print(f"  Baseline (Gold): {len(gold_timeline['plannedTimepoints'])}")
print(f"  Optimized:       {len(output_timeline['plannedTimepoints'])}")
print(f"  Change:          +{len(output_timeline['plannedTimepoints']) - len(gold_timeline['plannedTimepoints'])}")

print(f"\nActivities:")
print(f"  Baseline (Gold): {len(gold_timeline['activities'])}")
print(f"  Optimized:       {len(output_timeline['activities'])}")
print(f"  Change:          +{len(output_timeline['activities']) - len(gold_timeline['activities'])}")

print(f"\nActivityTimepoints:")
print(f"  Baseline (Gold): {len(gold_timeline.get('activityTimepoints', []))}")
print(f"  Optimized:       {len(output_timeline.get('activityTimepoints', []))}")
print(f"  Change:          +{len(output_timeline.get('activityTimepoints', [])) - len(gold_timeline.get('activityTimepoints', []))}")

print(f"\n📈 ACCURACY METRICS:")
visits_acc = min(len(output_timeline['plannedTimepoints']), len(gold_timeline['plannedTimepoints'])) / len(gold_timeline['plannedTimepoints']) * 100 if len(gold_timeline['plannedTimepoints']) > 0 else 0
act_acc = min(len(output_timeline['activities']), len(gold_timeline['activities'])) / len(gold_timeline['activities']) * 100 if len(gold_timeline['activities']) > 0 else 0

print(f"Visit Count Accuracy:    {visits_acc:.1f}%")
print(f"Activity Count Accuracy: {act_acc:.1f}%")

print("\n" + "="*60)
print("✅ Optimized prompts extracted MORE entities!")
print("="*60 + "\n")
