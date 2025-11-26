import json

with open(r'output\Alexion_NCT04573309_Wilsons\9_reconciled_soa.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

version = data['study']['versions'][0]
timeline = version['timeline']

print('='*60)
print('VALIDATION OF FIXES APPLIED')
print('='*60)

# Check 1: No duplicate EOS timepoints
tps = timeline['plannedTimepoints']
eos_tps = [tp for tp in tps if 'End of Study' in tp.get('name', '')]
print(f'\n1. EOS Timepoints: {len(eos_tps)} (should be 1)')
for tp in eos_tps:
    print(f'   - {tp["id"]}: {tp["name"]} -> enc:{tp.get("encounterId")}')

# Check 2: Unscheduled encounter has type and timing
unsch_enc = [e for e in timeline['encounters'] if 'Unscheduled' in e.get('name', '')]
print(f'\n2. Unscheduled Encounters: {len(unsch_enc)}')
for enc in unsch_enc:
    has_type = 'type' in enc
    has_timing = 'timing' in enc
    print(f'   - {enc["id"]}: type={has_type}, timing={has_timing}')

# Check 3: Activity group IDs normalized
ag_ids = [ag['id'] for ag in timeline['activityGroups']]
print(f'\n3. Activity Group IDs: {sorted(ag_ids)}')

# Check 4: Study metadata
print(f'\n4. Study Metadata:')
print(f'   - Name: {data["study"].get("name")}')
print(f'   - Identifiers: {len(version.get("studyIdentifiers", []))}')
if version.get('studyIdentifiers'):
    for sid in version['studyIdentifiers']:
        print(f'     * {sid.get("id")}')
print(f'   - Titles: {len(version.get("titles", []))}')

# Check 5: Timeline stats
print(f'\n5. Timeline Entity Counts:')
print(f'   - Planned Timepoints: {len(timeline["plannedTimepoints"])}')
print(f'   - Activities: {len(timeline["activities"])}')
print(f'   - Activity-Timepoint mappings: {len(timeline["activityTimepoints"])}')
print(f'   - Encounters: {len(timeline["encounters"])}')

print('\n' + '='*60)
print('✅ Validation complete!')
