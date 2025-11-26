import json
import sys
import re

def clean_name(n):
    if not n: return ""
    n = re.sub(r'\s*\(.*?\)', '', n)
    return n.strip().lower()

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_activities(soa):
    study = soa.get('study', {})
    versions = study.get('versions', [])
    if isinstance(versions, dict): versions = [versions]
    if not versions:
        # Fallback if structure is different
        return soa.get('study', {}).get('timeline', {}).get('activities', [])
    return versions[0].get('timeline', {}).get('activities', [])

def main():
    reconciled_path = sys.argv[1]
    prov_path = sys.argv[2]
    text_path = sys.argv[3]
    vision_path = sys.argv[4]
    
    print(f"Fixing provenance keys using:\n Reconciled: {reconciled_path}\n Prov: {prov_path}\n Text: {text_path}\n Vision: {vision_path}")

    reconciled = load_json(reconciled_path)
    prov = load_json(prov_path)
    text_soa = load_json(text_path)
    vision_soa = load_json(vision_path)
    
    # Map OldID -> Name (from Inputs)
    id_to_name = {}
    for act in get_activities(text_soa):
        aid = act.get('id') or act.get('activityId')
        name = act.get('name') or act.get('activityName')
        if aid and name:
            id_to_name[aid] = clean_name(name)
            
    for act in get_activities(vision_soa):
        aid = act.get('id') or act.get('activityId')
        name = act.get('name') or act.get('activityName')
        if aid and name:
            id_to_name[aid] = clean_name(name)
            
    # Map Name -> FinalID (from Reconciled)
    name_to_final_id = {}
    for act in get_activities(reconciled):
        aid = act.get('id') or act.get('activityId')
        name = act.get('name') or act.get('activityName')
        if aid and name:
            name_to_final_id[clean_name(name)] = aid
            
    print(f"Found {len(id_to_name)} input activities and {len(name_to_final_id)} reconciled activities.")
            
    # Rewrite Provenance
    updated = False
    if 'activities' in prov:
        new_act_prov = {}
        for k, v in prov['activities'].items():
            # k is OldID
            if k in name_to_final_id.values(): # Already correct (e.g. act1)
                new_act_prov[k] = v
                continue
                
            name = id_to_name.get(k)
            if name and name in name_to_final_id:
                final_id = name_to_final_id[name]
                
                # Flatten 'v' to a set of sources
                current_sources = set()
                if isinstance(v, str): current_sources.add(v)
                elif isinstance(v, list): current_sources.update(v)
                
                # Merge with existing entry for final_id
                existing = new_act_prov.get(final_id, [])
                if isinstance(existing, str): existing_sources = {existing}
                else: existing_sources = set(existing)
                
                merged_sources = current_sources | existing_sources
                
                # Determine final label
                if 'both' in merged_sources: label = 'both'
                elif 'text' in merged_sources and 'vision' in merged_sources: label = 'both'
                elif 'vision' in merged_sources: label = 'vision'
                else: label = 'text'
                
                new_act_prov[final_id] = label
                updated = True
            else:
                new_act_prov[k] = v # Keep unknown
        
        prov['activities'] = new_act_prov
    
    if updated:
        with open(prov_path, 'w', encoding='utf-8') as f:
            json.dump(prov, f, indent=2)
        print("Successfully updated provenance keys.")
    else:
        print("No provenance keys needed updating.")

if __name__ == "__main__":
    main()
