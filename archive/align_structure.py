import json
import os

def main():
    input_path = r"output\CDISC_Pilot_Study\9_reconciled_soa.json"
    # Overwrite the input file to make the fix permanent
    output_path = input_path 
    
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    study = data.get('study', {})
    versions = study.get('versions', [])
    if not versions: 
        print("No versions found.")
        return
    
    v1 = versions[0]
    timeline = v1.get('timeline', {})
    
    # Extract components from the flat timeline
    encounters = timeline.get('encounters', [])
    activities = timeline.get('activities', [])
    timepoints = timeline.get('plannedTimepoints', [])
    timelines = timeline.get('scheduleTimelines', [])
    
    # Create StudyDesign Structure matching the Example
    design = {
        "id": "StudyDesign_1",
        "instanceType": "InterventionalStudyDesign",
        "name": "Main Design",
        "label": "Primary Study Design",
        "description": "Generated from SoA Extraction",
        "studyType": {
            "id": "Code_StudyType",
            "code": "C98388",
            "codeSystem": "CDISC",
            "codeSystemVersion": "2024-09-27",
            "decode": "Interventional Study",
            "instanceType": "Code"
        },
        "studyPhase": {
            "id": "Code_StudyPhase",
            "code": "C15601",
            "codeSystem": "CDISC",
            "codeSystemVersion": "2024-09-27",
            "decode": "Phase II Trial",
            "instanceType": "Code"
        },
        "therapeuticAreas": [
            {
                "id": "Code_TA",
                "code": "C99999", 
                "codeSystem": "CDISC",
                "decode": "Therapeutic Area Placeholder",
                "instanceType": "Code"
            }
        ],
        "encounters": encounters,
        "activities": activities,
        # Note: USDM 4.0 usually puts plannedTimepoints in the ScheduleTimeline or referenced
        # But keeping them here ensures they are preserved.
        # The Example puts them in 'plannedTimepoints'? 
        # The example snippet didn't show the timepoints section clearly (truncated).
        # But usually they accompany the design.
    }
    
    # If scheduleTimelines exist, they should be under the Design or Version?
    # In USDM 4.0, ScheduleTimeline is a child of StudyDesign (via 'scheduleTimelines').
    if timelines:
        design["scheduleTimelines"] = timelines
        
    # Move plannedTimepoints?
    # If they are referenced by encounters/activities, they should be reachable.
    # We'll keep them in the design if allowed, or put them in the timeline logic.
    # For now, I'll add a 'plannedTimepoints' array to the Design to be safe, 
    # mimicking the Timeline object we are dismantling.
    design["plannedTimepoints"] = timepoints

    # Update Version
    v1['studyDesigns'] = [design]
    
    # Remove legacy timeline
    if 'timeline' in v1:
        del v1['timeline']
        
    # Clean up top-level metadata to match Example style
    if "p2uProvenance" in data:
        # Move provenance to a separate file or keep it? 
        # The user's example doesn't have it. 
        # We'll keep it for traceability but maybe rename or move?
        # Actually, let's keep it, it's useful for debugging.
        pass

    # Set System Info
    data['systemName'] = "CDISC USDM E2J"
    data['systemVersion'] = "0.62.0" # Matching example

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Aligned USDM structure saved to {output_path}")

if __name__ == "__main__":
    main()
