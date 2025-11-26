"""
SoA Reconciliation Script - Merges Text and Vision extractions.

⚠️  DEPRECATION NOTICE:
    This script implements complex reconciliation logic that is no longer needed
    in the new architecture. Use `main_v2.py` with `extraction/validator.py` instead.
    
    The new approach:
    - Vision extracts STRUCTURE only (not full SoA data)
    - Text extracts DATA using structure as anchor
    - Vision VALIDATES text (simple validation, not parallel extraction)
    
    This eliminates the need for complex reconciliation and anti-smear logic.
"""

import os
import json
from pathlib import Path

# Use consolidated core modules
from core import parse_llm_json, extract_json_str
from core.llm_client import get_openai_client, get_gemini_client
from core.provenance import ProvenanceTracker, ProvenanceSource

# --- Prompt template system ---
try:
    from prompt_templates import PromptTemplate
    TEMPLATES_AVAILABLE = True
except ImportError:
    print("[WARNING] PromptTemplate not available, using fallback prompt")
    TEMPLATES_AVAILABLE = False

# --- Optional imports (only if available) ---
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- Client setup via core ---
client = get_openai_client() if OpenAI else None

# --- Load reconciliation prompt template ---
def load_reconciliation_prompt():
    """Load the reconciliation prompt from YAML template (v2.0) or fallback to hardcoded (v1.0)."""
    if TEMPLATES_AVAILABLE:
        try:
            template = PromptTemplate.load("soa_reconciliation", "prompts")
            print(f"[INFO] Loaded reconciliation prompt template v{template.metadata.version}")
            return template
        except Exception as e:
            print(f"[WARNING] Could not load YAML template: {e}. Using fallback.")
    
    # Fallback to v1.0 hardcoded prompt
    return None

# Try to load template, fallback to hardcoded if not available
RECONCILIATION_TEMPLATE = load_reconciliation_prompt()

# Fallback prompt (v1.0 - deprecated but kept for backward compatibility)
FALLBACK_LLM_PROMPT = (
    "You are an expert in clinical trial data curation and CDISC USDM v4.0 standards.\n"
    "You will be given two JSON objects, each representing a Schedule of Activities (SoA) extracted from a clinical trial protocol. Both are intended to conform to the USDM v4.0 Wrapper-Input OpenAPI schema.\n"
    "Compare and reconcile the two objects using the USDM v4.0 standard, while strictly respecting the following constraints.\n"
    "\n"
    "HARD CONSTRAINTS (MUST FOLLOW):\n"
    "- Base all entities and values only on the two input JSONs. You MUST NOT introduce new activities, plannedTimepoints, encounters, epochs, arms, or activity groups that do not appear in at least one of the inputs (other than normalizing IDs or names).\n"
    "- The final sets of activities, plannedTimepoints, encounters, epochs, and arms must be a subset of the union of those in the text-extracted and vision-extracted SoAs.\n"
    "- For activityTimepoints (the matrix of checkmarks), the final set of (activityId, plannedTimepointId) pairs must be a subset of the union of the pairs present in the two inputs. Never add a new tick that is present in neither input.\n"
    "- If the inputs disagree or a mapping is ambiguous, you may drop a tick, but you must not create a new one that is not supported by at least one input. Prefer omission over guessing.\n"
    "- Output EXACTLY one JSON object that conforms to the USDM v4.0 Wrapper-Input schema, with no extra commentary, markdown, or explanation.\n"
    "\n"
    "Additional reconciliation guidance:\n"
    "IMPORTANT: Output ALL column headers (timepoints) from the table EXACTLY as shown, including ranges (e.g., 'Day 2-3', 'Day 30-35'), even if they appear similar or redundant. Do NOT drop or merge any timepoints unless they are exact duplicates.\n"
    "When creating the `plannedTimepoints` array, you MUST standardize the `name` for each timepoint. If a timepoint has a simple `name` (e.g., 'Screening') and a more detailed `description` (e.g., 'Visit 1 / Week -2'), combine them into a single, user-friendly `name` in the format 'Visit X (Week Y)'. For example, a timepoint with `name: 'Screening'` and `description: 'Visit 1 / Week -2'` should be reconciled into a final timepoint with `name: 'Visit 1 (Week -2)'. Preserve the original `description` field as well.\n"
    "CRITICAL: When reconciling the `activityTimepoints` (the matrix of checkmarks), you MUST prioritize the data from the VISION-EXTRACTED SoA. The vision model is more reliable for identifying which activities occur at which timepoints. If the vision JSON indicates a checkmark for an activity at a timepoint, you should normally preserve that tick in the final output, even if the text JSON disagrees, as long as it does not violate the hard constraints above.\n"
    "Your output must be a single, unified JSON object that:\n"
    "- Strictly conforms to the USDM v4.0 Wrapper-Input schema (including the top-level keys: study, usdmVersion, systemName, systemVersion).\n"
    "- Includes a fully detailed SoA consistent with the inputs: activities, plannedTimepoints, activityGroups, activityTimepoints, and all appropriate groupings and relationships (without introducing new entities beyond the union of the two sources).\n"
    "- Has correct instanceType values for all objects, uses unique IDs, and preserves correct mappings.\n"
    "- Is ready for validation and visualization in a SoA table viewer (with correct groupings, milestones, and 'ticks' as per the protocol template).\n"
    "Output ONLY valid JSON (no markdown, comments, or explanations).\n"
)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_reconciliation_prompts(text_soa_json: str, vision_soa_json: str):
    """
    Get system and user prompts for reconciliation, using YAML template if available.
    
    Args:
        text_soa_json: JSON string of text-extracted SoA
        vision_soa_json: JSON string of vision-extracted SoA
    
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if RECONCILIATION_TEMPLATE:
        # Use v2.0 YAML template
        messages = RECONCILIATION_TEMPLATE.render(
            text_soa_json=text_soa_json,
            vision_soa_json=vision_soa_json
        )
        return messages[0]["content"], messages[1]["content"]
    else:
        # Use v1.0 fallback
        user_content = (
            "TEXT-EXTRACTED SoA JSON:\n" + text_soa_json +
            "\nVISION-EXTRACTED SoA JSON:\n" + vision_soa_json
        )
        return FALLBACK_LLM_PROMPT, user_content

def reconcile_soa(vision_path, output_path, text_path, model_name='o3'):

    def standardize_ids_recursive(data):
        if isinstance(data, dict):
            return {k.replace('-', '_'): standardize_ids_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [standardize_ids_recursive(i) for i in data]
        else:
            return data

    def _merge_prov(dest: dict, src: dict, src_name: str) -> dict:
        """Merge provenance with 'both' detection when entity appears in multiple sources.
        
        Args:
            dest: Destination provenance dict
            src: Source provenance dict to merge in
            src_name: Name of source ('text', 'vision', 'llm_reconciled')
        
        Returns:
            Merged provenance dict with 'both' tags where appropriate
        """
        for key, val in src.items():
            if isinstance(val, dict) and isinstance(dest.get(key), dict):
                for inner_id, inner_val in val.items():
                    existing_val = dest[key].get(inner_id)
                    if existing_val is None:
                        # First time seeing this entity
                        dest[key][inner_id] = inner_val
                    elif existing_val != inner_val:
                        # Entity exists from different source - mark as 'both'
                        dest[key][inner_id] = "both"
                    # If values are the same, keep existing (already marked)
            elif key not in dest:
                dest[key] = val
        return dest

    def _build_cell_level_provenance(text_soa, vision_soa, final_soa):
        """Derive optional cell-level provenance for activityTimepoints.

        This function attempts to determine, for each (activityId, plannedTimepointId)
        pair in the final reconciled SoA, whether that tick originated from text,
        vision, or both. It uses name/label matching to align entities across the
        text and vision SoAs and inspects their activityTimepoints matrices.
        """

        def _get_timeline(soa):
            if not isinstance(soa, dict):
                return {}
            return soa.get('study', {}).get('versions', [{}])[0].get('timeline', {})

        def _label_timepoint(pt: dict) -> str:
            name = (pt.get('name') or '').strip()
            desc = (pt.get('description') or '').strip()
            return f"{name}||{desc}".strip().lower()

        def _build_maps(timeline):
            acts_by_name = {}
            for a in timeline.get('activities', []):
                aid = a.get('id')
                name = a.get('name')
                if aid and isinstance(name, str) and name.strip():
                    acts_by_name.setdefault(name.strip().lower(), aid)

            tps_by_label = {}
            for pt in timeline.get('plannedTimepoints', []):
                pid = pt.get('id')
                if not pid:
                    continue
                key = _label_timepoint(pt)
                if key:
                    # Keep first occurrence; collisions just mean ambiguous mapping
                    tps_by_label.setdefault(key, pid)

            links = set()
            for at in timeline.get('activityTimepoints', []):
                aid = at.get('activityId')
                pid = at.get('plannedTimepointId') or at.get('timepointId')
                if aid and pid:
                    links.add((aid, pid))
            return acts_by_name, tps_by_label, links

        try:
            text_tl = _get_timeline(text_soa)
            vision_tl = _get_timeline(vision_soa)
            final_tl = _get_timeline(final_soa)

            if not final_tl:
                return {}

            text_acts_by_name, text_tps_by_label, text_links = _build_maps(text_tl)
            vision_acts_by_name, vision_tps_by_label, vision_links = _build_maps(vision_tl)

            final_acts = {a.get('id'): a for a in final_tl.get('activities', []) if a.get('id')}
            final_pts = {pt.get('id'): pt for pt in final_tl.get('plannedTimepoints', []) if pt.get('id')}

            final_act_names = {aid: (a.get('name') or '').strip().lower() for aid, a in final_acts.items()}
            final_tp_labels = {pid: _label_timepoint(pt) for pid, pt in final_pts.items()}

            cell_prov = {}

            for at in final_tl.get('activityTimepoints', []):
                faid = at.get('activityId')
                fpid = at.get('plannedTimepointId') or at.get('timepointId')
                if not (faid and fpid):
                    continue

                name_key = final_act_names.get(faid)
                label_key = final_tp_labels.get(fpid)
                if not (name_key and label_key):
                    continue

                # Text side
                taid = text_acts_by_name.get(name_key)
                tpid = text_tps_by_label.get(label_key)
                from_text = bool(taid and tpid and (taid, tpid) in text_links)

                # Vision side
                vaid = vision_acts_by_name.get(name_key)
                vpid = vision_tps_by_label.get(label_key)
                from_vision = bool(vaid and vpid and (vaid, vpid) in vision_links)

                if not (from_text or from_vision):
                    continue

                if from_text and from_vision:
                    src = 'both'
                elif from_text:
                    src = 'text'
                else:
                    src = 'vision'

                cell_map = cell_prov.setdefault(faid, {})
                existing = cell_map.get(fpid)
                if existing is None:
                    cell_map[fpid] = src
                elif existing != src:
                    # Any disagreement upgrades to 'both'
                    cell_map[fpid] = 'both'

            return cell_prov
        except Exception as e:
            print(f"[WARN] Could not compute cell-level provenance: {e}")
            return {}

    def _normalize_and_fix_soa(parsed_json, output_path=None):
        """Apply systematic normalization and quality fixes to reconciled SoA."""
        try:
            version = parsed_json.get('study', {}).get('versions', [{}])[0]
            timeline = version.get('timeline', {})
            
            # Fix 1: Deduplicate timepoints (keep only one EOS timepoint)
            if 'plannedTimepoints' in timeline:
                tps = timeline['plannedTimepoints']
                seen_eos = {}
                tps_to_keep = []
                tps_to_remove_ids = set()
                
                for tp in tps:
                    # Check for duplicate EOS timepoints
                    if 'End of Study' in tp.get('name', '') or 'EOS' in tp.get('description', ''):
                        enc_id = tp.get('encounterId', '')
                        if enc_id not in seen_eos:
                            seen_eos[enc_id] = tp
                            tps_to_keep.append(tp)
                        else:
                            # Duplicate EOS for same encounter - skip it
                            tps_to_remove_ids.add(tp['id'])
                            print(f"[FIX] Removed duplicate EOS timepoint: {tp['id']}")
                    else:
                        tps_to_keep.append(tp)
                
                timeline['plannedTimepoints'] = tps_to_keep
                
                # Remove activity-timepoint mappings for removed timepoints
                if tps_to_remove_ids and 'activityTimepoints' in timeline:
                    original_count = len(timeline['activityTimepoints'])
                    timeline['activityTimepoints'] = [
                        at for at in timeline['activityTimepoints']
                        if at.get('plannedTimepointId') not in tps_to_remove_ids
                    ]
                    removed = original_count - len(timeline['activityTimepoints'])
                    if removed > 0:
                        print(f"[FIX] Removed {removed} activity-timepoint mappings for duplicate timepoints")
            
            # Fix 2: Ensure unscheduled encounters have type and timing
            if 'encounters' in timeline:
                for enc in timeline['encounters']:
                    if 'Unscheduled' in enc.get('name', ''):
                        if 'type' not in enc:
                            enc['type'] = {'code': 'C25426', 'decode': 'Visit'}
                            print(f"[FIX] Added type to unscheduled encounter: {enc['id']}")
                        if 'timing' not in enc:
                            enc['timing'] = {'windowLabel': enc.get('windowLabel', 'UNS')}
                            print(f"[FIX] Added timing to unscheduled encounter: {enc['id']}")
            
            # Fix 3: Normalize activity group IDs (ensure zero-padding consistency)
            # Convert ag_1, ag_2, ag_3 to ag_06, ag_07, ag_08 to avoid conflicts with ag_01, ag_02, etc.
            ag_id_map = {}
            if 'activityGroups' in timeline:
                existing_ids = {ag['id'] for ag in timeline['activityGroups']}
                
                # Find max number to continue sequence
                max_num = 0
                for ag_id in existing_ids:
                    if ag_id.startswith('ag_'):
                        try:
                            num = int(ag_id.split('_')[1])
                            max_num = max(max_num, num)
                        except (ValueError, IndexError):
                            pass
                
                # Map single-digit unpaded IDs to next available
                next_num = max_num + 1 if max_num >= 5 else 6
                for ag_id in sorted(existing_ids):
                    if ag_id.startswith('ag_') and '_' in ag_id:
                        suffix = ag_id.split('_', 1)[1]
                        # If it's a single digit without zero-padding
                        if len(suffix) == 1 and suffix.isdigit():
                            new_id = f"ag_{next_num:02d}"
                            ag_id_map[ag_id] = new_id
                            next_num += 1
                            print(f"[FIX] Mapped activity group ID: {ag_id} -> {new_id}")
                
                # Apply mapping to activity groups
                for ag in timeline['activityGroups']:
                    if ag['id'] in ag_id_map:
                        ag['id'] = ag_id_map[ag['id']]
                
                # Apply mapping to activities
                if 'activities' in timeline:
                    for act in timeline['activities']:
                        if 'activityGroupId' in act and act['activityGroupId'] in ag_id_map:
                            act['activityGroupId'] = ag_id_map[act['activityGroupId']]
            
            # Fix 4: Standardize encounter timing windowLabels (Day vs Days for ranges)
            if 'encounters' in timeline:
                for enc in timeline['encounters']:
                    if 'timing' in enc and 'windowLabel' in enc['timing']:
                        label = enc['timing']['windowLabel']
                        # Check if it's a range (has hyphen or "through")
                        is_range = '-' in label or 'through' in label.lower()
                        
                        if is_range:
                            # Ranges should use "Days"
                            if label.startswith('Day ') and not label.startswith('Days '):
                                enc['timing']['windowLabel'] = 'Days ' + label[4:]
                        # Single days are fine with "Day"

            # Fix 4b: Normalize encounterId on vision-only plannedTimepoints (tp1..tp7) to canonical encounter IDs
            try:
                if 'plannedTimepoints' in timeline and 'encounters' in timeline:
                    # Build a simple name -> encounterId map, preferring the first occurrence (text encounters come first)
                    enc_name_to_id = {}
                    for enc in timeline.get('encounters', []):
                        if not isinstance(enc, dict):
                            continue
                        eid = enc.get('id')
                        name = (enc.get('name') or '').strip().lower()
                        if eid and name and name not in enc_name_to_id:
                            enc_name_to_id[name] = eid

                    for pt in timeline.get('plannedTimepoints', []):
                        if not isinstance(pt, dict):
                            continue
                        pid = pt.get('id') or pt.get('plannedTimepointId') or ''
                        enc_id = pt.get('encounterId')
                        name = (pt.get('name') or '').strip()
                        key = name.lower()

                        # Only adjust obvious vision-derived ids (tp* or enc_*)
                        if not (isinstance(pid, str) and pid.startswith('tp')) and not (
                            isinstance(enc_id, str) and enc_id.startswith('enc_')
                        ):
                            continue

                        # Direct match on visit label, e.g. "Visit 9" -> encounter_8
                        canon_enc = enc_name_to_id.get(key)

                        # Fallbacks for ET / RT
                        if not canon_enc:
                            if 'termination' in key or key == 'early termination':
                                canon_enc = (
                                    enc_name_to_id.get('visit et')
                                    or enc_name_to_id.get('et')
                                    or enc_name_to_id.get('early termination')
                                )
                            elif 'retrieval' in key or key == 'rt' or 'visit rt' in key:
                                canon_enc = (
                                    enc_name_to_id.get('visit rt')
                                    or enc_name_to_id.get('rt')
                                    or enc_name_to_id.get('retrieval')
                                )

                        if canon_enc and enc_id != canon_enc:
                            pt['encounterId'] = canon_enc
            except Exception as e:
                print(f"[WARNING] Could not normalize vision plannedTimepoint encounterIds: {e}")

            # Fix 5: Derive a ScheduleTimeline with one ScheduledActivityInstance per PlannedTimepoint
            try:
                has_schedule_timeline = bool(timeline.get('scheduleTimelines'))
                has_activity_timepoints = bool(timeline.get('activityTimepoints'))
                if not has_schedule_timeline and has_activity_timepoints:
                    # Index plannedTimepoints by ID and keep encounter linkage
                    pt_index = {}
                    for pt in timeline.get('plannedTimepoints', []):
                        if not isinstance(pt, dict):
                            continue
                        pid = pt.get('id') or pt.get('plannedTimepointId') or pt.get('timepointId')
                        if pid:
                            pt_index[pid] = pt

                    if not pt_index:
                        return parsed_json

                    # Build plannedTimepointId -> set(activityIds) from activityTimepoints
                    pt_to_acts = {}
                    for at in timeline.get('activityTimepoints', []):
                        if not isinstance(at, dict):
                            continue
                        aid = at.get('activityId')
                        pid = at.get('plannedTimepointId') or at.get('timepointId')
                        if aid and pid and pid in pt_index:
                            pt_to_acts.setdefault(pid, set()).add(aid)

                    if pt_index:
                        instances = []
                        counter = 1
                        # Sort by plannedTimepointId for stable, chronological order
                        for pid in sorted(pt_index.keys()):
                            acts = pt_to_acts.get(pid, set())
                            pt = pt_index.get(pid, {})
                            pt_name = pt.get('name') or pt.get('valueLabel') or pid
                            enc_id = pt.get('encounterId')
                            inst = {
                                'id': f"sai_{counter}",
                                'name': f"Scheduled activities for {pt_name}",
                                'description': 'Derived from activityTimepoints matrix (post-normalization).',
                                'activityIds': sorted(acts),
                                'encounterId': enc_id,
                                'instanceType': 'ScheduledActivityInstance',
                            }
                            instances.append(inst)
                            counter += 1

                        if instances:
                            first_inst_id = instances[0].get('id', 'sai_1')
                            schedule_timeline = {
                                'id': 'st_1',
                                'name': 'SoA Schedule Timeline',
                                'description': 'Derived from reconciled activityTimepoints.',
                                'mainTimeline': True,
                                'entryCondition': 'true',
                                'entryId': first_inst_id,
                                'instances': instances,
                                'instanceType': 'ScheduleTimeline',
                            }
                            timeline['scheduleTimelines'] = [schedule_timeline]
                            print(f"[FIX] Added ScheduleTimeline with {len(instances)} ScheduledActivityInstance entries derived from activityTimepoints.")
            except Exception as e:
                print(f"[WARNING] Could not derive ScheduleTimeline from activityTimepoints: {e}")
            
            # Fix 6: Extract and add proper study metadata from protocol filename
            study = parsed_json.get('study', {})
            
            # Try to extract NCT ID and study name from any available source
            import re
            nct_id = None
            protocol_name = None
            
            # First check study name
            study_name = study.get('name', '')
            if 'NCT' in study_name:
                match = re.search(r'NCT\d+', study_name)
                if match:
                    nct_id = match.group(0)
            
            # Also check output_path for NCT ID (e.g., output/Alexion_NCT04573309_Wilsons/)
            if not nct_id and output_path:
                match = re.search(r'NCT\d+', output_path)
                if match:
                    nct_id = match.group(0)
            
            # Extract protocol name from path if we have NCT ID
            if nct_id and output_path and not protocol_name:
                # Normalize path separators
                norm_path = output_path.replace('\\', '/')
                # Match pattern: Sponsor_NCT#####_Indication
                path_match = re.search(r'([A-Za-z0-9]+)_NCT\d+_([A-Za-z0-9]+)', norm_path)
                if path_match:
                    sponsor = path_match.group(1)
                    indication = path_match.group(2)
                    protocol_name = f"{sponsor} {indication}"
                    print(f"[INFO] Extracted protocol name from path: {protocol_name}")
            
            # Only add metadata if we have meaningful info
            # Check if study identifiers is empty or missing
            if nct_id and (not version.get('studyIdentifiers') or len(version.get('studyIdentifiers', [])) == 0):
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
                print(f"[FIX] Added study identifier: {nct_id}")
            
            # Add proper study name if it's still generic
            if study.get('name') in ['Auto-generated Study Name', 'Reconciled Study', None, '']:
                if protocol_name and nct_id:
                    study['name'] = f"{protocol_name} ({nct_id})"
                    print(f"[FIX] Updated study name: {study['name']}")
                elif nct_id:
                    study['name'] = f"Clinical Trial {nct_id}"
                    print(f"[FIX] Updated study name to include NCT ID")
            
            # Add study titles if missing and we have metadata
            if not version.get('titles') or len(version.get('titles', [])) == 0:
                if protocol_name and nct_id:
                    # Extract phase if present in protocol_name
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
                    print(f"[FIX] Added study titles based on protocol name")
            
        except (KeyError, IndexError, AttributeError, TypeError) as e:
            print(f"[WARNING] Error during normalization: {e}")
        
        return parsed_json

    def _enforce_union_subset(parsed_json, text_soa, vision_soa):
        """Enforce that core SoA entities/ticks are a subset of union(text, vision).

        This is a deterministic safety net that mirrors the hard constraints in the
        reconciliation prompt: the final activities, plannedTimepoints, encounters,
        activityGroups, and activityTimepoints must not introduce new IDs or
        (activityId, plannedTimepointId) pairs beyond what appears in the text and
        vision postprocessed inputs. Where the inputs carry no recognizable
        structure, this function is a no-op.
        """
        try:
            def _get_timeline(soa):
                if not isinstance(soa, dict):
                    return {}
                study = soa.get('study', {})
                versions = study.get('versions') or []
                if isinstance(versions, list) and versions:
                    return versions[0].get('timeline', {}) or {}
                return {}

            def _canon_id(v):
                if isinstance(v, str):
                    return v.replace('-', '_').strip()
                return v

            def _collect_allowed(soa):
                tl = _get_timeline(soa)
                if not tl:
                    return set(), set(), set(), set(), set()

                act_ids = set()
                pt_ids = set()
                enc_ids = set()
                ag_ids = set()
                at_pairs = set()

                for act in tl.get('activities', []):
                    if not isinstance(act, dict):
                        continue
                    aid = act.get('id') or act.get('activityId')
                    if aid:
                        act_ids.add(_canon_id(aid))

                for pt in tl.get('plannedTimepoints', []):
                    if not isinstance(pt, dict):
                        continue
                    pid = pt.get('id') or pt.get('plannedTimepointId') or pt.get('timepointId')
                    if pid:
                        pt_ids.add(_canon_id(pid))

                for enc in tl.get('encounters', []):
                    if not isinstance(enc, dict):
                        continue
                    eid = enc.get('id')
                    if eid:
                        enc_ids.add(_canon_id(eid))

                for ag in tl.get('activityGroups', []):
                    if not isinstance(ag, dict):
                        continue
                    gid = ag.get('id') or ag.get('activityGroupId')
                    if gid:
                        ag_ids.add(_canon_id(gid))

                for at in tl.get('activityTimepoints', []):
                    if not isinstance(at, dict):
                        continue
                    aid = at.get('activityId')
                    pid = at.get('plannedTimepointId') or at.get('timepointId')
                    if aid and pid:
                        at_pairs.add((_canon_id(aid), _canon_id(pid)))

                return act_ids, pt_ids, enc_ids, ag_ids, at_pairs

            def _collect_name_ticks(soa):
                tl = _get_timeline(soa)
                if not tl: return set()
                id_to_name = {}
                for act in tl.get('activities', []):
                    aid = act.get('id') or act.get('activityId')
                    name = act.get('name') or act.get('activityName')
                    if aid and name:
                        id_to_name[_canon_id(aid)] = name.strip().lower()
                name_ticks = set()
                for at in tl.get('activityTimepoints', []):
                     aid = _canon_id(at.get('activityId'))
                     pid = _canon_id(at.get('plannedTimepointId') or at.get('timepointId'))
                     if aid in id_to_name and pid:
                         name_ticks.add((id_to_name[aid], pid))
                return name_ticks

            # Build allowed sets from text and vision inputs
            a_text, pt_text, enc_text, ag_text, at_text = _collect_allowed(text_soa)
            a_vis, pt_vis, enc_vis, ag_vis, at_vis = _collect_allowed(vision_soa)

            # Collect name-based ticks for robust matching across ID mismatches
            at_text_names = _collect_name_ticks(text_soa)
            at_vis_names = _collect_name_ticks(vision_soa)

            allowed_activities = a_text | a_vis
            allowed_pts = pt_text | pt_vis
            allowed_encs = enc_text | enc_vis
            allowed_ags = ag_text | ag_vis
            allowed_at_pairs = at_text | at_vis

            # If neither input provides recognizable structure, do nothing
            if not (allowed_activities or allowed_pts or allowed_encs or allowed_at_pairs):
                return parsed_json

            final_tl = _get_timeline(parsed_json)
            if not final_tl:
                return parsed_json

            def _filter_with_ids(objs, id_keys, allowed_ids, label):
                if not isinstance(objs, list):
                    return objs
                kept = []
                dropped = 0
                for obj in objs:
                    if not isinstance(obj, dict):
                        continue
                    raw_id = None
                    for k in id_keys:
                        val = obj.get(k)
                        if val:
                            raw_id = val
                            break
                    if raw_id is None:
                        # Leave objects without IDs untouched (usually meta)
                        kept.append(obj)
                        continue
                    if _canon_id(raw_id) in allowed_ids:
                        kept.append(obj)
                    else:
                        dropped += 1
                if dropped:
                    print(f"[FIX] Dropped {dropped} {label} outside union of text+vision inputs.")
                return kept

            # Enforce subset constraint on core entity arrays
            final_tl['activities'] = _filter_with_ids(
                final_tl.get('activities', []), ['id', 'activityId'], allowed_activities, 'activities'
            )
            final_tl['plannedTimepoints'] = _filter_with_ids(
                final_tl.get('plannedTimepoints', []), ['id', 'plannedTimepointId', 'timepointId'], allowed_pts, 'plannedTimepoints'
            )
            final_tl['encounters'] = _filter_with_ids(
                final_tl.get('encounters', []), ['id'], allowed_encs, 'encounters'
            )
            final_tl['activityGroups'] = _filter_with_ids(
                final_tl.get('activityGroups', []), ['id', 'activityGroupId'], allowed_ags, 'activityGroups'
            )

            # Identify early timepoints (first 3 by order) to target smearing
            sorted_pts = sorted(final_tl.get('plannedTimepoints', []), key=lambda x: float(x.get('value')) if x.get('value') is not None else 999.0)
            early_tp_ids = { _canon_id(p.get('id')) for p in sorted_pts[:3] if p.get('id') }
            
            # Identify activities and timepoints where vision is active (has >0 ticks)
            vision_active_acts = set()
            vision_active_tps = set()
            for (vaid, vpid) in at_vis:
                vision_active_acts.add(vaid)
                vision_active_tps.add(vpid)

            # Enforce subset constraint on activityTimepoints (tick matrix)
            at_list = final_tl.get('activityTimepoints', [])
            
            # Map final activity IDs to names for fuzzy matching
            final_act_names = {}
            for act in final_tl.get('activities', []):
                aid = act.get('id') or act.get('activityId')
                name = act.get('name') or act.get('activityName')
                if aid and name:
                    final_act_names[_canon_id(aid)] = name.strip().lower()

            if isinstance(at_list, list):
                new_at = []
                dropped_pairs = 0
                dropped_text_only = 0
                dropped_smear = 0
                for at in at_list:
                    if not isinstance(at, dict):
                        continue
                    aid = at.get('activityId')
                    pid = at.get('plannedTimepointId') or at.get('timepointId')
                    if not (aid and pid):
                        continue

                    pid_canon = _canon_id(pid)
                    aid_canon = _canon_id(aid)
                    pair_key = (aid_canon, pid_canon)
                    
                    act_name = final_act_names.get(aid_canon)
                    in_vis_tick = (pair_key in at_vis) or (act_name and (act_name, pid_canon) in at_vis_names)
                    in_text_tick = (pair_key in at_text) or (act_name and (act_name, pid_canon) in at_text_names)

                    keep = False
                    in_vis_tp = pid_canon in pt_vis
                    in_text_tp = pid_canon in pt_text

                    if in_vis_tp:
                        # For late visits (tp1..tp7), vision is authoritative.
                        if in_vis_tick:
                            keep = True
                        elif in_text_tick:
                            # Present only in text for a vision timepoint: drop to avoid hallucinated ticks.
                            # EXCEPTION: If Vision missed the column entirely (no ticks), trust text.
                            if pid_canon not in vision_active_tps:
                                keep = True
                            else:
                                dropped_pairs += 1
                                dropped_text_only += 1
                        else:
                            # Not present in either input's tick matrix.
                            dropped_pairs += 1
                    elif in_text_tp:
                        # For early visits (plannedTimepoint_1.. etc.), usually retain ticks from text.
                        # BUT: Apply Anti-Smear Logic.
                        if in_text_tick and not in_vis_tick:
                            # If this is an early timepoint, and Vision has ticks for this activity elsewhere 
                            # (proving Vision saw the row), but Vision explicitly did NOT tick this early column,
                            # assume Text is hallucinating/smearing.
                            if pid_canon in early_tp_ids and aid_canon in vision_active_acts:
                                # Only drop if Vision actually saw the column (timepoint) at all.
                                # If Vision missed the entire column (e.g. PTP-1), we cannot use it as a negative signal.
                                if pid_canon in vision_active_tps:
                                    dropped_pairs += 1
                                    dropped_smear += 1
                                    # Skip enabling 'keep'
                                else:
                                    keep = True
                            else:
                                keep = True
                        elif in_text_tick or in_vis_tick:
                            keep = True
                        else:
                            dropped_pairs += 1
                    else:
                        # Timepoint not recognized in either input; treat as unsafe.
                        if pair_key in allowed_at_pairs:
                            keep = True
                        else:
                            dropped_pairs += 1

                    if keep:
                        new_at.append(at)

                if dropped_pairs:
                    msg = f"[FIX] Dropped {dropped_pairs} activityTimepoints outside safe text+vision set."
                    if dropped_text_only:
                        msg += f" ({dropped_text_only} text-only ticks removed in favor of vision where vision defined the timepoint.)"
                    if dropped_smear:
                        msg += f" ({dropped_smear} text-only 'smear' ticks removed from early visits because vision contradicted them.)"
                    print(msg)
                final_tl['activityTimepoints'] = new_at

            # Remove activityTimepoints that reference undefined activities or timepoints
            valid_act_ids = {
                a.get('id') for a in final_tl.get('activities', []) if isinstance(a, dict) and a.get('id')
            }
            valid_pt_ids = set()
            for pt in final_tl.get('plannedTimepoints', []):
                if not isinstance(pt, dict):
                    continue
                pid = pt.get('id') or pt.get('plannedTimepointId') or pt.get('timepointId')
                if pid:
                    valid_pt_ids.add(pid)

            cleaned_at = []
            dropped_invalid = 0
            for at in final_tl.get('activityTimepoints', []):
                if not isinstance(at, dict):
                    continue
                aid = at.get('activityId')
                pid = at.get('plannedTimepointId') or at.get('timepointId')
                if aid in valid_act_ids and pid in valid_pt_ids:
                    cleaned_at.append(at)
                else:
                    dropped_invalid += 1
            if dropped_invalid:
                print(f"[FIX] Dropped {dropped_invalid} activityTimepoints referencing undefined activities or timepoints.")
            final_tl['activityTimepoints'] = cleaned_at

            # Rebuild ScheduleTimeline instances from the pruned activityTimepoints (one per PlannedTimepoint)
            try:
                # Index plannedTimepoints by ID and keep encounter linkage
                pt_index = {}
                for pt in final_tl.get('plannedTimepoints', []):
                    if not isinstance(pt, dict):
                        continue
                    pid = pt.get('id') or pt.get('plannedTimepointId') or pt.get('timepointId')
                    if pid:
                        pt_index[pid] = pt

                pt_to_acts = {}
                for at in final_tl.get('activityTimepoints', []):
                    if not isinstance(at, dict):
                        continue
                    aid = at.get('activityId')
                    pid = at.get('plannedTimepointId') or at.get('timepointId')
                    if aid and pid and pid in pt_index:
                        pt_to_acts.setdefault(pid, set()).add(aid)

                instances = []
                counter = 1
                # Iterate over all plannedTimepoints so that visits without ticks are still represented.
                for pid in sorted(pt_index.keys()):
                    acts = pt_to_acts.get(pid, set())
                    pt = pt_index.get(pid, {})
                    pt_name = pt.get('name') or pt.get('valueLabel') or pid
                    enc_id = pt.get('encounterId')
                    inst = {
                        'id': f"sai_{counter}",
                        'name': f"Scheduled activities for {pt_name}",
                        'description': 'Derived from activityTimepoints matrix (post-union-enforcement).',
                        'activityIds': sorted(acts),
                        'encounterId': enc_id,
                        'instanceType': 'ScheduledActivityInstance',
                    }
                    instances.append(inst)
                    counter += 1

                if instances:
                    first_inst_id = instances[0].get('id', 'sai_1')
                    schedule_timeline = {
                        'id': 'st_1',
                        'name': 'SoA Schedule Timeline',
                        'description': 'Derived from reconciled activityTimepoints.',
                        'mainTimeline': True,
                        'entryCondition': 'true',
                        'entryId': first_inst_id,
                        'instances': instances,
                        'instanceType': 'ScheduleTimeline',
                    }
                    final_tl['scheduleTimelines'] = [schedule_timeline]
                else:
                    final_tl['scheduleTimelines'] = []
            except Exception as e:
                print(f"[WARNING] Could not rebuild ScheduleTimeline from pruned activityTimepoints: {e}")

        except Exception as e:
            print(f"[WARN] Union-subset enforcement failed: {e}")
        return parsed_json

    # ... rest of the code remains the same ...
    def _post_process_and_save(parsed_json, text_soa, vision_soa, text_prov, vision_prov, output_path):
        """Applies all post-reconciliation fixes and saves the final JSON."""
        # 0. Apply systematic normalization and fixes
        parsed_json = _normalize_and_fix_soa(parsed_json, output_path)
        
        # 1. Deep merge provenance from all sources with 'both' detection.
        prov_merged = {}
        
        # Merge text provenance
        if text_prov:
            prov_merged = _merge_prov(prov_merged, text_prov, 'text')
        
        # Merge vision provenance (will detect 'both' if entity already in text)
        if vision_prov:
            prov_merged = _merge_prov(prov_merged, vision_prov, 'vision')
        
        # Merge any provenance from LLM reconciliation output itself
        if isinstance(parsed_json, dict) and 'p2uProvenance' in parsed_json:
            prov_merged = _merge_prov(prov_merged, parsed_json['p2uProvenance'], 'llm_reconciled')
        
        # 2. Standardize all keys in the merged provenance to snake_case.
        if prov_merged:
            prov_merged = standardize_ids_recursive(prov_merged)

        # 3. Inject missing but critical data from vision SoA as a fallback.
        try:
            parsed_tl = parsed_json.get('study', {}).get('versions', [{}])[0].get('timeline', {})
            vision_tl = vision_soa.get('study', {}).get('versions', [{}])[0].get('timeline', {})

            if vision_tl:
                # If LLM misses activityTimepoints, inject from vision to restore checkmarks.
                if not parsed_tl.get('activityTimepoints') and vision_tl.get('activityTimepoints'):
                    print("[INFO] Injecting missing 'activityTimepoints' from vision SoA.")
                    parsed_tl['activityTimepoints'] = vision_tl['activityTimepoints']
                
                # If LLM misses activityGroups, inject from vision.
                if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                    print("[INFO] Injecting missing 'activityGroups' from vision SoA.")
                    parsed_tl['activityGroups'] = vision_tl['activityGroups']
        except (KeyError, IndexError, AttributeError) as e:
            print(f"[WARNING] Could not perform fallback data injection: {e}")

        # 4. Carry over other top-level metadata keys if they are missing.
        for meta_key in ['p2uOrphans', 'p2uGroupConflicts', 'p2uTimelineOrderIssues']:
            if meta_key not in parsed_json:
                if meta_key in vision_soa:
                    parsed_json[meta_key] = vision_soa[meta_key]
                elif meta_key in text_soa:
                    parsed_json[meta_key] = text_soa[meta_key]

        # 5. Add required USDM fields with defaults if missing (for schema validation)
        try:
            study = parsed_json.get('study', {})
            
            # Required Study-level fields
            if 'name' not in study:
                # Try to extract from input files or use a default
                study['name'] = (text_soa.get('study', {}).get('name') or 
                                vision_soa.get('study', {}).get('name') or 
                                "Reconciled Study")
            if 'instanceType' not in study:
                study['instanceType'] = "Study"
            
            versions = study.get('versions', [])
            if versions:
                version = versions[0]
                # Required version fields per USDM StudyVersion-Input schema
                if 'id' not in version:
                    version['id'] = 'autogen-version-id-1'
                if 'versionIdentifier' not in version:
                    version['versionIdentifier'] = '1.0.0'
                if 'instanceType' not in version:
                    version['instanceType'] = 'StudyVersion'
                if 'rationale' not in version:
                    version['rationale'] = "Version reconciled from text and vision extractions."
                if 'studyIdentifiers' not in version:
                    version['studyIdentifiers'] = []
                if 'titles' not in version:
                    version['titles'] = []
        except (KeyError, IndexError, AttributeError) as e:
            print(f"[WARNING] Could not add required USDM fields: {e}")

        # 5b. Enforce no-new-data constraint vs. union(text, vision) on core SoA entities
        parsed_json = _enforce_union_subset(parsed_json, text_soa, vision_soa)

        # 6. Derive optional cell-level provenance for activityTimepoints
        try:
            cell_prov = _build_cell_level_provenance(text_soa, vision_soa, parsed_json)
            if cell_prov:
                prov_merged['activityTimepoints'] = cell_prov
                print(f"[INFO] Added cell-level provenance for {sum(len(v) for v in cell_prov.values())} activityTimepoints.")
        except Exception as e:
            print(f"[WARN] Failed to attach cell-level provenance: {e}")

        # 7. Remove provenance from main JSON before saving (keep USDM pure)
        parsed_json.pop('p2uProvenance', None)

        # 8. Save clean USDM JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Reconciled SoA written to {output_path}")
        
        # 9. Save provenance separately (parallel file)
        prov_path = output_path.replace('.json', '_provenance.json')
        with open(prov_path, "w", encoding="utf-8") as pf:
            json.dump(prov_merged, pf, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Provenance written to {prov_path}")
        
        # 10. Print provenance summary
        if prov_merged:
            total_entities = sum(len(v) if isinstance(v, dict) else 0 for v in prov_merged.values())
            both_count = sum(1 for entities in prov_merged.values() if isinstance(entities, dict) 
                           for source in entities.values() if source == "both")
            print(f"[INFO] Provenance tracking: {total_entities} entities, {both_count} found in both text+vision")

    # --- Main Execution Logic ---
    try:
        print(f"[INFO] Loading text-extracted SoA from: {text_path}")
        text_soa = load_json(text_path)
        print(f"[INFO] Loading vision-extracted SoA from: {vision_path}")
        vision_soa = load_json(vision_path)
        
        # Load separate provenance files (Steps 7 & 8 create these)
        text_prov_path = text_path.replace('.json', '_provenance.json')
        vision_prov_path = vision_path.replace('.json', '_provenance.json')
        
        text_prov = {}
        vision_prov = {}
        
        try:
            if os.path.exists(text_prov_path):
                print(f"[INFO] Loading text provenance from: {text_prov_path}")
                text_prov = load_json(text_prov_path)
            else:
                print(f"[WARN] Text provenance file not found, using embedded provenance if available")
                text_prov = text_soa.get('p2uProvenance', {})
        except Exception as e:
            print(f"[WARN] Could not load text provenance: {e}")
            text_prov = text_soa.get('p2uProvenance', {})
        
        try:
            if os.path.exists(vision_prov_path):
                print(f"[INFO] Loading vision provenance from: {vision_prov_path}")
                vision_prov = load_json(vision_prov_path)
            else:
                print(f"[WARN] Vision provenance file not found, using embedded provenance if available")
                vision_prov = vision_soa.get('p2uProvenance', {})
        except Exception as e:
            print(f"[WARN] Could not load vision provenance: {e}")
            vision_prov = vision_soa.get('p2uProvenance', {})
            
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FATAL] Could not load or parse input SoA JSONs: {e}")
        raise

    # Prepare prompts using template system (v2.0) or fallback (v1.0)
    text_soa_json = json.dumps(text_soa, ensure_ascii=False, indent=2)
    vision_soa_json = json.dumps(vision_soa, ensure_ascii=False, indent=2)
    system_prompt, user_prompt = get_reconciliation_prompts(text_soa_json, vision_soa_json)

    tried_models = []

    # Attempt 1: Gemini (if requested)
    if 'gemini' in model_name.lower():
        tried_models.append(model_name)
        try:
            print(f"[INFO] Attempting reconciliation with Gemini model: {model_name}")
            if not genai:
                raise ImportError("Gemini library not available.")
            genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
            gemini_client = genai.GenerativeModel(model_name)
            response = gemini_client.generate_content(
                [system_prompt, user_prompt],
                generation_config=genai.types.GenerationConfig(temperature=0.1, response_mime_type="application/json")
            )
            parsed = json.loads(response.text.strip())
            _post_process_and_save(parsed, text_soa, vision_soa, text_prov, vision_prov, output_path)
            return
        except Exception as e:
            print(f"[WARNING] Gemini model '{model_name}' failed: {e}")

    # Attempt 2: OpenAI (if available and not already tried)
    if client and model_name not in tried_models:
        tried_models.append(model_name)
        try:
            print(f"[INFO] Attempting reconciliation with OpenAI model: {model_name}")
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            
            # Configure parameters based on model type
            reasoning_models = ['o1', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini']
            params = {
                "model": model_name,
                "messages": messages,
            }
            
            if model_name in reasoning_models:
                # Reasoning models do not support temperature
                params["max_completion_tokens"] = 16000
            else:
                params["temperature"] = 0.1
                # params["max_tokens"] = 16000 # Optional for non-reasoning
            
            response = client.chat.completions.create(**params)
            result = response.choices[0].message.content.strip()
            if result.startswith('```json'):
                result = result[7:-3].strip()
            parsed = json.loads(result)
            _post_process_and_save(parsed, text_soa, vision_soa, text_prov, vision_prov, output_path)
            return
        except Exception as e:
            print(f"[WARNING] OpenAI model '{model_name}' failed: {e}")
            # If GPT-5.1 was requested and Gemini is available, try Gemini fallback
            if 'gpt-5.1' in model_name.lower() and genai and os.environ.get('GOOGLE_API_KEY'):
                fallback_model = 'gemini-2.5-pro'
                tried_models.append(fallback_model)
                try:
                    print(f"[INFO] Falling back to Gemini model: {fallback_model} for reconciliation")
                    genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
                    gemini_client = genai.GenerativeModel(fallback_model)
                    response = gemini_client.generate_content(
                        [system_prompt, user_prompt],
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            response_mime_type="application/json",
                        ),
                    )
                    parsed = json.loads(response.text.strip())
                    _post_process_and_save(parsed, text_soa, vision_soa, text_prov, vision_prov, output_path)
                    return
                except Exception as e2:
                    print(f"[WARNING] Gemini fallback model '{fallback_model}' failed: {e2}")

    raise RuntimeError(f"Reconciliation failed with all attempted models: {', '.join(tried_models)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM-based reconciliation of SoA JSONs.")
    parser.add_argument("--text-input", required=True, help="Path to text-extracted SoA JSON.")
    parser.add_argument("--vision-input", required=True, help="Path to vision-extracted SoA JSON.")
    parser.add_argument("--output", required=True, help="Path to write reconciled SoA JSON.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'o3'), help="LLM model to use (e.g., 'o3', 'gpt-4o', or 'gemini-2.5-pro')")
    args = parser.parse_args()

    # Set the environment variable if it's not already set.
    # This ensures that if this script were to call another script, the model choice would propagate.
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = args.model
    print(f"[INFO] Using OpenAI model: {args.model}")

    reconcile_soa(vision_path=args.vision_input, output_path=args.output, text_path=args.text_input, model_name=args.model)
