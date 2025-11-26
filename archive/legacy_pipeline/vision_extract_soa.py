"""
Vision-based SoA Extraction Script.

⚠️  DEPRECATION NOTICE:
    This script extracts FULL SoA data from images, which led to reconciliation
    complexity. The new architecture uses `extraction/header_analyzer.py` which:
    - Extracts STRUCTURE only (epochs, encounters, timepoints, groups)
    - Does NOT extract activities or tick marks
    - Provides anchor IDs for text extraction
    
    Use `main_v2.py` for the new simplified pipeline.
"""

import os
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import argparse
import io
from PIL import Image

# Use consolidated core modules
from core import extract_json_str, get_llm_client, LLMConfig
from core.llm_client import get_openai_client, get_gemini_client

# Provider layer is now always available via core
PROVIDER_LAYER_AVAILABLE = True
from llm_providers import LLMProviderFactory

# For direct API access when needed
import google.generativeai as genai
from openai import OpenAI

# Prompt template system
try:
    from prompt_templates import PromptTemplate
    TEMPLATES_AVAILABLE = True
except ImportError:
    print("[WARNING] PromptTemplate not available, using fallback prompts")
    TEMPLATES_AVAILABLE = False

# API clients are initialized on-demand via core
openai_client = None
gemini_client = None

# Load vision extraction template
def load_vision_template():
    """Load vision extraction prompt from YAML template (v2.0) or fallback to hardcoded (v1.0)."""
    if TEMPLATES_AVAILABLE:
        try:
            template = PromptTemplate.load("vision_soa_extraction", "prompts")
            print(f"[INFO] Loaded vision extraction template v{template.metadata.version}")
            return template
        except Exception as e:
            print(f"[WARNING] Could not load YAML template: {e}. Using fallback.")
    return None

VISION_TEMPLATE = load_vision_template()

# Fallback prompts (v1.0 - deprecated but kept for backward compatibility)
FALLBACK_SYSTEM_PROMPT = (
    "You are an expert medical writer specializing in authoring clinical trial protocols. "
    "Your task is to analyze the provided image(s) of a Schedule of Activities (SoA) table and extract its contents into a structured JSON format that strictly adheres to the provided USDM schema. "
    "CRITICAL: You MUST return ONLY a single, valid JSON object. Do not include any markdown formatting (like ```json), explanations, or any other text outside of the JSON object itself. "
    "Pay close attention to the provided header structure and schema definitions to ensure all entities and relationships are mapped correctly. "
    "For each column, you MUST reuse the encounters and plannedTimepoints from the headerHints JSON instead of inventing new visits or timepoints (including late visits such as Week 12, Week 26, ET, RT). "
    "For activityTimepoints, ONLY create entries where the image shows a clearly visible tick or marker in that cell (for example 'X' or a check mark symbol); never fill in a repeating pattern across visits, and when a cell is ambiguous or hard to see—especially in the later visits—you MUST leave it empty rather than guessing."
)

FALLBACK_OPENAI_SYSTEM_PROMPT = (
    "You are an expert medical writer specializing in authoring clinical trial protocols. "
    "When extracting text from the image, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. "
    "Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. "
    "To conserve space, use short but unique identifiers for all `id` fields (e.g., `act-1`, `tp-2`). "
    "Re-use the encounters and plannedTimepoints defined in the headerHints JSON; do NOT invent new visits or timepoints beyond those. "
    "For activityTimepoints, only create entries where there is a clearly visible tick or mark in the image. If a cell is ambiguous or faint—particularly in later visits—you MUST treat it as empty and omit the tick. Do NOT output any markdown, explanation, or additional text."
)

def get_vision_prompts(base_prompt: str, header_structure: str = ""):
    """
    Get system and user prompts for vision extraction, using YAML template if available.
    
    Args:
        base_prompt: Base USDM prompt with schema
        header_structure: JSON string of header structure
    
    Returns:
        tuple: (system_prompt, user_prompt_content)
    """
    if VISION_TEMPLATE:
        # Use v2.0 YAML template
        messages = VISION_TEMPLATE.render(
            base_prompt=base_prompt,
            header_structure=header_structure or "No header structure provided"
        )
        return messages[0]["content"], messages[1]["content"]
    else:
        # Use v1.0 fallback - return different prompts for Gemini vs OpenAI
        # (caller will choose which to use based on model)
        return None, base_prompt  # Signal to use fallback

# Ensure console can print UTF-8 (Windows default codepage causes logging errors)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def setup_logger():
    """Return a logger that writes to console and timestamped log file."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"soa_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logger = logging.getLogger("SOA_Extractor")
    logger.setLevel(logging.DEBUG)

    # File handler (full debug)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    # Console handler (info+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Initialise logger early so all functions can use it
logger = setup_logger()

def encode_image_to_data_url(image_path: str) -> str:
    """Return base64 data URL string for image (PNG assumed)."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"

def extract_soa_from_image_batch(image_paths, model_name, usdm_prompt):
    """Send all images to the vision-capable chat model in a single request and
    return the parsed USDM JSON, or None on failure."""
    logger.info(f"Processing {len(image_paths)} images with model '{model_name}'.")

    if 'gemini' in model_name.lower():
        global gemini_client
        if not gemini_client:
            try:
                google_api_key = os.environ.get("GOOGLE_API_KEY")
                if not google_api_key:
                    raise ValueError("GOOGLE_API_KEY environment variable not set.")
                genai.configure(api_key=google_api_key)
                gemini_client = genai.GenerativeModel(model_name)
            except Exception as e:
                logger.error(f"Failed to configure Gemini client: {e}")
                return None

        try:
            # Get prompts using template system (v2.0) or fallback (v1.0)
            system_prompt, user_prompt = get_vision_prompts(usdm_prompt, header_structure="")
            
            if system_prompt:
                # v2.0: Use template-generated prompts
                prompt_parts = [system_prompt, user_prompt]
            else:
                # v1.0: Use fallback
                prompt_parts = [FALLBACK_SYSTEM_PROMPT, usdm_prompt]
            for img_path in image_paths:
                try:
                    img = Image.open(img_path)
                    # Convert to a format Gemini can use, like PNG bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    prompt_parts.append({'inline_data': {'mime_type': 'image/png', 'data': base64.b64encode(img_byte_arr).decode('utf-8')}})
                except Exception as e:
                    logger.error(f"Failed to process image {img_path}: {e}")
                    return None

            logger.info("Sending request to Gemini API...")
            response = gemini_client.generate_content(prompt_parts, generation_config=genai.types.GenerationConfig(
                temperature=0.15,
                response_mime_type="application/json"
            ))
            response_text = response.text or ""
            result = clean_llm_json(response_text)
            if not result:
                logger.warning("Gemini vision call returned empty or unparseable content.")
                return None
            return result

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    else: # Assume OpenAI model
        # Build prompts and messages (system + user with text + images)
        system_prompt, user_prompt_text = get_vision_prompts(usdm_prompt, header_structure="")
        
        if system_prompt:
            # v2.0: Use template-generated prompts
            system_msg = {"role": "system", "content": system_prompt}
            user_content = [{"type": "text", "text": user_prompt_text}]
        else:
            # v1.0: Use fallback
            system_msg = {"role": "system", "content": FALLBACK_OPENAI_SYSTEM_PROMPT}
            user_content = [{"type": "text", "text": usdm_prompt}]
        for img_path in image_paths:
            user_content.append({"type": "image_url", "image_url": {"url": encode_image_to_data_url(img_path)}})

        messages = [system_msg, {"role": "user", "content": user_content}]
        is_gpt51 = 'gpt-5.1' in model_name.lower()
        
        # Prefer provider abstraction layer if available
        if PROVIDER_LAYER_AVAILABLE:
            try:
                provider = LLMProviderFactory.auto_detect(model_name)
                logger.info(f"Using provider layer for OpenAI vision model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider for model '{model_name}': {e}")
            else:
                # First attempt: JSON mode enabled
                config = LLMConfig(
                    temperature=0.15,
                    max_tokens=8192,
                    json_mode=True,
                )
                try:
                    response = provider.generate(messages, config)
                    response_text = response.content or ""
                    result = clean_llm_json(response_text)
                    if not result and is_gpt51:
                        logger.info("Empty or unparseable response from GPT-5.1 via provider (JSON mode); falling back to Gemini 2.5 Pro.")
                        return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
                    return result
                except Exception as e:
                    logger.warning(f"Provider-based OpenAI call failed (JSON mode). Retrying without JSON mode: {e}")
                    try:
                        config_no_json = LLMConfig(
                            temperature=0.15,
                            max_tokens=8192,
                            json_mode=False,
                        )
                        response = provider.generate(messages, config_no_json)
                        response_text = response.content or ""
                        result = clean_llm_json(response_text)
                        if not result and is_gpt51:
                            logger.info("Empty or unparseable response from GPT-5.1 via provider (no JSON mode); falling back to Gemini 2.5 Pro.")
                            return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
                        return result
                    except Exception as e2:
                        logger.error(f"Provider-based OpenAI call failed again: {e2}")
                        if is_gpt51:
                            logger.info("Falling back to Gemini 2.5 Pro for vision extraction (OpenAI calls failing via provider layer).")
                            return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
                        # If provider path failed and not GPT-5.1, fall through to legacy client as a last resort
                        pass
        
        # Legacy OpenAI client path (used if provider layer is unavailable or failed)
        global openai_client
        if not openai_client:
            try:
                openai_api_key = os.environ.get("OPENAI_API_KEY")
                if not openai_api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set.")
                openai_client = OpenAI(api_key=openai_api_key)
            except Exception as e:
                logger.error(f"Failed to configure OpenAI client: {e}")
                if is_gpt51:
                    logger.info("Falling back to Gemini 2.5 Pro for vision extraction (OpenAI client unavailable).")
                    return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
                return None
        
        # Configure OpenAI parameters with reasoning-model support (GPT-5 family, o3)
        reasoning_models = ['o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini']
        base_params = {
            "model": model_name,
            "messages": messages,
        }
        if model_name not in reasoning_models:
            base_params["temperature"] = 0.15
            base_params["max_tokens"] = 8192
        else:
            base_params["max_completion_tokens"] = 8192
        
        try:
            params = dict(base_params)
            params["response_format"] = {"type": "json_object"}
            response = openai_client.chat.completions.create(**params)
        except Exception as e:
            logger.warning(f"Retrying legacy OpenAI call without response_format due to API error: {e}")
            try:
                response = openai_client.chat.completions.create(**base_params)
            except Exception as e2:
                logger.error(f"Legacy OpenAI API error on second attempt: {e2}")
                if is_gpt51:
                    logger.info("Falling back to Gemini 2.5 Pro for vision extraction (OpenAI calls failing).")
                    return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
                return None
        
        try:
            response_text = (response.choices[0].message.content if response.choices else "") or ""
            result = clean_llm_json(response_text)
            if not result and is_gpt51:
                logger.info("Empty or unparseable response from GPT-5.1; falling back to Gemini 2.5 Pro for vision extraction.")
                return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
            return result
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            logger.debug(f"Raw response content:\n{response.choices[0].message.content if response.choices else 'No response content'}")
            if is_gpt51:
                logger.info("Falling back to Gemini 2.5 Pro for vision extraction (JSON parsing error).")
                return extract_soa_from_image_batch(image_paths, 'gemini-2.5-pro', usdm_prompt)
            return None

def repair_json_with_llm(broken_json_str):
    """Uses a lightweight LLM to repair a broken JSON string."""
    logger.info("Attempting to repair JSON with a second LLM call...")
    try:
        # Use a fast and cheap model for the repair task
        repair_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        repair_prompt = (
            "The following string is a malformed JSON object that was extracted from a document. "
            "Your task is to correct any syntax errors (e.g., missing commas, quotes, brackets) and return ONLY the valid, corrected JSON object. "
            "Do not include any explanation, markdown, or other text outside of the JSON object itself. Ensure the corrected output is a single, complete JSON object."
            f"\n\nMalformed JSON:```json\n{broken_json_str}\n```"
        )

        response = repair_model.generate_content(
            repair_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        repaired_json = json.loads(response.text)
        logger.info("[SUCCESS] JSON repaired and parsed successfully.")
        return repaired_json
    except Exception as e:
        logger.error(f"JSON repair failed: {e}")
        logger.debug(f"Original broken string that failed repair:\n{broken_json_str}")
        return None

def clean_llm_json(text_response):
    """Extract and parse JSON from an LLM response using shared extractor, with optional repair.

    Returns a parsed JSON object when possible; on unrecoverable errors returns None
    so that callers can decide how to handle it (e.g., try a fallback model).
    """
    # Handle completely empty responses early – there is nothing to repair.
    if text_response is None:
        logger.warning("LLM response was None; skipping JSON extraction.")
        return None
    if isinstance(text_response, str) and not text_response.strip():
        logger.warning("LLM response was empty string; skipping JSON repair.")
        return None

    try:
        # First try the shared defensive extractor + json.loads
        cleaned_str = extract_json_str(text_response)
        return json.loads(cleaned_str)
    except Exception as e:
        logger.warning(f"Primary JSON extraction failed, attempting repair: {e}")
        repaired_json = repair_json_with_llm(text_response)
        if repaired_json is not None:
            return repaired_json
        # If repair fails, signal failure to caller
        return None

def augment_header_structure(header_structure):
    """
    Parses and augments header structure to ensure all valid columns are represented as timepoints.
    Specifically, promotes Encounters like 'ET', 'RT' (that don't start with 'Visit') to PlannedTimepoints
    if they aren't already covered, preventing them from being dropped.
    
    Returns:
        tuple: (encounters_list, planned_timepoints_list, activity_groups_list)
    """
    if not isinstance(header_structure, dict):
        return [], [], []

    col_h = header_structure.get("columnHierarchy", {}) or header_structure.get("column_hierarchy", {})
    row_h = header_structure.get("rowHierarchy", {}) or header_structure.get("row_hierarchy", {})

    encs = [e for e in (col_h.get("encounters", []) or []) if isinstance(e, dict) and e.get("id")]
    pts = [p for p in (col_h.get("plannedTimepoints", []) or []) if isinstance(p, dict) and p.get("id")]
    groups = [g for g in (row_h.get("activityGroups", []) or []) if isinstance(g, dict) and g.get("id")]

    # Augment plannedTimepoints with special encounters (e.g. ET, RT)
    # Heuristic: If encounter name doesn't start with "Visit" (case-insensitive), assume it's a named column
    # that might be missing from the explicit timepoint rows.
    existing_pt_names = set((p.get("name") or "").strip().lower() for p in pts)
    
    for enc in encs:
        name = (enc.get("name") or "").strip()
        if not name:
            continue
        
        # Check if already exists
        if name.lower() in existing_pt_names:
            continue
            
        # Heuristic: promote non-"Visit X" encounters
        if not name.lower().startswith("visit"):
            # This is likely a special visit (ET, RT, Screening, Baseline, etc.)
            # Add it as a valid timepoint target
            pts.append({
                "id": enc.get("id"), # Reuse encounter ID as timepoint ID (or should we synthesis? reuse is fine for vision)
                "name": name,
                "description": enc.get("description", ""),
                "value": None,
                "valueLabel": name
            })
            existing_pt_names.add(name.lower())
            
    return encs, pts, groups

def merge_soa_jsons(soa_parts, header_structure=None):
    if not soa_parts:
        return None

    import copy

    # Dictionaries to hold unique items by a meaningful key (name).
    unique_timepoints = {}
    unique_activities = {}
    # This will hold tuples of (activity_name, timepoint_name) to represent checkmarks
    unique_activity_timepoint_pairs = set()

    # Optional header-driven timepoint information (from analyze_soa_structure)
    header_pts = []
    header_pts_by_name = {}
    header_pts_by_label = {}
    
    if header_structure:
        _, augmented_pts, _ = augment_header_structure(header_structure)
        header_pts = augmented_pts
        for pt in header_pts:
            name_key = (pt.get('name') or pt.get('label') or '').strip().lower()
            if name_key:
                header_pts_by_name.setdefault(name_key, pt)
            label_key = (pt.get('valueLabel') or '').strip().lower()
            if label_key:
                header_pts_by_label.setdefault(label_key, pt)

    import re
    split_pattern = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
    # --- PASS 1: Collect all unique entities and relationships by NAME --- 
    for part in soa_parts:
        # Robustness check: ensure the part has the expected nested structure.
        if not isinstance(part, dict) or 'study' not in part or not isinstance(part.get('study'), dict) or 'versions' not in part['study'] or not part['study']['versions']:
            logger.warning(f"Skipping malformed SoA part: {str(part)[:200]}")
            continue

        timeline = part['study']['versions'][0].get('timeline', {})
        
        # Create local maps for this part's LLM-generated IDs to names
        part_activity_id_to_name = {a['id']: a['name'] for a in timeline.get('activities', []) if a.get('id') and a.get('name')}
        part_timepoint_id_to_name = {t['id']: t['name'] for t in timeline.get('plannedTimepoints', []) if t.get('id') and t.get('name')}

        # Collect unique activities and timepoints, keyed by name
        for act in timeline.get('activities', []):
            if act.get('name'):
                unique_activities[act['name']] = act
        
        for enc in timeline.get('encounters', []):
            # Split concatenated timing in name
            if isinstance(enc.get('name'), str):
                m = split_pattern.match(enc['name'])
                if m:
                    enc['name'] = m.group(1).strip()
                    timing_label = m.group(2).strip()
                    enc['timing'] = enc.get('timing') or {}
                    if 'windowLabel' not in enc['timing']:
                        enc['timing']['windowLabel'] = timing_label
            enc_name = enc.get('name') or enc.get('label')
            unique_activities[enc_name] = enc

        for tp in timeline.get('plannedTimepoints', []):
            # Split concatenated label if needed ("Visit 1 (Week -2)")
            if isinstance(tp.get('name'), str):
                m = split_pattern.match(tp['name'])
                if m:
                    tp['name'] = m.group(1).strip()
                    if not tp.get('description'):
                        tp['description'] = m.group(2).strip()
            tp_name = tp.get('name') or tp.get('label')
            unique_timepoints[tp['name']] = tp

        # Collect unique (activity, timepoint) checkmark pairs using names
        for at in timeline.get('activityTimepoints', []):
            act_id = at.get('activityId')
            tp_id = at.get('plannedTimepointId')
            if act_id in part_activity_id_to_name and tp_id in part_timepoint_id_to_name:
                act_name = part_activity_id_to_name[act_id]
                tp_name = part_timepoint_id_to_name[tp_id]
                unique_activity_timepoint_pairs.add((act_name, tp_name))

    # --- PASS 2: Build the final, merged_soa JSON with new, consistent IDs --- #

    # Find a base structure to copy metadata from (e.g., usdmVersion)
    # Require at minimum a Study with a non-empty versions list.
    base_soa = next(
        (
            p
            for p in soa_parts
            if isinstance(p, dict)
            and isinstance(p.get('study'), dict)
            and isinstance(p['study'].get('versions'), list)
            and p['study']['versions']
        ),
        None,
    )
    if not base_soa:
        logger.error("No valid SoA structure found in any of the parts to merge.")
        return None

    final_soa = copy.deepcopy(base_soa)
    # Ensure there is a timeline object to populate, even if the base lacked one
    try:
        version0 = final_soa['study']['versions'][0]
        if 'timeline' not in version0 or not isinstance(version0.get('timeline'), dict):
            version0['timeline'] = {}
        final_timeline = version0['timeline']
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Base SoA structure missing expected study/versions layout: {e}")
        return None
    
    # Re-index activities and create a name -> new_id map
    final_activities = []
    activity_name_to_new_id = {}
    for i, (name, act_data) in enumerate(unique_activities.items()):
        new_id = f"act{i+1}"
        act_data['id'] = new_id
        final_activities.append(act_data)
        activity_name_to_new_id[name] = new_id

    # Map LLM timepoint names onto header-defined plannedTimepoints when available
    llm_tp_to_hdr_id = {}
    if header_pts:
        for name, tp_data in unique_timepoints.items():
            key = (name or '').strip().lower()
            cand = header_pts_by_name.get(key)
            if not cand:
                vlabel = (tp_data.get('valueLabel') or tp_data.get('label') or '').strip().lower()
                if vlabel:
                    cand = header_pts_by_label.get(vlabel)
            if cand:
                llm_tp_to_hdr_id[name] = cand['id']
            else:
                logger.warning(f"[MERGE] No header timepoint match for vision timepoint '{name}'")

    # Build final plannedTimepoints and name->id map
    final_timepoints = []
    timepoint_name_to_new_id = {}
    if header_pts:
        # Use header-defined timepoints as canonical columns
        final_timepoints = list(header_pts)
        timepoint_name_to_new_id = dict(llm_tp_to_hdr_id)
    else:
        # Fallback to LLM-generated timepoints when no header structure is available
        for i, (name, tp_data) in enumerate(unique_timepoints.items()):
            new_id = f"tp{i+1}"
            tp_data['id'] = new_id
            final_timepoints.append(tp_data)
            timepoint_name_to_new_id[name] = new_id

    # Build final activityTimepoints (the checkmarks) using the mapped IDs
    final_activity_timepoints = []
    dropped_pairs = 0
    for act_name, tp_name in unique_activity_timepoint_pairs:
        if act_name not in activity_name_to_new_id:
            continue
        if tp_name not in timepoint_name_to_new_id:
            dropped_pairs += 1
            continue
        final_activity_timepoints.append({
            "activityId": activity_name_to_new_id[act_name],
            "plannedTimepointId": timepoint_name_to_new_id[tp_name]
        })
    if dropped_pairs:
        logger.info(f"[MERGE] Dropped {dropped_pairs} (activity, timepoint) pairs that could not be aligned to header timepoints.")

    # Populate the final timeline, ensuring a consistent order
    final_timeline['activities'] = sorted(final_activities, key=lambda x: int(x['id'][3:]))
    if header_pts:
        # Preserve header order for timepoints (as they appear in header structure)
        final_timeline['plannedTimepoints'] = final_timepoints
    else:
        # Maintain numeric order of synthetic tp ids when no header is available
        final_timeline['plannedTimepoints'] = sorted(final_timepoints, key=lambda x: int(x['id'][2:]))
    final_timeline['activityTimepoints'] = final_activity_timepoints
    final_timeline['activityGroups'] = []  # Not currently handled

    return final_soa

def extract_and_merge_soa_from_images(image_paths, model_name, usdm_prompt, header_structure=None):
    all_soa_parts = []
    # Process images one by one to get separate JSON outputs
    for image_path in image_paths:
        logger.info(f"Processing image: {image_path}")
        # We use the batch extractor but with a single image
        result = extract_soa_from_image_batch([image_path], model_name, usdm_prompt)
        if result:
            logger.info(f"[SUCCESS] Extracted SoA from {image_path}.")
            all_soa_parts.append(result)
        else:
            logger.warning(f"[FAILURE] No JSON returned from {image_path}.")

    if not all_soa_parts:
        logger.fatal("Vision extraction failed for all images. No valid JSON produced.")
        return None

    logger.info(f"Successfully extracted SoA data from {len(all_soa_parts)} images. Merging...")
    merged_soa = merge_soa_jsons(all_soa_parts, header_structure=header_structure)
    # Tag provenance for downstream auditing
    prov_map = merged_soa.setdefault('p2uProvenance', {}) if isinstance(merged_soa, dict) else {}
    def _tag(container_key, items):
        if not isinstance(merged_soa, dict):
            return
        cm = prov_map.setdefault(container_key, {})
        for obj in items:
            if isinstance(obj, dict) and obj.get('id'):
                cm[obj['id']] = 'vision'
    tl = merged_soa.get('study', {}).get('versions', [{}])[0].get('timeline', {}) if isinstance(merged_soa, dict) else {}
    _tag('plannedTimepoints', tl.get('plannedTimepoints', []))
    _tag('activities', tl.get('activities', []))
    _tag('encounters', tl.get('encounters', []))
    return merged_soa

def get_llm_prompt(prompt_file=None, header_structure_file=None):
    base_prompt = ''
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    else:
        # Fallback to a default prompt if file doesn't exist
        base_prompt = (
            "You are an expert in clinical trial protocols and CDISC USDM v4.0. "
            "Your task is to extract the Schedule of Activities (SoA) from the provided table image. "
            "HARD CONSTRAINTS: All entities and values must be derived only from what is visibly present in the SoA table and from the headerHints JSON; "
            "do NOT create activities, planned timepoints, encounters, epochs, arms, or activity-timepoint links that are not clearly visible or described. "
            "For activityTimepoints, only create entries where the image shows a visible tick or marker in that cell (for example 'X' or a check mark symbol); "
            "never infer ticks from phrases like 'at each visit' or from clinical expectations, and if a cell is ambiguous or unclear, leave it empty. "
            "Return EXACTLY one JSON object in USDM v4.0 Wrapper-Input format, with no additional commentary."
        )

    if header_structure_file and os.path.exists(header_structure_file):
        try:
            with open(header_structure_file, 'r', encoding='utf-8') as f:
                structure_data = json.load(f)

            # New header structure uses columnHierarchy/rowHierarchy with augmentation
            hdr_encs, hdr_pts, hdr_groups = augment_header_structure(structure_data)

            hints = {
                "encounters": [
                    {
                        "id": e.get("id"),
                        "name": e.get("name", ""),
                        "description": e.get("description", "")
                    } for e in hdr_encs if isinstance(e, dict) and e.get("id")
                ],
                "plannedTimepoints": [
                    {
                        "id": pt.get("id"),
                        "name": pt.get("name", ""),
                        "description": pt.get("description", ""),
                        "value": pt.get("value"),
                        "valueLabel": pt.get("valueLabel", "")
                    } for pt in hdr_pts if isinstance(pt, dict) and pt.get("id")
                ],
                "activityGroups": [
                    {
                        "id": ag.get("id"),
                        "name": ag.get("name", ""),
                        "activities": ag.get("activities", [])
                    } for ag in hdr_groups if isinstance(ag, dict) and ag.get("id")
                ],
            }

            header_prompt_part = (
                "\n\nThe following JSON object (headerHints) describes the detected table structure. "
                "Use this information strictly to assign correct IDs, groupings, and labels. "
                "You may copy values and IDs from headerHints but MUST NOT invent new IDs, columns, timepoints, or activity groups beyond what headerHints provides.\n" +
                "```json\n" + json.dumps({"headerHints": hints}, indent=2) + "\n```\n"
            )
            return base_prompt + header_prompt_part
        except Exception as e:
            print(f"[WARN] Could not read or parse header structure file {header_structure_file}: {e}")

    return base_prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("--images-dir", required=True, help="Directory containing the SoA image files.")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gemini-2.5-pro'), help="LLM model to use (e.g., 'gemini-2.5-pro', 'gpt-4o').")
    parser.add_argument("--prompt-file", required=True, help="Path to the LLM prompt file.")
    parser.add_argument("--header-structure-file", required=True, help="Path to the header structure JSON file.")

    args = parser.parse_args()

    try:
        image_paths_to_process = sorted([
            os.path.join(args.images_dir, f)
            for f in os.listdir(args.images_dir)
            if f.lower().endswith('.png')
        ])
        if not image_paths_to_process:
            logger.error(f"No PNG images found in {args.images_dir}")
            sys.exit(1)
    except FileNotFoundError:
        logger.error(f"Images directory not found: {args.images_dir}")
        sys.exit(1)

    usdm_prompt = get_llm_prompt(args.prompt_file, args.header_structure_file)

    # Load header structure JSON so merge_soa_jsons can align timepoints/encounters
    header_structure = None
    if args.header_structure_file and os.path.exists(args.header_structure_file):
        try:
            with open(args.header_structure_file, 'r', encoding='utf-8') as hf:
                header_structure = json.load(hf)
        except Exception as e:
            logger.warning(f"Could not load header structure for merge: {e}")

    final_soa_json = extract_and_merge_soa_from_images(
        image_paths_to_process,
        args.model,
        usdm_prompt,
        header_structure=header_structure,
    )

    if not final_soa_json:
        logger.fatal("Vision extraction failed because no valid JSON could be produced.")
        sys.exit(1)

    # The final_soa_json from merging should already be in the correct Wrapper-Input format.
    # We just need to ensure the study object and its keys are robust.
    if 'study' not in final_soa_json:
        final_soa_json['study'] = {} # Should not happen with new merge logic, but safe.
    
    # Ensure attributes and relationships keys exist in the study object
    if 'attributes' not in final_soa_json['study']:
        final_soa_json['study']['attributes'] = {}
    if 'relationships' not in final_soa_json['study']:
        final_soa_json['study']['relationships'] = {}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_soa_json, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Wrote merged_soa SoA vision output to {args.output}")
