"""Debug script to find cells that should be blue (text-only)."""
import json

# Load provenance
prov = json.load(open('output/Alexion_NCT04573309_Wilsons/9_final_soa_provenance.json'))
cells = prov.get('cells', {})

# Find all text-only cells
text_only = [(k, v) for k, v in cells.items() if v == 'text']
print(f'Total text-only cells: {len(text_only)}')

# Load protocol_usdm.json to get activity and timepoint names
usdm = json.load(open('output/Alexion_NCT04573309_Wilsons/protocol_usdm.json'))
sd = usdm.get('studyDesigns', [{}])[0]

# Build ID -> name maps
activities = {a['id']: a.get('name', a['id']) for a in sd.get('activities', [])}
print(f'Activities in USDM: {len(activities)}')
print('Activity IDs:', list(activities.keys()))

# Get timepoints from plannedTimepoints (not scheduleTimelines)
timepoints = {}
for tp in sd.get('plannedTimepoints', []):
    tp_id = tp.get('id')
    tp_label = tp.get('label') or tp.get('name') or tp.get('description') or tp_id
    timepoints[tp_id] = tp_label

print(f'\nTimepoints in USDM: {len(timepoints)}')
print('Timepoint IDs:', list(timepoints.keys())[:10])

print('\n' + '='*60)
print('ID MISMATCH ANALYSIS')
print('='*60)

# Check provenance IDs vs USDM IDs
prov_act_ids = set(k.split('|')[0] for k in cells.keys())
prov_pt_ids = set(k.split('|')[1] for k in cells.keys() if '|' in k)
usdm_act_ids = set(activities.keys())
usdm_pt_ids = set(timepoints.keys())

print(f'\nProvenance activity IDs: {sorted(prov_act_ids)[:10]}')
print(f'USDM activity IDs: {sorted(usdm_act_ids)[:10]}')
print(f'Match: {prov_act_ids == usdm_act_ids}')

print(f'\nProvenance timepoint IDs: {sorted(prov_pt_ids)[:10]}')
print(f'USDM timepoint IDs: {sorted(usdm_pt_ids)[:10]}')
print(f'Match: {prov_pt_ids == usdm_pt_ids}')

print('\n' + '='*60)
print('CELLS THAT SHOULD BE BLUE (with labels)')
print('='*60)
for cell_key, source in text_only[:5]:
    parts = cell_key.split('|', 1)
    if len(parts) == 2:
        act_id, pt_id = parts
        act_name = activities.get(act_id, f'[NOT FOUND: {act_id}]')
        pt_label = timepoints.get(pt_id, f'[NOT FOUND: {pt_id}]')
        print(f'\nRow: "{act_name}"')
        print(f'Column: "{pt_label}"')
        print(f'IDs: {act_id} | {pt_id}')
