import json
import sys
from copy import deepcopy
import os
import logging
import re

# Use consolidated core modules
from core import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION
from core import standardize_ids, parse_llm_json, make_hashable
from core.llm_client import get_openai_client

# Use processing module for normalization/enrichment
from processing import normalize_names_vs_timing, ensure_required_fields

# Alias for backward compatibility
standardize_ids_recursive = standardize_ids

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Load entity mapping for required fields and value sets
def load_entity_mapping(mapping_path="soa_entity_mapping.json"):
    with open(mapping_path, "r", encoding="utf-8") as f:
        return json.load(f)

ENTITY_MAP = None
try:
    ENTITY_MAP = load_entity_mapping()
except Exception:
    ENTITY_MAP = None
    print("[WARNING] Could not load soa_entity_mapping.json. Post-processing will not fill missing fields.")

def infer_activity_groups_llm(activities, existing_groups=None, model_name=None):
    """Infer ActivityGroups for ungrouped activities using an LLM.

    Returns a list of group dicts with at least:
        {"id": str, "name": str, "description": str, "activities": [str, ...]}

    If the OpenAI client or API key is not available, returns an empty list.
    """
    if not OpenAI:
        return []

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []

    # Build a minimal activity list for the model
    simple_activities = []
    for act in activities:
        name = (act.get("name") or "").strip()
        if not name:
            continue
        simple_activities.append({
            "id": act.get("id"),
            "name": name,
            "description": (act.get("description") or "").strip(),
        })

    if not simple_activities:
        return []

    payload = {
        "activities": simple_activities,
        "existingGroups": existing_groups or [],
    }

    system_prompt = (
        "You are an expert in clinical trial Schedule of Activities (SoA) and CDISC USDM v4.0. "
        "Given a list of activities (procedures/assessments) and optional existing groups, "
        "propose high-quality ActivityGroups consistent with USDM v4.0. "
        "Each ActivityGroup should represent a meaningful category (e.g., Safety Assessments, "
        "Cognitive/Efficacy Assessments, Concomitant Medications) and must only reference activity "
        "names from the input list. If activities already belong to an existing group, you may keep them there "
        "and focus primarily on ungrouped activities."
    )

    user_prompt = (
        "Return a JSON object with a single key 'activityGroups', whose value is a list of groups.\n"  # noqa: E501
        "Each group must have: 'id' (short string id), 'name', optional 'description', and 'activities' "
        "(a list of exact activity names drawn from the input). Do not invent new activity names.\n"  # noqa: E501
        "If you cannot form any sensible groups, return an empty list for 'activityGroups'.\n"  # noqa: E501
        "Here is the input data:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    model = model_name or os.environ.get("OPENAI_MODEL", "gpt-4o")
    reasoning_models = ['o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini']

    try:
        client = OpenAI(api_key=api_key)
        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if model in reasoning_models:
            params["max_completion_tokens"] = 2048
        else:
            params["max_tokens"] = 2048
            params["temperature"] = 0.1

        response = client.chat.completions.create(**params)
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            # Strip markdown fences if the model included them
            content = content.strip('`')
            # Remove potential json language tag
            if content.lower().startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        groups = parsed.get("activityGroups", []) if isinstance(parsed, dict) else []
        if not isinstance(groups, list):
            return []
        return groups
    except Exception as e:
        print(f"[WARN] LLM-based activity grouping failed: {e}")
        return []

# make_hashable, standardize_ids_recursive, normalize_names_vs_timing, 
# and ensure_required_fields are now imported from core and processing modules

def postprocess_usdm(data: dict, verbose: bool = False) -> dict:
    """
    Orchestrator function for all post-processing normalizations.
    
    Applies in order:
    1. Ensure required fields with defaults
    2. Normalize names vs. timing separation
    3. Standardize IDs (existing function)
    
    Args:
        data: Raw USDM JSON object from LLM
        verbose: Print normalization statistics
    
    Returns:
        Normalized USDM JSON object
    """
    if verbose:
        print("[POST-PROCESS] Starting USDM normalization...")
    
    # Step 1: Ensure required fields
    added_fields = ensure_required_fields(data)
    if verbose and added_fields:
        print(f"[POST-PROCESS] Added {len(added_fields)} missing fields: {', '.join(added_fields[:5])}{'...' if len(added_fields) > 5 else ''}")
    
    # Step 2: Normalize naming vs. timing
    study = data.get('study', {})
    versions = study.get('versions', []) or study.get('studyVersions', [])
    if versions:
        timeline = versions[0].get('timeline', {})
        normalized_count = normalize_names_vs_timing(timeline)
        if verbose and normalized_count > 0:
            print(f"[POST-PROCESS] Normalized {normalized_count} entity names (removed timing text)")
    
    # Step 3: Standardize IDs
    standardize_ids_recursive(data)
    if verbose:
        print("[POST-PROCESS] Standardized all entity IDs (- → _)")
    
    if verbose:
        print("[POST-PROCESS] Normalization complete")
    
    return data

def consolidate_and_fix_soa(input_path, output_path, header_structure_path=None, ref_metadata_path=None):
    """
    Consolidate, normalize, and fully expand a loosely structured SoA file into strict USDM v4.0 Wrapper-Input format.
    Optionally merge in richer metadata from a hand-curated reference file.
    - Enforces top-level keys: study, usdmVersion, systemName, systemVersion
    - Normalizes field names and expands group-based activityTimepoints
    - Preserves and merges metadata (description, code, window, etc.) where possible
    - Validates all references and schema compliance
    - Extracts footnotes, legend, and milestone and outputs a secondary M11-table-aligned JSON for Streamlit
    """
    fixes = []
    provenance_path = output_path.replace('.json', '_provenance.json') if output_path else None

    # Helper to record provenance
    def _tp_sort_key(label: str):
        label_l = label.lower() if isinstance(label, str) else ''
        m = re.search(r'(visit|day|week|period)\s*(-?\d+)', label_l)
        if m:
            return int(m.group(2))
        m = re.search(r'(-?\d+)\s*hour', label_l)
        if m:
            return int(m.group(1))
        if 'screen' in label_l:
            return -9999
        return 9999

    def _tag_provenance(container_key, obj_list, src):
        prov = data.setdefault('p2uProvenance', {}).setdefault(container_key, {})
        for obj in obj_list:
            if isinstance(obj, dict) and obj.get('id'):
                prov[obj['id']] = src

    def _normalize_timing_codes(timeline: dict) -> None:
        """Normalize PlannedTimepoint and Encounter timing-related codes to USDM CT.

        This is a deterministic, non-LLM step that fixes cases where the model has
        emitted decode text (e.g., "Fixed Reference", "Start to Start", "Visit")
        into the code slot instead of the CDISC code (e.g., "C99073", "C99074",
        "C25426"). Values that are not recognized are left unchanged.
        """
        if not isinstance(timeline, dict):
            return

        # These mappings reflect what the prompts/schema expect for SoA timing
        pt_type_code_map = {
            "Fixed Reference": "C99073",
        }
        rel_to_from_code_map = {
            "Start to Start": "C99074",
        }

        # PlannedTimepoints
        for pt in timeline.get('plannedTimepoints', []):
            if not isinstance(pt, dict):
                continue

            t = pt.get('type')
            if isinstance(t, dict):
                code_val = t.get('code')
                dec_val = t.get('decode') or code_val
                # Handle cases where the decode string appears in either slot
                if code_val in pt_type_code_map:
                    t['code'] = pt_type_code_map[code_val]
                    if not t.get('decode'):
                        t['decode'] = code_val
                elif dec_val in pt_type_code_map:
                    t['code'] = pt_type_code_map[dec_val]
                    if not t.get('decode'):
                        t['decode'] = dec_val
            elif isinstance(t, str) and t in pt_type_code_map:
                pt['type'] = {"code": pt_type_code_map[t], "decode": t}

            rtf = pt.get('relativeToFrom')
            if isinstance(rtf, dict):
                rcode = rtf.get('code')
                rdec = rtf.get('decode') or rcode
                if rcode in rel_to_from_code_map:
                    rtf['code'] = rel_to_from_code_map[rcode]
                    if not rtf.get('decode'):
                        rtf['decode'] = rcode
                elif rdec in rel_to_from_code_map:
                    rtf['code'] = rel_to_from_code_map[rdec]
                    if not rtf.get('decode'):
                        rtf['decode'] = rdec
            elif isinstance(rtf, str) and rtf in rel_to_from_code_map:
                pt['relativeToFrom'] = {
                    'code': rel_to_from_code_map[rtf],
                    'decode': rtf,
                }

        # Encounters
        for enc in timeline.get('encounters', []):
            if not isinstance(enc, dict):
                continue
            t = enc.get('type')
            # Default all SoA encounters to Visit when type is missing/empty
            if not isinstance(t, dict) or not (t.get('code') or t.get('decode')):
                enc['type'] = {'code': 'C25426', 'decode': 'Visit'}
            else:
                code_val = t.get('code')
                dec_val = t.get('decode') or code_val
                # Normalize when the literal decode got placed into code
                if code_val == 'Visit' and not t.get('decode'):
                    t['decode'] = 'Visit'
                    t['code'] = 'C25426'
                elif dec_val == 'Visit' and code_val != 'C25426':
                    t['code'] = 'C25426'

    def _enforce_header_ids(timeline: dict, header_path: str):
        """
        Force-map the IDs in the timeline to match the IDs in the header structure file.
        Returns (message, pt_id_rewrite, enc_id_rewrite).
        """
        try:
            with open(header_path, 'r', encoding='utf-8') as f:
                hdr = json.load(f)
        except Exception as e:
            return f"Skipped header ID enforcement: {e}", {}, {}

        col_h = hdr.get('columnHierarchy', {})
        
        # Build Name -> ID maps from Header Structure
        # Normalize names: lower, strip, remove timing info for robust matching
        def clean_name(n):
            if not n: return ""
            # remove text in parens
            n = re.sub(r'\s*\(.*?\)', '', n)
            return n.strip().lower()

        # PlannedTimepoints
        pt_name_map = {}
        header_pts = col_h.get('plannedTimepoints', [])
        for pt in header_pts:
            if pt.get('id'):
                if pt.get('name'):
                    pt_name_map[clean_name(pt['name'])] = pt['id']
                if pt.get('valueLabel'):
                    pt_name_map[clean_name(pt['valueLabel'])] = pt['id']
                if pt.get('description'):
                     pt_name_map[clean_name(pt['description'])] = pt['id']

        # Encounters
        enc_name_map = {}
        header_encs = col_h.get('encounters', [])
        for enc in header_encs:
            if enc.get('id'):
                 if enc.get('name'):
                    enc_name_map[clean_name(enc['name'])] = enc['id']
                 if enc.get('description'):
                    enc_name_map[clean_name(enc['description'])] = enc['id']

        updated_pts = 0
        pt_id_rewrite = {} # Old ID -> New ID
        
        # Strategy 1: Map by Name
        text_pts = timeline.get('plannedTimepoints', [])
        for pt in text_pts:
            old_id = pt.get('id')
            # Try matching by name
            cname = clean_name(pt.get('name'))
            new_id = pt_name_map.get(cname)
            
            # Try matching by description if name fails
            if not new_id and pt.get('description'):
                 new_id = pt_name_map.get(clean_name(pt['description']))
            
            # Fuzzy Fallback: Check if one string contains the other as a whole word
            if not new_id and cname:
                for k, vid in pt_name_map.items():
                    if k and (re.search(r'\b' + re.escape(cname) + r'\b', k) or re.search(r'\b' + re.escape(k) + r'\b', cname)):
                        new_id = vid
                        print(f"[INFO] Fuzzy matched '{cname}' to '{k}' -> {new_id}")
                        break

            if new_id:
                if old_id != new_id:
                    pt['id'] = new_id
                    pt['plannedTimepointId'] = new_id
                    if old_id:
                        pt_id_rewrite[old_id] = new_id
                    updated_pts += 1

        # Strategy 2: Positional Fallback (if names failed for most/all)
        # Only apply if counts match exactly, assuming implicit column order preservation
        if updated_pts < len(text_pts) and len(text_pts) == len(header_pts):
             print(f"[INFO] ID Enforcer: Falling back to positional mapping for PlannedTimepoints (Matches: {len(text_pts)})")
             for i, pt in enumerate(text_pts):
                 old_id = pt.get('id')
                 # skip if already remapped (unless we want to force positional? usually name is safer if valid)
                 if old_id in pt_id_rewrite.values(): 
                     continue
                     
                 target_id = header_pts[i].get('id')
                 if target_id and old_id != target_id:
                     pt['id'] = target_id
                     pt['plannedTimepointId'] = target_id
                     if old_id:
                         pt_id_rewrite[old_id] = target_id
                     updated_pts += 1

        # Rewrite Encounters
        updated_encs = 0
        enc_id_rewrite = {}
        text_encs = timeline.get('encounters', [])
        
        # Strategy 1: Map by Name
        for enc in text_encs:
            old_id = enc.get('id')
            cname = clean_name(enc.get('name'))
            new_id = enc_name_map.get(cname)
            
            if not new_id and enc.get('description'):
                 new_id = enc_name_map.get(clean_name(enc['description']))

            # Fuzzy Fallback for Encounters
            if not new_id and cname:
                for k, vid in enc_name_map.items():
                    if k and (re.search(r'\b' + re.escape(cname) + r'\b', k) or re.search(r'\b' + re.escape(k) + r'\b', cname)):
                        new_id = vid
                        print(f"[INFO] Fuzzy matched Encounter '{cname}' to '{k}' -> {new_id}")
                        break

            if new_id:
                if old_id != new_id:
                    enc['id'] = new_id
                    if old_id:
                        enc_id_rewrite[old_id] = new_id
                    updated_encs += 1
                    
        # Strategy 2: Positional Fallback for Encounters
        if updated_encs < len(text_encs) and len(text_encs) == len(header_encs):
             print(f"[INFO] ID Enforcer: Falling back to positional mapping for Encounters (Matches: {len(text_encs)})")
             for i, enc in enumerate(text_encs):
                 old_id = enc.get('id')
                 if old_id in enc_id_rewrite.values():
                     continue
                 target_id = header_encs[i].get('id')
                 if target_id and old_id != target_id:
                     enc['id'] = target_id
                     if old_id:
                         enc_id_rewrite[old_id] = target_id
                     updated_encs += 1

        # Apply Rewrites to Foreign Keys
        rewritten_refs = 0
        
        # 1. Rewrite PTP refs in ActivityTimepoints
        if pt_id_rewrite:
            for atp in timeline.get('activityTimepoints', []):
                pid = atp.get('plannedTimepointId')
                if pid in pt_id_rewrite:
                    atp['plannedTimepointId'] = pt_id_rewrite[pid]
                    rewritten_refs += 1
            # 2. Rewrite PTP refs in Encounters (scheduledAtId)
            for enc in timeline.get('encounters', []):
                sid = enc.get('scheduledAtId')
                if sid in pt_id_rewrite:
                    enc['scheduledAtId'] = pt_id_rewrite[sid]

        # 3. Rewrite Encounter refs in PlannedTimepoints (encounterId)
        if enc_id_rewrite:
             for pt in timeline.get('plannedTimepoints', []):
                 eid = pt.get('encounterId')
                 if eid in enc_id_rewrite:
                     pt['encounterId'] = enc_id_rewrite[eid]
                     rewritten_refs += 1

        return f"Enforced header IDs: Updated {updated_pts} timepoints, {updated_encs} encounters, {rewritten_refs} references.", pt_id_rewrite, enc_id_rewrite

    def _reconstruct_encounter_ids(timeline: dict) -> int:
        """Populate encounterId on plannedTimepoints using existing hints.

        Strategy:
        1) If a plannedTimepoint already has an encounterId that resolves to an
           existing encounter (or a known alias), leave it as-is.
        2) Otherwise, try relativeFromScheduledInstanceId / relativeToScheduledInstanceId
           to map IDs like "enc_1" to canonical encounter IDs such as "encounter_1".
        3) As a last resort, match by cleaned name (e.g., "Visit 1").

        Returns the number of timepoints for which encounterId was set or updated.
        """
        if not isinstance(timeline, dict):
            return 0

        planned_timepoints = timeline.get('plannedTimepoints', [])
        encounters = timeline.get('encounters', [])
        if not planned_timepoints or not encounters:
            return 0

        # Canonical encounter map
        enc_by_id = {e.get('id'): e for e in encounters if isinstance(e, dict) and e.get('id')}
        if not enc_by_id:
            return 0

        # Build alias map: e.g., encounter_1 -> enc_1 so that references like enc_1
        # can be mapped back to the canonical encounter_1 ID.
        alias_to_canonical = {}
        for enc_id in enc_by_id.keys():
            m = re.match(r'^encounter_(.+)$', enc_id)
            if m:
                short_id = f"enc_{m.group(1)}"
                alias_to_canonical.setdefault(short_id, enc_id)

        # Name-based map as a final fallback
        name_to_ids = {}
        for enc in encounters:
            name = enc.get('name')
            if isinstance(name, str) and name.strip() and enc.get('id'):
                key = name.strip().lower()
                name_to_ids.setdefault(key, set()).add(enc['id'])

        updated = 0
        for pt in planned_timepoints:
            if not isinstance(pt, dict):
                continue
            pt_id = pt.get('id') or pt.get('plannedTimepointId')
            if not pt_id:
                continue

            # If encounterId is already present and resolvable, normalize and keep.
            existing = pt.get('encounterId')
            if existing:
                canonical = None
                if existing in enc_by_id:
                    canonical = existing
                elif existing in alias_to_canonical:
                    canonical = alias_to_canonical[existing]
                if canonical:
                    if canonical != existing:
                        pt['encounterId'] = canonical
                        updated += 1
                    continue

            candidates = []
            # Prefer explicit scheduled-instance style references
            for key in (
                'relativeFromScheduledInstanceId',
                'relativeToScheduledInstanceId',
                'scheduledAtId',
                'scheduledInstanceId',
            ):
                ref_id = pt.get(key)
                if not ref_id:
                    continue
                if ref_id in enc_by_id:
                    candidates.append(ref_id)
                elif ref_id in alias_to_canonical:
                    candidates.append(alias_to_canonical[ref_id])

            # Fallback: match by cleaned name (e.g., "Visit 1") when unambiguous
            if not candidates:
                name = pt.get('name')
                if isinstance(name, str) and name.strip():
                    ids = list(name_to_ids.get(name.strip().lower(), []))
                    if len(ids) == 1:
                        candidates.append(ids[0])

            if candidates:
                pt['encounterId'] = candidates[0]
                updated += 1

        return updated

    # Load files
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Standardize all IDs ('epoch-1' -> 'epoch_1') before any processing
    data = standardize_ids_recursive(data)
    fixes.append("Standardized all hyphenated IDs to use underscores.")

    ref_metadata = None
    if ref_metadata_path:
        with open(ref_metadata_path, 'r', encoding='utf-8') as f:
            ref_metadata = json.load(f)

    # --- USDM v4 Wrapper-Input enforcement ---
    required_keys = {'study', 'usdmVersion', 'systemName', 'systemVersion'}
    if not (isinstance(data, dict) and required_keys.issubset(set(data.keys()))):
        print("[INFO] Input missing USDM Wrapper-Input keys. Attempting to fix.")
        # If the input is just the study object itself (no 'study' key at top level)
        if 'study' not in data:
            print("[INFO] Assuming input is the study object. Wrapping.")
            data = {
                'study': data,
                'usdmVersion': USDM_VERSION,
                'systemName': SYSTEM_NAME,
                'systemVersion': SYSTEM_VERSION,
            }
        # If the input has a 'study' key but is missing other wrapper keys
        else:
            print("[INFO] Found 'study' key. Adding missing wrapper keys.")
            data.setdefault('usdmVersion', USDM_VERSION)
            data.setdefault('systemName', SYSTEM_NAME)
            data.setdefault('systemVersion', SYSTEM_VERSION)

    study = data.get('study')
    if not study:
        print("[FATAL] Could not find 'study' object in the input data.")
        sys.exit(1)

    # --- Inject required Study fields to pass schema validation ---
    study.setdefault('name', 'Auto-generated Study Name')
    study.setdefault('instanceType', 'Study')

    # Robustly drill to timeline, handling old and new grouping structures
    versions = study.get('versions') or study.get('studyVersions')
    # Accept single version as dict
    if versions and isinstance(versions, dict):
        versions = [versions]
        study['versions'] = versions
    # If missing or empty, but study itself looks like a version (has timeline), wrap it
    if (not versions or not isinstance(versions, list) or len(versions) == 0):
        # Accept timeline at study, studyDesign, or direct timeline keys
        timeline_candidate = study.get('timeline') or study.get('studyDesign', {}).get('timeline') or study.get('Timeline')
        if timeline_candidate:
            versions = [dict(study)]
            versions[0]['timeline'] = timeline_candidate
            study['versions'] = versions
            print("[INFO] Study missing versions/studyVersions; treating study as a single version.")
        else:
            print("[FATAL] Study must contain a non-empty 'versions' or 'studyVersions' array, and no timeline found in study.")
            print("[DEBUG] Study keys:", list(study.keys()))
            sys.exit(1)
    # --- Inject required StudyVersion fields to pass schema validation ---
    for version in versions:
        version.setdefault('id', 'autogen-version-id-1')
        version.setdefault('versionIdentifier', '1.0.0')
        version.setdefault('rationale', 'Version auto-generated by pipeline.')
        version.setdefault('studyIdentifiers', [])
        version.setdefault('titles', [])
        version.setdefault('instanceType', 'StudyVersion')

    # Accept timeline in various possible locations/names
    timeline = (
        versions[0].get('timeline') or
        versions[0].get('Timeline') or
        versions[0].get('studyDesign', {}).get('timeline') or
        versions[0].get('studyDesign', {}).get('Timeline')
    )
    if not timeline:
        print("[FATAL] No timeline found in study version.")
        print("[DEBUG] Version keys:", list(versions[0].keys()))
        sys.exit(1)
    # Accept timeline as a list (legacy), wrap as dict
    if isinstance(timeline, list):
        timeline = {'plannedTimepoints': timeline}
        versions[0]['timeline'] = timeline
        print("[INFO] Timeline was a list, wrapped as dict.")

    # --- Enforce Header IDs (Text Extraction Fix) ---
    if header_structure_path:
         msg, pt_rewrites, enc_rewrites = _enforce_header_ids(timeline, header_structure_path)
         fixes.append(msg)
         
         # Also update the provenance file keys if they match the rewritten IDs
         if provenance_path and os.path.exists(provenance_path) and (pt_rewrites or enc_rewrites):
             try:
                 with open(provenance_path, 'r', encoding='utf-8') as f:
                     prov = json.load(f)
                 
                 updated_prov = False
                 if 'plannedTimepoints' in prov and pt_rewrites:
                     new_pt_prov = {}
                     for k, v in prov['plannedTimepoints'].items():
                         # Handle ID standardization (underscores vs hyphens) if needed?
                         # Usually keys match the 'old_id' in the timeline exactly.
                         new_k = pt_rewrites.get(k, k)
                         new_pt_prov[new_k] = v
                     prov['plannedTimepoints'] = new_pt_prov
                     updated_prov = True

                 if 'encounters' in prov and enc_rewrites:
                     new_enc_prov = {}
                     for k, v in prov.get('encounters', {}).items():
                         new_k = enc_rewrites.get(k, k)
                         new_enc_prov[new_k] = v
                     prov['encounters'] = new_enc_prov
                     updated_prov = True
                     
                 if updated_prov:
                     with open(provenance_path, 'w', encoding='utf-8') as f:
                         json.dump(prov, f, indent=2)
                     fixes.append("Updated provenance keys to match enforced header IDs.")
             except Exception as e:
                 print(f"[WARN] Failed to update provenance keys: {e}")

    # --- Normalize plannedTimepoints and add milestone support ---
    norm_timepoints = []
    seen_timepoints = set()
    pt_map = {}
    for pt in timeline.get('plannedTimepoints', [],):
        pt_tuple = make_hashable(pt)
        if pt_tuple not in seen_timepoints:
            # Normalize ID fields
            pt_id = pt.get('plannedTimepointId') or pt.get('id')
            if not pt_id:
                print(f"[WARNING] Skipping timepoint with no ID: {pt}")
                continue
            pt['id'] = pt_id
            pt['plannedTimepointId'] = pt_id

            # Merge in metadata from reference if available
            if ref_metadata:
                ref_pts = ref_metadata.get('plannedTimepoints', [])
                ref = next((x for x in ref_pts if (x.get('plannedTimepointId') or x.get('id')) == pt_id), None)
                if ref:
                    for k in ['description', 'code', 'window']:
                        if k in ref:
                            pt[k] = ref[k]
            
            norm_timepoints.append(pt)
            pt_map[pt_id] = pt
            seen_timepoints.add(pt_tuple)
    timeline['plannedTimepoints'] = norm_timepoints

    # --- Inject default epochId for Encounters ---
    epochs = timeline.get('epochs', [])
    default_epoch_id = epochs[0]['id'] if epochs else None
    if default_epoch_id:
        for enc in timeline.get('encounters', []):
            if not enc.get('epochId'):
                enc['epochId'] = default_epoch_id
    
    # Populate encounterId on plannedTimepoints where possible so that
    # downstream consumers (e.g., the Streamlit viewer) can render full
    # epoch/visit hierarchies instead of falling back to a flat timeline.
    updated_pts = _reconstruct_encounter_ids(timeline)
    if updated_pts:
        fixes.append(f"Reconstructed encounterId for {updated_pts} plannedTimepoints.")

    # Deterministic normalization of timing-related codes
    _normalize_timing_codes(timeline)
    fixes.append("Normalized PlannedTimepoint and Encounter timing codes where recognizable.")

    # --- Normalize activities ---
    act_map = {}
    norm_acts = []
    acts = timeline.get('activities', [])
    if acts and isinstance(acts[0], str):
        for i, act_str in enumerate(acts):
            act = {"activityId": f"A{i+1}", "activityName": act_str}
            norm_acts.append(act)
            act_map[act['activityId']] = act
        fixes.append("Converted activities from strings to objects.")
    else:
        for act in acts:
            act = deepcopy(act)
            act_id = act.get('activityId') or act.get('id')
            if act_id:
                act['activityId'] = act_id
            if 'name' in act and 'activityName' not in act:
                act['activityName'] = act['name']
            norm_acts.append(act)
            act_map[act['activityId']] = act
    timeline['activities'] = norm_acts

    # --- Normalize activityGroups ---
    # First, map all existing groups by their ID for easy lookup.
    group_map = {g.get('activityGroupId'): g for g in timeline.get('activityGroups', []) if g.get('activityGroupId')}
    # For now, we are not performing group inference, so the final list of groups is just the ones from the input.
    norm_groups = list(group_map.values())
    timeline['activityGroups'] = norm_groups

    # --- Process ActivityTimepoints ---
    atps = timeline.get('activityTimepoints', [])
    new_atps = []
    dropped = []
    
    # Handle multiple formats in a single pass, robustly handling nested ID objects
    for atp in atps:
        try:
            # Format 1: Direct IDs (most common from vision)
            if 'activityId' in atp and 'plannedTimepointId' in atp:
                act_id = atp['activityId']
                if isinstance(act_id, dict): act_id = act_id.get('id')

                pt_id = atp['plannedTimepointId']
                if isinstance(pt_id, dict): pt_id = pt_id.get('id')

                if act_id and pt_id and act_id in act_map and pt_id in pt_map:
                    new_atps.append({'activityId': act_id, 'plannedTimepointId': pt_id})
                else:
                    dropped.append({**atp, 'reason': 'invalid activityId or plannedTimepointId'})
            
            # Format 2: Group-based
            elif 'activityGroupId' in atp and 'plannedTimepointId' in atp:
                group = next((g for g in norm_groups if g.get('id') == atp['activityGroupId']), None)
                pt_id = atp['plannedTimepointId']
                if isinstance(pt_id, dict): pt_id = pt_id.get('id')

                if group and pt_id and pt_id in pt_map:
                    for act_id_from_group in group.get('activityIds', []):
                        if act_id_from_group in act_map:
                            new_atps.append({'activityId': act_id_from_group, 'plannedTimepointId': pt_id})
                        else:
                            dropped.append({'activityId': act_id_from_group, 'plannedTimepointId': pt_id, 'reason': 'invalid activityId in group expansion'})
                else:
                    dropped.append({**atp, 'reason': 'group not found or invalid timepointId'})
            
            # Format 3: Activity-based with a list of timepoints
            elif 'activityId' in atp and 'plannedTimepointIds' in atp:
                act_id = atp['activityId']
                if isinstance(act_id, dict): act_id = act_id.get('id')

                if act_id and act_id in act_map:
                    for ptid_item in atp['plannedTimepointIds']:
                        ptid = ptid_item
                        if isinstance(ptid, dict): ptid = ptid.get('id')

                        if ptid and ptid in pt_map:
                            new_atps.append({'activityId': act_id, 'plannedTimepointId': ptid})
                        else:
                            dropped.append({'activityId': act_id, 'plannedTimepointId': ptid, 'reason': 'invalid plannedTimepointId in list'})
                else:
                    dropped.append({**atp, 'reason': 'invalid activityId'})
            
            # Unrecognized format
            else:
                dropped.append({**atp, 'reason': 'unrecognized format'})
        except Exception as e:
            dropped.append({**atp, 'reason': f'processing error: {e}'})

    # --- Fallback: If no activityTimepoints, try to infer from activities ---
    if not new_atps:
        for act in norm_acts:
            aid = act.get('activityId') or act.get('id')
            for k in ['plannedTimepoints', 'plannedTimepointIds']:
                if k in act:
                    for ptid in act[k]:
                        if aid and ptid:
                            new_atps.append({'activityId': aid, 'plannedTimepointId': ptid})
        if new_atps:
            fixes.append('Auto-generated activityTimepoints from per-activity plannedTimepoints.')

    timeline['activityTimepoints'] = new_atps

    # --- Auto-provenance tagging if missing --------------------------------------
    source_tag = 'text' if 'text' in os.path.basename(input_path).lower() else (
        'vision' if 'vision' in os.path.basename(input_path).lower() else None)
    if source_tag:
        prov_root = data.setdefault('p2uProvenance', {})
        # timepoints
        if 'plannedTimepoints' not in prov_root:
            prov_root['plannedTimepoints'] = {pt['id']: source_tag for pt in timeline.get('plannedTimepoints', []) if pt.get('id')}
        # activities
        if 'activities' not in prov_root:
            prov_root['activities'] = {act['id']: source_tag for act in timeline.get('activities', []) if act.get('id')}

    # --- Fill missing fields using entity mapping ---
    def fill_missing_fields(entity_type, obj):
        if not ENTITY_MAP or entity_type not in ENTITY_MAP:
            return
        mapping = ENTITY_MAP[entity_type]
        for field, meta in mapping.items():
            if field not in obj:
                # Use empty string or placeholder for missing required fields
                if 'allowed_values' in meta:
                    obj[field] = meta['allowed_values'][0]['term'] if meta['allowed_values'] else ''
                else:
                    obj[field] = ''
            # Normalize coded values
            if 'allowed_values' in meta and obj[field]:
                allowed = [v['term'] for v in meta['allowed_values']]
                if isinstance(obj[field], list):
                    obj[field] = [v if v in allowed else allowed[0] for v in obj[field]]
                else:
                    if obj[field] not in allowed:
                        obj[field] = allowed[0]
    # Study
    fill_missing_fields("Study", data)
    for sv in data.get("studyVersions", []):
        fill_missing_fields("StudyVersion", sv)
        sd = sv.get("studyDesign", {})
        timeline = sd.get("timeline", {})
        fill_missing_fields("Timeline", timeline)
        _normalize_timing_codes(timeline)
        # PlannedTimepoints
        
        pt_pattern = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
        pt_map = {}
        unhandled_timepoints = []
        for pt in timeline.get('plannedTimepoints', []):
            # --- Split concatenated name/description like "Visit 1 (Week -2)" ---
            if pt and isinstance(pt.get('name'), str):
                m = pt_pattern.match(pt['name'])
                if m and (not pt.get('description')):
                    pt['name'] = m.group(1).strip()
                    pt['description'] = m.group(2).strip()
            # Accept both 'plannedTimepointId' and 'plannedVisitId' as equivalent
            pt_id = pt.get('plannedTimepointId') or pt.get('plannedVisitId') or pt.get('id')
            if pt_id is not None:
                pt['plannedTimepointId'] = pt_id  # Normalize key
                pt_map[pt_id] = pt
            else:
                print(f"[WARNING] Skipping timepoint missing both plannedTimepointId and plannedVisitId: {pt}")
                unhandled_timepoints.append(pt)
        if unhandled_timepoints:
            print(f"[SUMMARY] {len(unhandled_timepoints)} timepoints skipped due to missing IDs.")
        # --- Propagate timing from PlannedTimepoints to Encounters ---
        # Build quick lookup of PT description by cleaned name
        pt_label_to_desc = {pt['name']: pt.get('description') for pt in timeline.get('plannedTimepoints', []) if pt.get('name')}

        # Encounters - split concatenated name and create timing
        for enc in timeline.get('encounters', []):
            if enc and isinstance(enc.get('name'), str):
                m = pt_pattern.match(enc['name'])
                if m:
                    enc['name'] = m.group(1).strip()
                    timing_label = m.group(2).strip()
                    enc['timing'] = enc.get('timing') or {}
                    if 'windowLabel' not in enc['timing']:
                        enc['timing']['windowLabel'] = timing_label
            # If still no timing, attempt to copy from matching PlannedTimepoint description
            if enc.get('name') and (not enc.get('timing') or not enc['timing'].get('windowLabel')):
                desc = pt_label_to_desc.get(enc['name'])
                if desc:
                    enc.setdefault('timing', {})['windowLabel'] = desc
        # Activities
        for act in timeline.get("activities", []):
            fill_missing_fields("Activity", act)
        # ActivityGroups
        for ag in timeline.get("activityGroups", []):
            fill_missing_fields("ActivityGroup", ag)
        # ActivityTimepoints
        for atp in timeline.get("activityTimepoints", []):
            fill_missing_fields("ActivityTimepoint", atp)
            # --- Orphan PlannedTimepoints detection ---------------------------------
        # Build set of linked timepoint IDs from activityTimepoints
        linked_tp_ids = {link['plannedTimepointId'] for link in timeline.get('activityTimepoints', []) if isinstance(link, dict)}
        orphan_pts = [pt for pt in timeline.get('plannedTimepoints', []) if pt.get('id') not in linked_tp_ids]
        if orphan_pts:
            timeline['plannedTimepoints'] = [pt for pt in timeline['plannedTimepoints'] if pt.get('id') in linked_tp_ids]
            data.setdefault('p2uOrphans', {})['plannedTimepoints'] = orphan_pts
            fixes.append(f"Moved {len(orphan_pts)} orphan plannedTimepoints to p2uOrphans.")
        # --- Header-structure-driven enrichment ----------------------------------
        if header_structure_path:
            try:
                with open(header_structure_path, 'r', encoding='utf-8') as f:
                    hdr = json.load(f)
                hdr_groups = {g['id']: g for g in hdr.get('rowHierarchy', {}).get('activityGroups', []) if g.get('activities')}
                # Map activity name (lower) to group id
                name_to_gid = {}
                for gid, grp in hdr_groups.items():
                    for act_name in grp.get('activities', []):
                        name_to_gid[act_name.strip().lower()] = gid
                # Assign missing activityGroupId on activities
                added = 0
                for act in timeline.get('activities', []):
                    if not act.get('activityGroupId'):
                        gid = name_to_gid.get(act.get('name', '').strip().lower())
                        if gid:
                            act['activityGroupId'] = gid
                            _tag_provenance('activities', [act], 'headerStructure')
                            added += 1
                if added:
                    fixes.append(f"Filled activityGroupId for {added} activities using header structure.")
                # Populate missing activityIds lists in groups from header if still empty
                acts_by_id_lc = {a['name'].strip().lower(): a['id'] for a in timeline.get('activities', []) if a.get('id') and a.get('name')}
                for gid, grp in hdr_groups.items():
                    g_obj = next((g for g in timeline.get('activityGroups', []) if g.get('id') == gid), None)
                    if not g_obj:
                        continue
                    if not g_obj.get('activityIds'):
                        ids = [acts_by_id_lc.get(n.strip().lower()) for n in grp.get('activities', [])]
                        ids = [i for i in ids if i]
                        if ids:
                            g_obj['activityIds'] = ids
                            _tag_provenance('activityGroups', [g_obj], 'headerStructure')
                fixes.append("Applied header structure group mappings where possible.")
            except Exception as e:
                print(f"[WARN] Could not apply header structure enrichment: {e}")

        # --- LLM-based inferred ActivityGroups for remaining activities ----------
        # This step can introduce new groupings not explicitly present in the
        # protocol header. To avoid inventing new structure by default, it is
        # gated behind the P2U_ENABLE_LLM_GROUPING flag.
        if os.environ.get('P2U_ENABLE_LLM_GROUPING', '').lower() in ('1', 'true', 'yes', 'on'):
            try:
                # Only consider activities that still have no activityGroupId
                ungrouped_acts = [a for a in timeline.get('activities', []) if not a.get('activityGroupId') and a.get('name')]
                if ungrouped_acts:
                    inferred_groups = infer_activity_groups_llm(
                        activities=ungrouped_acts,
                        existing_groups=timeline.get('activityGroups', []),
                        model_name=os.environ.get('OPENAI_MODEL')
                    )
                    if inferred_groups:
                        name_lc_to_id = {
                            a['name'].strip().lower(): a['id']
                            for a in timeline.get('activities', [])
                            if a.get('id') and a.get('name')
                        }
                        existing_ids = {g.get('id') for g in timeline.get('activityGroups', []) if g.get('id')}
                        added_groups = 0
                        for g in inferred_groups:
                            # Map activity names to IDs
                            act_ids = []
                            for nm in g.get('activities', []):
                                aid = name_lc_to_id.get(str(nm).strip().lower())
                                if aid:
                                    act_ids.append(aid)
                            act_ids = list({aid for aid in act_ids})  # deduplicate
                            if not act_ids:
                                continue

                            gid = g.get('id') or f"ag_inferred_{len(existing_ids) + 1}"
                            # Ensure uniqueness of group ID
                            if gid in existing_ids:
                                base = gid
                                suffix = 1
                                while f"{base}_{suffix}" in existing_ids:
                                    suffix += 1
                                gid = f"{base}_{suffix}"
                            existing_ids.add(gid)

                            group_obj = {
                                'id': gid,
                                'name': g.get('name') or gid,
                                'description': g.get('description', ''),
                                'activityIds': act_ids,
                                'instanceType': 'ActivityGroup',
                            }
                            timeline.setdefault('activityGroups', []).append(group_obj)
                            # Attach activityGroupId to activities that were grouped
                            for aid in act_ids:
                                for a in timeline.get('activities', []):
                                    if a.get('id') == aid and not a.get('activityGroupId'):
                                        a['activityGroupId'] = gid
                            _tag_provenance('activityGroups', [group_obj], 'llmGrouping')
                            added_groups += 1
                        if added_groups:
                            fixes.append(f"Inferred {added_groups} activityGroups via LLM grouping for unassigned activities.")
            except Exception as e:
                print(f"[WARN] LLM-based activity grouping step failed: {e}")

        # --- ActivityGroup enrichment & conflict detection -----------------------
        acts_by_id = {a['id']: a for a in timeline.get('activities', []) if a.get('id')}
        # Fill missing activityIds lists
        for ag in timeline.get('activityGroups', []):
            if not ag.get('activityIds'):
                ag['activityIds'] = [aid for aid, a in acts_by_id.items() if a.get('activityGroupId') == ag['id']]
        # --- Chronology sanity check -----------------------------------------------
        # Compare canonical sort order with current order in timeline
        tp_list = timeline.get('plannedTimepoints', [])
        sort_key = lambda pt: _tp_sort_key(pt.get('name', ''))
        sorted_ids = [pt['id'] for pt in sorted(tp_list, key=sort_key)]
        current_ids = [pt['id'] for pt in tp_list]
        if sorted_ids != current_ids:
            data['p2uTimelineOrderIssues'] = {
                'expectedOrder': sorted_ids,
                'currentOrder': current_ids
            }
            fixes.append('Detected out-of-order plannedTimepoints; stored in p2uTimelineOrderIssues.')
        # Detect activities linked to >1 group
        group_membership = {}
        for ag in timeline.get('activityGroups', []):
            for aid in ag.get('activityIds', []):
                group_membership.setdefault(aid, set()).add(ag['id'])
        conflicts = [ {'activityId': aid, 'groupIds': list(gids)} for aid, gids in group_membership.items() if len(gids) > 1 ]
        if conflicts:
            data.setdefault('p2uGroupConflicts', conflicts)
            fixes.append(f"Detected {len(conflicts)} activities assigned to multiple groups (stored in p2uGroupConflicts).")
        
        # --- Restructure to StudyDesign-centric USDM (Gold Standard Alignment) ---
        print("DEBUG: Attempting restructure...")
        study_obj = data.get('study', {})
        vers = study_obj.get('versions', [])
        if vers:
            v1_obj = vers[0]
            # Use the local 'timeline' variable which is already resolved and processed
            tl_obj = v1_obj.get('timeline') or timeline
            if tl_obj:
                print("DEBUG: Found timeline, restructuring.")
                
                # Create Design
                design_obj = {
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
                    "encounters": tl_obj.get('encounters', []),
                    "activities": tl_obj.get('activities', []),
                    "plannedTimepoints": tl_obj.get('plannedTimepoints', []),
                    "activityGroups": tl_obj.get('activityGroups', [])
                }
                
                sched_tls = tl_obj.get('scheduleTimelines', [])
                if sched_tls:
                    design_obj["scheduleTimelines"] = sched_tls
                    
                v1_obj['studyDesigns'] = [design_obj]
                # Remove legacy timeline keys
                v1_obj.pop('timeline', None)
                v1_obj.pop('Timeline', None)
                fixes.append("Restructured USDM to StudyDesign-centric hierarchy.")
            else:
                print("DEBUG: No timeline object found in version.")
        else:
            print("DEBUG: No versions found in study.")

        # --- Save and report ---
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # --- NEW: Write provenance separately ---
    prov_path = output_path.replace('.json', '_provenance.json')
    prov_data = data.get('p2uProvenance', {}) if isinstance(data, dict) else {}
    try:
        with open(prov_path, 'w', encoding='utf-8') as pf:
            json.dump(prov_data, pf, indent=2, ensure_ascii=False)
        print(f"[INFO] Wrote provenance to {prov_path}")
    except Exception as e:
        print(f"[WARN] Could not write provenance file: {e}")
    print(f"[CONSOLIDATE/FIX] {len(new_atps)} valid activityTimepoints. {len(dropped)} dropped. {len(norm_timepoints)} timepoints, {len(norm_acts)} activities, {len(norm_groups)} groups.")
    if fixes:
        print("Fixes applied:")
        for fix in fixes:
            print("- ", fix)
    if dropped:
        print("First 10 dropped:")
        for d in dropped[:10]:
            print(d)
    else:
        print("No invalid links found.")

if __name__ == "__main__":
    if len(sys.argv) not in [4, 5]:
        print("Usage: python soa_postprocess_consolidated.py <input.json> <output.json> <header_structure.json> [reference_metadata.json]")
        sys.exit(1)
    consolidate_and_fix_soa(*sys.argv[1:])
