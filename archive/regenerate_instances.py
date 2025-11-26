import json
import os

def main():
    path = r"output\CDISC_Pilot_Study\9_reconciled_soa.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    study = data.get('study', {})
    versions = study.get('versions', [])
    if not versions: return
    v1 = versions[0]
    
    # Check if we are in Timeline-centric or Design-centric
    if 'timeline' in v1:
        source = v1['timeline']
    elif 'studyDesigns' in v1:
        source = v1['studyDesigns'][0]
    else:
        print("No timeline or studyDesign found.")
        return

    encounters = source.get('encounters', [])
    activities = source.get('activities', [])
    timepoints = source.get('plannedTimepoints', [])
    # Matrix might be in source or missing if we already restructured without copying
    # But since we just copied 7_text, it SHOULD be in timeline.
    matrix = source.get('activityTimepoints', [])
    
    if not matrix:
        print("WARNING: No activityTimepoints found! Cannot regenerate instances correctly.")
        # If missing, check if we can recover? No.
        return

    # 1. Create ScheduleTimeline
    st_id = "st_1"
    schedule_timeline = {
        "id": st_id,
        "name": "Main Schedule",
        "description": "SoA Matrix",
        "mainTimeline": True,
        "instances": [],
        "instanceType": "ScheduleTimeline"
    }
    
    # Group ticks by PTP
    ticks_by_ptp = {}
    for tick in matrix:
        pid = tick['plannedTimepointId']
        aid = tick['activityId']
        ticks_by_ptp.setdefault(pid, []).append(aid)
        
    # Create Instance for each Encounter
    instances = []
    # We iterate Encounters to create ScheduledActivityInstances linked to them
    for enc in encounters:
        enc_id = enc['id']
        ptp_id = enc.get('scheduledAtId')
        # If encounter has no timepoint, we can't map matrix ticks to it easily
        # Unless we map PTP ID to Encounter ID via other means.
        # Usually scheduledAtId is the link.
        if not ptp_id: 
            continue
        
        act_ids = ticks_by_ptp.get(ptp_id, [])
        # Even if empty, we might want an instance? 
        # Gold standard usually lists all visits.
        
        # Deduplicate act_ids
        act_ids = list(set(act_ids))
        
        inst_id = f"sai_{enc_id}"
        instance = {
            "id": inst_id,
            "name": f"Activities for {enc['name']}",
            "description": "Generated from Matrix",
            "encounterId": enc_id,
            "activityIds": act_ids,
            "instanceType": "ScheduledActivityInstance"
        }
        instances.append(instance)
        
    schedule_timeline['instances'] = instances
    
    # 2. Enrich Activities with timelineId
    for act in activities:
        act['timelineId'] = st_id
        
    # 3. Create/Update StudyDesign
    design = {
        "id": "StudyDesign_1",
        "instanceType": "InterventionalStudyDesign",
        "name": "Main Design",
        "label": "Primary Study Design",
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
        "encounters": encounters,
        "activities": activities,
        "plannedTimepoints": timepoints,
        "scheduleTimelines": [schedule_timeline]
        # We assume we don't need 'activityTimepoints' in the final USDM if we have instances?
        # But keeping it for reference is fine.
    }
    
    # 4. Update Version
    v1['studyDesigns'] = [design]
    if 'timeline' in v1:
        del v1['timeline']
        
    # Save
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Regenerated {len(instances)} instances and Restructured to StudyDesign.")

if __name__ == "__main__":
    main()
