"""
Audit Extraction Gaps - Compare raw LLM responses vs parsed output.

This script identifies cases where the LLM extracted data correctly
but the parser failed to convert it to the final output structure.

Uses dataStructure.yml as reference for expected USDM entities.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.usdm_schema_loader import USDMSchemaLoader


@dataclass
class GapReport:
    """Report of a gap between raw and parsed data."""
    file: str
    entity_type: str
    raw_count: int
    parsed_count: int
    sample_raw: Any = None
    issue: str = ""


def count_entities(data: Any, key: str) -> int:
    """Count entities in data by key, handling nested structures."""
    if isinstance(data, dict):
        if key in data:
            val = data[key]
            if isinstance(val, list):
                return len(val)
            elif val:
                return 1
        # Check nested
        for v in data.values():
            count = count_entities(v, key)
            if count > 0:
                return count
    return 0


def get_entity_data(data: Any, key: str) -> List[Any]:
    """Get entity list from data by key."""
    if isinstance(data, dict):
        if key in data:
            val = data[key]
            if isinstance(val, list):
                return val
            elif val:
                return [val]
        for v in data.values():
            result = get_entity_data(v, key)
            if result:
                return result
    return []


def audit_file(file_path: str, entity_mappings: Dict[str, List[str]]) -> List[GapReport]:
    """Audit a single extraction result file for gaps."""
    gaps = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [GapReport(file=file_path, entity_type="FILE", raw_count=0, parsed_count=0, issue=f"Error loading: {e}")]
    
    raw_response = data.get('rawResponse', {})
    if not raw_response:
        return []  # No raw response to compare
    
    # Determine the parsed data key based on file type
    file_name = os.path.basename(file_path)
    parsed_data = None
    
    if 'metadata' in file_name:
        parsed_data = data.get('metadata', {})
    elif 'objectives' in file_name:
        parsed_data = data.get('objectivesEndpoints', {})
    elif 'eligibility' in file_name:
        parsed_data = data.get('eligibilityCriteria', {})
    elif 'studydesign' in file_name or 'study_design' in file_name:
        parsed_data = data.get('studyDesign', {})
    elif 'interventions' in file_name:
        parsed_data = data.get('interventions', {})
    elif 'narrative' in file_name:
        parsed_data = data.get('narrative', {})
    elif 'advanced' in file_name:
        parsed_data = data.get('advancedEntities', {})
    
    if not parsed_data:
        parsed_data = {}
    
    # Check each entity type
    for entity_type, keys in entity_mappings.items():
        for key in keys:
            raw_count = count_entities(raw_response, key)
            parsed_count = count_entities(parsed_data, key)
            
            if raw_count > 0 and parsed_count == 0:
                # Gap found - data extracted but not parsed
                sample = get_entity_data(raw_response, key)[:1]
                gaps.append(GapReport(
                    file=file_name,
                    entity_type=entity_type,
                    raw_count=raw_count,
                    parsed_count=parsed_count,
                    sample_raw=sample[0] if sample else None,
                    issue=f"Extracted {raw_count} but parsed 0"
                ))
            elif raw_count > parsed_count and parsed_count > 0:
                # Partial gap
                gaps.append(GapReport(
                    file=file_name,
                    entity_type=entity_type,
                    raw_count=raw_count,
                    parsed_count=parsed_count,
                    issue=f"Extracted {raw_count} but only parsed {parsed_count}"
                ))
    
    return gaps


def audit_output_directory(output_dir: str) -> Dict[str, List[GapReport]]:
    """Audit all extraction files in an output directory."""
    
    # Entity mappings: entity type -> possible keys in JSON
    entity_mappings = {
        # Metadata entities
        "StudyIdentifier": ["identifiers", "studyIdentifiers"],
        "StudyTitle": ["titles", "studyTitles"],
        "Organization": ["organizations", "sponsors"],
        "Indication": ["indications", "indication"],
        
        # Objectives entities
        "Objective": ["objectives", "primaryObjectives", "secondaryObjectives", "exploratoryObjectives"],
        "Endpoint": ["endpoints", "primaryEndpoints", "secondaryEndpoints"],
        "Estimand": ["estimands"],
        
        # Eligibility entities
        "EligibilityCriterion": ["criteria", "eligibilityCriteria", "inclusionCriteria", "exclusionCriteria"],
        
        # Study design entities
        "StudyArm": ["arms", "studyArms"],
        "StudyEpoch": ["epochs", "studyEpochs"],
        "StudyCohort": ["cohorts", "studyCohorts"],
        
        # Intervention entities
        "StudyIntervention": ["interventions", "studyInterventions"],
        "AdministrableProduct": ["products", "administrableProducts"],
        "Substance": ["substances"],
        
        # Narrative entities
        "NarrativeContent": ["sections", "narrativeContents"],
        "Abbreviation": ["abbreviations"],
        
        # Advanced entities
        "StudyAmendment": ["amendments", "studyAmendments"],
        "Country": ["countries"],
        "Procedure": ["procedures"],
    }
    
    results = {}
    
    # Find all extraction result files
    json_files = [
        "2_study_metadata.json",
        "3_eligibility_criteria.json",
        "4_objectives_endpoints.json",
        "5_study_design.json",
        "6_interventions.json",
        "7_narrative_structure.json",
        "8_advanced_entities.json",
    ]
    
    for json_file in json_files:
        file_path = os.path.join(output_dir, json_file)
        if os.path.exists(file_path):
            gaps = audit_file(file_path, entity_mappings)
            if gaps:
                results[json_file] = gaps
    
    return results


def print_report(results: Dict[str, List[GapReport]]):
    """Print a formatted report of gaps found."""
    print("\n" + "=" * 70)
    print("EXTRACTION GAP AUDIT REPORT")
    print("=" * 70)
    
    if not results:
        print("\n✅ No gaps detected - all extracted data was properly parsed!")
        return
    
    total_gaps = sum(len(gaps) for gaps in results.values())
    print(f"\n❌ Found {total_gaps} gaps across {len(results)} files:\n")
    
    for file_name, gaps in results.items():
        print(f"\n📄 {file_name}")
        print("-" * 50)
        
        for gap in gaps:
            print(f"  ⚠️  {gap.entity_type}")
            print(f"      Raw: {gap.raw_count} items | Parsed: {gap.parsed_count} items")
            print(f"      Issue: {gap.issue}")
            
            if gap.sample_raw:
                # Show sample of raw data (truncated)
                sample_str = json.dumps(gap.sample_raw, indent=2)[:200]
                if len(json.dumps(gap.sample_raw)) > 200:
                    sample_str += "..."
                print(f"      Sample: {sample_str}")
            print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Audit extraction gaps")
    parser.add_argument("output_dir", nargs="?", help="Output directory to audit")
    parser.add_argument("--latest", action="store_true", help="Use latest output directory")
    
    args = parser.parse_args()
    
    if args.latest or not args.output_dir:
        # Find latest output directory
        output_base = Path(__file__).parent.parent / "output"
        if output_base.exists():
            dirs = sorted([d for d in output_base.iterdir() if d.is_dir()], 
                         key=lambda x: x.stat().st_mtime, reverse=True)
            if dirs:
                output_dir = str(dirs[0])
                print(f"Using latest output: {dirs[0].name}")
            else:
                print("No output directories found")
                return
        else:
            print("Output directory not found")
            return
    else:
        output_dir = args.output_dir
    
    results = audit_output_directory(output_dir)
    print_report(results)
    
    # Return exit code based on gaps found
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
