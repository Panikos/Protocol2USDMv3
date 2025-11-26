#!/usr/bin/env python3
"""
Pipeline Validation Script

Validates each step of the Protocol2USDM extraction pipeline.
"""

import json
import os
from pathlib import Path


def validate_pipeline(output_dir: str = "output/CDISC_Pilot_Study"):
    """Validate pipeline outputs step by step."""
    
    output_path = Path(output_dir)
    
    print("=" * 60)
    print("PROTOCOL2USDM PIPELINE VALIDATION")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Check header structure
    print("STEP 1: Header Structure Analysis")
    print("-" * 40)
    header_file = output_path / "4_header_structure.json"
    
    if header_file.exists():
        with open(header_file) as f:
            header = json.load(f)
        
        epochs = header.get("columnHierarchy", {}).get("epochs", [])
        encounters = header.get("columnHierarchy", {}).get("encounters", [])
        timepoints = header.get("columnHierarchy", {}).get("plannedTimepoints", [])
        groups = header.get("activityGroups", [])
        
        print(f"✓ Epochs: {len(epochs)}")
        print(f"✓ Encounters: {len(encounters)}")
        print(f"✓ PlannedTimepoints: {len(timepoints)}")
        print(f"✓ ActivityGroups: {len(groups)}")
        
        # Show sample encounters
        if encounters:
            print("\nSample Encounters:")
            for e in encounters[:5]:
                print(f"  - {e.get('id')}: {e.get('name')}")
            if len(encounters) > 5:
                print(f"  ... and {len(encounters) - 5} more")
    else:
        print("✗ Header structure not found")
    
    print()
    
    # Step 2: Check validation result
    print("STEP 2: Validation Result")
    print("-" * 40)
    validation_file = output_path / "6_validation_result.json"
    
    if validation_file.exists():
        with open(validation_file) as f:
            validation = json.load(f)
        
        print(f"✓ Confirmed ticks: {validation.get('confirmed_ticks', 0)}")
        print(f"✓ Hallucinations flagged: {validation.get('hallucination_count', 0)}")
        print(f"✓ Missed ticks found: {validation.get('missed_count', 0)}")
        print(f"✓ Model used: {validation.get('model_used', 'N/A')}")
    else:
        print("✗ Validation result not found (validation may be disabled)")
    
    print()
    
    # Step 3: Check final output
    print("STEP 3: Final USDM Output")
    print("-" * 40)
    final_file = output_path / "9_final_soa.json"
    
    if final_file.exists():
        with open(final_file) as f:
            data = json.load(f)
        
        # Get USDM metadata
        print(f"✓ USDM Version: {data.get('usdmVersion', 'N/A')}")
        print(f"✓ System: {data.get('systemName', 'N/A')} v{data.get('systemVersion', 'N/A')}")
        
        # Navigate to timeline
        study = data.get("study", {})
        versions = study.get("versions", [])
        timeline = versions[0].get("timeline", {}) if versions else {}
        
        acts = timeline.get("activities", [])
        pts = timeline.get("plannedTimepoints", [])
        encs = timeline.get("encounters", [])
        epochs = timeline.get("epochs", [])
        ticks = timeline.get("activityTimepoints", [])
        groups = timeline.get("activityGroups", [])
        
        print()
        print("Entity Counts:")
        print(f"  ✓ Activities: {len(acts)}")
        print(f"  ✓ PlannedTimepoints: {len(pts)}")
        print(f"  ✓ Encounters: {len(encs)}")
        print(f"  ✓ Epochs: {len(epochs)}")
        print(f"  ✓ ActivityGroups: {len(groups)}")
        print(f"  ✓ ActivityTimepoints (ticks): {len(ticks)}")
        
        # Sample activities
        if acts:
            print("\nSample Activities:")
            for a in acts[:5]:
                print(f"  - {a.get('id')}: {a.get('name')}")
            if len(acts) > 5:
                print(f"  ... and {len(acts) - 5} more")
        
        # Sample timepoints
        if pts:
            print("\nSample PlannedTimepoints:")
            for p in pts[:5]:
                print(f"  - {p.get('id')}: {p.get('name')}")
            if len(pts) > 5:
                print(f"  ... and {len(pts) - 5} more")
        
        # Tick coverage
        if ticks and acts and pts:
            total_possible = len(acts) * len(pts)
            tick_rate = (len(ticks) / total_possible * 100) if total_possible > 0 else 0
            print(f"\nTick Coverage: {len(ticks)}/{total_possible} ({tick_rate:.1f}%)")
    else:
        print("✗ Final output not found")
    
    print()
    
    # Step 4: Check provenance
    print("STEP 4: Provenance Tracking")
    print("-" * 40)
    provenance_file = output_path / "9_final_soa_provenance.json"
    
    if provenance_file.exists():
        with open(provenance_file) as f:
            provenance = json.load(f)
        
        entities = provenance.get("entities", {})
        cells = provenance.get("cells", {})
        
        # Count sources
        entity_sources = {}
        for entity_type, items in entities.items():
            for item_id, source in items.items():
                entity_sources[source] = entity_sources.get(source, 0) + 1
        
        print("Entity Provenance:")
        for source, count in sorted(entity_sources.items()):
            print(f"  ✓ {source}: {count} entities")
        
        print(f"\nCell-level provenance: {len(cells)} entries")
    else:
        print("✗ Provenance file not found")
    
    print()
    print("=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)


def compare_with_expected(output_dir: str = "output/CDISC_Pilot_Study"):
    """Compare extracted data with expected values for CDISC Pilot Study."""
    
    print()
    print("=" * 60)
    print("COMPARISON WITH EXPECTED VALUES")
    print("=" * 60)
    
    # Expected visits for CDISC Pilot Study
    expected_visits = [
        "Visit 1/Week -2", "Visit 2/Week -0.3", "Visit 3/Week 0", 
        "Visit 4/Week 2", "Visit 5/Week 4", "Visit 7/Week 6", 
        "Visit 8/Week 8", "Visit 9/Week 12", "Visit 10/Week 16", 
        "Visit 11/Week 20", "Visit 12/Week 24", "Visit 13/Week 26", 
        "ET", "RT"
    ]
    
    final_file = Path(output_dir) / "9_final_soa.json"
    if not final_file.exists():
        print("Final output not found")
        return
    
    with open(final_file) as f:
        data = json.load(f)
    
    timeline = data.get("study", {}).get("versions", [{}])[0].get("timeline", {})
    
    # Compare encounters
    print("\nExpected Visits vs Extracted Encounters:")
    print("-" * 40)
    
    extracted = timeline.get("encounters", [])
    for i, exp in enumerate(expected_visits):
        if i < len(extracted):
            ext = extracted[i]
            ext_name = ext.get("name", "")
            match = "✓" if exp.split("/")[0].replace("Visit ", "") in str(ext_name) else "?"
            print(f"  {match} Expected: {exp:25} | Got: {ext_name}")
        else:
            print(f"  ✗ Expected: {exp:25} | Got: (missing)")
    
    if len(extracted) > len(expected_visits):
        print(f"  + {len(extracted) - len(expected_visits)} extra encounters")
    
    print(f"\nExpected: {len(expected_visits)} visits")
    print(f"Extracted: {len(extracted)} encounters")


if __name__ == "__main__":
    import sys
    
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output/CDISC_Pilot_Study"
    validate_pipeline(output_dir)
    compare_with_expected(output_dir)
