"""Test that metadata extraction and addition works correctly"""
import json
import re

# Simulate the fix logic
output_path = r'output\Alexion_NCT04573309_Wilsons\9_reconciled_soa.json'

# Load current file
with open(output_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

version = data['study']['versions'][0]
study = data['study']

# Extract NCT ID and protocol name
nct_id = None
protocol_name = None

study_name = study.get('name', '')
if 'NCT' in study_name:
    match = re.search(r'NCT\d+', study_name)
    if match:
        nct_id = match.group(0)

if not nct_id and output_path:
    match = re.search(r'NCT\d+', output_path)
    if match:
        nct_id = match.group(0)
        path_match = re.search(r'([^/\\\\]+)_NCT\d+_([^/\\\\]+)', output_path)
        if path_match:
            sponsor = path_match.group(1)
            indication = path_match.group(2)
            protocol_name = f"{sponsor} {indication}"

print(f"Extracted NCT ID: {nct_id}")
print(f"Extracted protocol name: {protocol_name}")
print(f"Current studyIdentifiers: {version.get('studyIdentifiers')}")
print(f"Current titles: {version.get('titles')}")

# Test the condition
should_add_ids = nct_id and (not version.get('studyIdentifiers') or len(version.get('studyIdentifiers', [])) == 0)
should_add_titles = not version.get('titles') or len(version.get('titles', [])) == 0

print(f"\nShould add studyIdentifiers: {should_add_ids}")
print(f"Should add titles: {should_add_titles}")

if should_add_ids:
    version['studyIdentifiers'] = [{
        'id': nct_id,
        'studyIdentifierScope': {
            'organisationType': {
                'code': 'C93453',
                'decode': 'Clinical Trial Registry'
            }
        },
        'instanceType': 'StudyIdentifier'
    }]
    print(f"✓ Added study identifier: {nct_id}")

if should_add_titles and protocol_name and nct_id:
    phase_match = re.search(r'Phase\s+(\d+)', protocol_name, re.IGNORECASE)
    phase_str = f"Phase {phase_match.group(1)} " if phase_match else ""
    
    version['titles'] = [
        {
            'text': f"A {phase_str}Study of {protocol_name.replace('_', ' ')}",
            'type': {'code': 'C99879', 'decode': 'Official Study Title'},
            'instanceType': 'StudyTitle'
        },
        {
            'text': protocol_name.replace('_', ' '),
            'type': {'code': 'C99880', 'decode': 'Brief Study Title'},
            'instanceType': 'StudyTitle'
        }
    ]
    print(f"✓ Added study titles")

# Save the fixed version
output_fixed = output_path.replace('.json', '_METADATA_FIXED.json')
with open(output_fixed, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n✓ Saved fixed version to: {output_fixed}")
print(f"\nFinal studyIdentifiers: {version.get('studyIdentifiers')}")
print(f"Final titles count: {len(version.get('titles', []))}")
