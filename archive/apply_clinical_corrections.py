import json
import sys
import re

def clean_name(n):
    if not n: return ""
    return re.sub(r'\s*\(.*?\)', '', n).strip().lower()

def main():
    path = r"output\CDISC_Pilot_Study\9_reconciled_soa.json"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {path}")
        return

    timeline = data['study']['versions'][0]['timeline']
    
    # Build Maps
    act_map = {}
    # Prefer exact name match first
    for a in timeline['activities']:
        n = clean_name(a['name'])
        if n: act_map[n] = a['id']
        # Also map by raw name
        act_map[a['name'].strip().lower()] = a['id']
        
    pt_map = {}
    for p in timeline['plannedTimepoints']:
        n = clean_name(p['name'])
        if n: pt_map[n] = p['id']
        
    # Helper to find ID
    def find_act(pattern):
        # Regex search in keys
        matches = [id for name, id in act_map.items() if re.search(pattern, name)]
        if not matches:
            print(f"WARN: No activity found for '{pattern}'")
            return None
        return matches[0] 

    def find_pt(name):
        id = pt_map.get(clean_name(name))
        if not id:
             print(f"WARN: No timepoint found for '{name}'")
        return id

    # Define IDs
    v1 = find_pt("Visit 1")
    v2 = find_pt("Visit 2")
    v3 = find_pt("Visit 3")
    v4 = find_pt("Visit 4")
    v9 = find_pt("Visit 9")
    v12 = find_pt("Visit 12")
    et = find_pt("ET")
    
    amb_ecg_place = find_act(r"ambulatory ecg placed")
    amb_ecg_remove = find_act(r"ambulatory ecg removed")
    plasma = find_act(r"plasma specimen")
    study_drug = find_act(r"study drug record")
    meds_disp = find_act(r"medications dispensed")
    apo_e = find_act(r"apo e")
    urine = find_act(r"urinalysis")
    adas = find_act(r"adas-cog")
    cibic = find_act(r"cibic\+")
    dad = find_act(r"dad")
    tts = find_act(r"tts acceptability")
    
    print(f"IDs Resolved: V1={v1}, V2={v2}, V4={v4}, V9={v9}, ET={et}")
    print(f"Acts Resolved: AmbPlace={amb_ecg_place}, ApoE={apo_e}")

    # Operations
    at_list = timeline.get('activityTimepoints', [])
    
    def remove_tick(aid, pid):
        nonlocal at_list
        if not aid or not pid: return
        len_before = len(at_list)
        at_list = [x for x in at_list if not (x['activityId'] == aid and x['plannedTimepointId'] == pid)]
        if len(at_list) < len_before:
            print(f"Removed tick {aid} at {pid}")
            
    def add_tick(aid, pid):
        nonlocal at_list
        if not aid or not pid: return
        # Check exist
        if not any(x['activityId'] == aid and x['plannedTimepointId'] == pid for x in at_list):
            at_list.append({'activityId': aid, 'plannedTimepointId': pid})
            print(f"Added tick {aid} at {pid}")

    # 1. Move Amb ECG
    remove_tick(amb_ecg_place, v1)
    add_tick(amb_ecg_place, v2)
    
    remove_tick(amb_ecg_remove, v1)
    add_tick(amb_ecg_remove, v3)
        
    # 2. Clean V2
    remove_tick(plasma, v2)
    remove_tick(study_drug, v2)
    remove_tick(meds_disp, v2)
    
    # 3. Populate V4
    add_tick(apo_e, v4)
    add_tick(urine, v4)
    
    # 4. Clean V9
    remove_tick(adas, v9)
    remove_tick(cibic, v9)
    remove_tick(dad, v9)
    
    # 5. Populate ET
    if v12 and et:
        # Get ticks for v12
        v12_acts = [x['activityId'] for x in at_list if x['plannedTimepointId'] == v12]
        print(f"Copying {len(v12_acts)} activities from Visit 12 to ET")
        for aid in v12_acts:
            add_tick(aid, et)
        add_tick(tts, et)
        
    timeline['activityTimepoints'] = at_list
    
    # Save
    data['study']['versions'][0]['timeline'] = timeline
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print("Corrections applied and saved.")

if __name__ == "__main__":
    main()
