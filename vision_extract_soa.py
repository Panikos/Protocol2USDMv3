import os
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from json_utils import clean_llm_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

    system_msg = {
        "role": "system",
        "content": (
            "You are an expert medical writer specializing in authoring clinical trial protocols. "
            "When extracting text from the image, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. "
            "Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. "
            "To conserve space, use short but unique identifiers for all `id` fields (e.g., `act-1`, `tp-2`). "
            "Do NOT output any markdown, explanation, or additional text."
        ),
    }

    # Build user message: prompt text + each image as a base-64 data URL
    user_content = [{"type": "text", "text": usdm_prompt}]
    for img_path in image_paths:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": encode_image_to_data_url(img_path)},
            }
        )

    messages = [system_msg, {"role": "user", "content": user_content}]

    # Try strict JSON enforcement first; if the API refuses, fall back.
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.15,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(f"Retrying without response_format due to API error: {e}")
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.15,
                max_tokens=8192,
            )
        except Exception as e2:
            logger.error(f"OpenAI API error on second attempt: {e2}")
            return None
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None

    # Log finish_reason and token usage for diagnostics
    finish_reason = response.choices[0].finish_reason if response and response.choices else 'n/a'
    logger.info(f"finish_reason={finish_reason}, usage={getattr(response, 'usage', {})}")

    content = response.choices[0].message.content if response and response.choices else None
    if not content:
        logger.warning("Model returned empty content. Attempting fallback with minimal prompt.")
        logger.debug(f"Full response object: {response}")

        # Build a much shorter prompt that often bypasses safety filters
        minimal_prompt = (
            "Return ONLY a valid JSON object that conforms to the Wrapper-Input schema "
            "for the Schedule of Activities (SoA) found in the supplied image."
        )
        minimal_user_content = [
            {"type": "text", "text": minimal_prompt}
        ]
        for img_path in image_paths:
            minimal_user_content.append({
                "type": "image_url",
                "image_url": {"url": encode_image_to_data_url(img_path)},
            })

        minimal_messages = [system_msg, {"role": "user", "content": minimal_user_content}]

        try:
            response_retry = client.chat.completions.create(
                model=model_name,
                messages=minimal_messages,
                temperature=0.15,
                max_tokens=8192,
            )
            finish_reason_retry = response_retry.choices[0].finish_reason if response_retry and response_retry.choices else 'n/a'
            logger.info(f"[FALLBACK] finish_reason={finish_reason_retry}, usage={getattr(response_retry, 'usage', {})}")
            content_retry = response_retry.choices[0].message.content if response_retry and response_retry.choices else None
            if not content_retry:
                logger.warning("Fallback also returned empty content.")
                logger.debug(f"[FALLBACK] Full response object: {response_retry}")
                return None
            content = content_retry
        except Exception as e:
            logger.error(f"Fallback API call failed: {e}")
            return None

    logger.debug(f"Raw LLM output: {content}")
    cleaned = clean_llm_json(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
        return None

def merge_soa_jsons(soa_parts):
    if not soa_parts:
        return None

    import copy

    # Dictionaries to hold unique items by a meaningful key (name).
    unique_timepoints = {}
    unique_activities = {}
    # This will hold tuples of (activity_name, timepoint_name) to represent checkmarks
    unique_activity_timepoint_pairs = set()

    # --- PASS 1: Collect all unique entities and relationships by NAME --- 
    for part in soa_parts:
        if not ('study' in part and 'versions' in part['study'] and part['study']['versions']):
            continue

        timeline = part['study']['versions'][0].get('timeline', {})
        
        # Create local maps for this part's LLM-generated IDs to names
        part_activity_id_to_name = {a['id']: a['name'] for a in timeline.get('activities', []) if a.get('id') and a.get('name')}
        part_timepoint_id_to_name = {t['id']: t['name'] for t in timeline.get('plannedTimepoints', []) if t.get('id') and t.get('name')}

        # Collect unique activities and timepoints, keyed by name
        for act in timeline.get('activities', []):
            if act.get('name'):
                unique_activities[act['name']] = act
        
        for tp in timeline.get('plannedTimepoints', []):
            if tp.get('name'):
                unique_timepoints[tp['name']] = tp

        # Collect unique (activity, timepoint) checkmark pairs using names
        for at in timeline.get('activityTimepoints', []):
            act_id = at.get('activityId')
            tp_id = at.get('plannedTimepointId')
            if act_id in part_activity_id_to_name and tp_id in part_timepoint_id_to_name:
                act_name = part_activity_id_to_name[act_id]
                tp_name = part_timepoint_id_to_name[tp_id]
                unique_activity_timepoint_pairs.add((act_name, tp_name))

    # --- PASS 2: Build the final, merged JSON with new, consistent IDs --- #

    # Find a base structure to copy metadata from (e.g., usdmVersion)
    base_soa = next((p for p in soa_parts if 'study' in p), None)
    if not base_soa:
        logger.error("No valid SoA structure found in any of the parts to merge.")
        return None
        
    final_soa = copy.deepcopy(base_soa)
    final_timeline = final_soa['study']['versions'][0]['timeline']
    
    # Re-index activities and create a name -> new_id map
    final_activities = []
    activity_name_to_new_id = {}
    for i, (name, act_data) in enumerate(unique_activities.items()):
        new_id = f"act{i+1}"
        act_data['id'] = new_id
        final_activities.append(act_data)
        activity_name_to_new_id[name] = new_id
        
    # Re-index timepoints and create a name -> new_id map
    final_timepoints = []
    timepoint_name_to_new_id = {}
    for i, (name, tp_data) in enumerate(unique_timepoints.items()):
        new_id = f"tp{i+1}"
        tp_data['id'] = new_id
        final_timepoints.append(tp_data)
        timepoint_name_to_new_id[name] = new_id

    # Build final activityTimepoints (the checkmarks) using the new, consistent IDs
    final_activity_timepoints = []
    for act_name, tp_name in unique_activity_timepoint_pairs:
        if act_name in activity_name_to_new_id and tp_name in timepoint_name_to_new_id:
            final_activity_timepoints.append({
                "activityId": activity_name_to_new_id[act_name],
                "plannedTimepointId": timepoint_name_to_new_id[tp_name]
            })

    # Populate the final timeline, ensuring a consistent order
    final_timeline['activities'] = sorted(final_activities, key=lambda x: int(x['id'][3:]))
    final_timeline['plannedTimepoints'] = sorted(final_timepoints, key=lambda x: int(x['id'][2:]))
    final_timeline['activityTimepoints'] = final_activity_timepoints
    final_timeline['activityGroups'] = [] # Not currently handled

    return final_soa

def extract_and_merge_soa_from_images(image_paths, model_name, usdm_prompt):
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
    merged_soa = merge_soa_jsons(all_soa_parts)
    return merged_soa

def get_llm_prompt(prompt_file=None, header_structure_file=None):
    base_prompt = ''
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    else:
        # Fallback to a default prompt if file doesn't exist
        base_prompt = 'You are an expert in clinical trial protocols. Extract the Schedule of Activities (SoA) from this image in USDM v4.0 format.'

    if header_structure_file and os.path.exists(header_structure_file):
        try:
            with open(header_structure_file, 'r', encoding='utf-8') as f:
                structure_data = json.load(f)

            # Add timepoint header structure to the prompt
            header_prompt_part = "\n\nTo guide your extraction, here is the hierarchical structure of the table I have identified:\n"
            header_prompt_part += "\n--- TIMEPOINT COLUMN HEADERS ---\n"
            for tp in structure_data.get('timepoints', []):
                header_prompt_part += f"- Column '{tp.get('id')}' has a primary name of '{tp.get('primary_name')}'"
                if tp.get('secondary_name'):
                    header_prompt_part += f" and a secondary name/date of '{tp.get('secondary_name')}'"
                header_prompt_part += '.\n'
            
            # Add activity group structure to the prompt
            header_prompt_part += "\n--- ACTIVITY ROW GROUPINGS ---\n"
            for ag in structure_data.get('activity_groups', []):
                header_prompt_part += f"- The group '{ag.get('group_name')}' contains the following activities: {', '.join(ag.get('activities', []))}\n"

            header_prompt_part += "\nPlease use this structural information to correctly interpret the table's columns, rows, and their relationships during your extraction. Ensure that the 'activityGroupId' in your output correctly references the groups identified here."
            return base_prompt + header_prompt_part
        except Exception as e:
            print(f"[WARN] Could not read or parse header structure file {header_structure_file}: {e}")

    return base_prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("--images-dir", required=True, help="Directory containing the SoA image files.")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use.")
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

    final_soa_json = extract_and_merge_soa_from_images(
        image_paths_to_process,
        args.model,
        usdm_prompt,
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
    
    logger.info(f"Wrote merged SoA vision output to {args.output}")
