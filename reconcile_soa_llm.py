import os
import json
from dotenv import load_dotenv
from pathlib import Path

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

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
openai_api_key = os.environ.get("OPENAI_API_KEY")
if OpenAI and openai_api_key:
    client = OpenAI(api_key=openai_api_key)
else:
    client = None

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
    "Compare and reconcile the two objects, resolving any discrepancies by using your best judgment and the USDM v4.0 standard.\n"
    "IMPORTANT: Output ALL column headers (timepoints) from the table EXACTLY as shown, including ranges (e.g., 'Day 2-3', 'Day 30-35'), even if they appear similar or redundant. Do NOT drop or merge any timepoints unless they are exact duplicates.\n"
    "When creating the `plannedTimepoints` array, you MUST standardize the `name` for each timepoint. If a timepoint has a simple `name` (e.g., 'Screening') and a more detailed `description` (e.g., 'Visit 1 / Week -2'), combine them into a single, user-friendly `name` in the format 'Visit X (Week Y)'. For example, a timepoint with `name: 'Screening'` and `description: 'Visit 1 / Week -2'` should be reconciled into a final timepoint with `name: 'Visit 1 (Week -2)'`. Preserve the original `description` field as well.\n"
    "CRITICAL: When reconciling the `activityTimepoints` (the matrix of checkmarks), you MUST prioritize the data from the VISION-EXTRACTED SoA. The vision model is more reliable for identifying which activities occur at which timepoints. If the vision JSON indicates a checkmark (`isPerformed: true`) for an activity at a timepoint, ensure it is present in the final output, even if the text JSON disagrees.\n"
    "Your output must be a single, unified JSON object that:\n"
    "- Strictly conforms to the USDM v4.0 Wrapper-Input schema (including the top-level keys: study, usdmVersion, systemName, systemVersion).\n"
    "- The study object must include all required and as many optional fields as possible, including a fully detailed SoA: activities, plannedTimepoints, activityGroups, activityTimepoints, and all appropriate groupings and relationships.\n"
    "- All objects must have their correct instanceType. Use unique IDs and preserve correct mappings.\n"
    "- The output must be ready for validation and for visualization in a SoA table viewer (with correct groupings, milestones, and 'ticks' as per the protocol template).\n"
    "Output ONLY valid JSON (no markdown, comments, or explanations)."
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

    def _post_process_and_save(parsed_json, text_soa, vision_soa, text_prov, vision_prov, output_path):
        """Applies all post-reconciliation fixes and saves the final JSON."""
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
                # Required version fields per USDM schema
                if 'rationale' not in version:
                    version['rationale'] = "Version reconciled from text and vision extractions."
                if 'studyIdentifiers' not in version:
                    version['studyIdentifiers'] = []
                if 'titles' not in version:
                    version['titles'] = []
        except (KeyError, IndexError, AttributeError) as e:
            print(f"[WARNING] Could not add required USDM fields: {e}")

        # 6. Remove provenance from main JSON before saving (keep USDM pure)
        parsed_json.pop('p2uProvenance', None)

        # 7. Save clean USDM JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Reconciled SoA written to {output_path}")
        
        # 8. Save provenance separately (parallel file)
        prov_path = output_path.replace('.json', '_provenance.json')
        with open(prov_path, "w", encoding="utf-8") as pf:
            json.dump(prov_merged, pf, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Provenance written to {prov_path}")
        
        # 9. Print provenance summary
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
            response = client.chat.completions.create(model=model_name, messages=messages, max_tokens=16384, temperature=0.1)
            result = response.choices[0].message.content.strip()
            if result.startswith('```json'):
                result = result[7:-3].strip()
            parsed = json.loads(result)
            _post_process_and_save(parsed, text_soa, vision_soa, text_prov, vision_prov, output_path)
            return
        except Exception as e:
            print(f"[WARNING] OpenAI model '{model_name}' failed: {e}")

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
