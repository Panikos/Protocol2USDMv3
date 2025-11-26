"""
Fix issues in the reconciled SoA JSON file:
1. Add type and timing to enc_24 (Unscheduled encounter)
2. Remove duplicate tp8 (keep only tp6 for EOS)
3. Standardize encounter timing windowLabel (Days vs Day for ranges)
4. Normalize activity group IDs (ag_1->ag_06, ag_2->ag_07, ag_3->ag_08)
5. Add study metadata (NCT ID, titles, name)
"""
import json
import sys
import os

input_file = r'output\Alexion_NCT04573309_Wilsons\9_reconciled_soa.json'
output_file = r'output\Alexion_NCT04573309_Wilsons\9_reconciled_soa.json'
backup_file = r'output\Alexion_NCT04573309_Wilsons\9_reconciled_soa_backup.json'

print(f"Reading {input_file}...")

# Read the corrupted file - if it fails, try backup
try:
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error reading file: {e}")
    print("File may be corrupted. Please restore from backup if available.")
    sys.exit(1)

# Create backup
import shutil
if os.path.exists(input_file):
    shutil.copy(input_file, backup_file)
    print(f"✓ Created backup: {backup_file}")

version = data['study']['versions'][0]
timeline = version['timeline']

fixes_applied = []

# Fix 1: Add type and timing to enc_24 (Unscheduled encounter)
for enc in timeline['encounters']:
    if enc['id'] == 'enc_24':
        if 'type' not in enc:
            enc['type'] = {'code': 'C25426', 'decode': 'Visit'}
            fixes_applied.append('Added type to enc_24')
        if 'timing' not in enc:
            enc['timing'] = {'windowLabel': 'UNS'}
            fixes_applied.append('Added timing to enc_24')
        break

# Fix 2: Remove duplicate tp8 (keep only tp6 for EOS)
tp_indices_to_remove = []
for i, tp in enumerate(timeline['plannedTimepoints']):
    if tp['id'] == 'tp8' and tp['name'] == 'End of Study':
        tp_indices_to_remove.append(i)
        fixes_applied.append(f"Marked tp8 for removal (duplicate EOS)")

# Remove from highest index first to avoid index shifts
for i in sorted(tp_indices_to_remove, reverse=True):
    timeline['plannedTimepoints'].pop(i)

# Remove all activityTimepoints that reference tp8
original_count = len(timeline['activityTimepoints'])
timeline['activityTimepoints'] = [
    at for at in timeline['activityTimepoints'] 
    if at['plannedTimepointId'] != 'tp8'
]
removed_count = original_count - len(timeline['activityTimepoints'])
if removed_count > 0:
    fixes_applied.append(f"Removed {removed_count} activity-timepoint mappings for tp8")

# Fix 3: Standardize encounter timing.windowLabel (Days vs Day for ranges)
for enc in timeline['encounters']:
    if 'timing' in enc and 'windowLabel' in enc['timing']:
        old_label = enc['timing']['windowLabel']
        # Check if it's a range (has hyphen or "through")
        is_range = '-' in old_label or 'through' in old_label.lower()
        
        # For ranges, should start with "Days", for single should start with "Day"
        if is_range and old_label.startswith('Day ') and not old_label.startswith('Days '):
            enc['timing']['windowLabel'] = 'Days ' + old_label[4:]
            fixes_applied.append(f"Fixed {enc['id']}: '{old_label}' -> '{enc['timing']['windowLabel']}'")

# Fix 4: Normalize activity group IDs
ag_map = {'ag_1': 'ag_06', 'ag_2': 'ag_07', 'ag_3': 'ag_08'}
act_fixed = 0
for act in timeline['activities']:
    if 'activityGroupId' in act and act['activityGroupId'] in ag_map:
        old_id = act['activityGroupId']
        act['activityGroupId'] = ag_map[old_id]
        act_fixed += 1

# Update activity groups list
ag_fixed = 0
for ag in timeline['activityGroups']:
    if ag['id'] in ag_map:
        old_id = ag['id']
        ag['id'] = ag_map[old_id]
        ag_fixed += 1

if act_fixed > 0 or ag_fixed > 0:
    fixes_applied.append(f"Normalized {act_fixed} activity group refs and {ag_fixed} group definitions")

# Fix 5: Add study metadata
if not version.get('studyIdentifiers'):
    version['studyIdentifiers'] = [{
        'id': 'NCT04573309',
        'studyIdentifierScope': {
            'organisationType': {
                'code': 'C93453',
                'decode': 'Clinical Trial Registry'
            }
        },
        'instanceType': 'StudyIdentifier'
    }]
    fixes_applied.append("Added NCT04573309 study identifier")

if not version.get('titles'):
    version['titles'] = [
        {
            'text': 'A Phase 1, Open-label Study to Assess the Pharmacokinetics, Pharmacodynamics, Safety, and Tolerability of ALXN1840 in Patients With Wilson Disease',
            'type': {'code': 'C99879', 'decode': 'Official Study Title'},
            'instanceType': 'StudyTitle'
        },
        {
            'text': 'ALXN1840 in Wilson Disease',
            'type': {'code': 'C99880', 'decode': 'Brief Study Title'},
            'instanceType': 'StudyTitle'
        }
    ]
    fixes_applied.append("Added official and brief study titles")

if data['study']['name'] == 'Auto-generated Study Name':
    data['study']['name'] = 'ALXN1840 Wilson Disease Phase 1 Study (NCT04573309)'
    fixes_applied.append("Updated study name")

# Write back
print(f"\nWriting fixed file to {output_file}...")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n" + "="*60)
print("FIXES APPLIED:")
print("="*60)
for i, fix in enumerate(fixes_applied, 1):
    print(f"{i}. {fix}")

print("\n✅ All fixes applied successfully!")
print(f"   Fixed file: {output_file}")
print(f"   Backup saved: {backup_file}")
