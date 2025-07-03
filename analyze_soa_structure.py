import os
import json
import base64
from openai import OpenAI
from dotenv import load_dotenv

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

LLM_PROMPT = (
    "You are an expert in analyzing the structure of clinical trial documents, specifically the Schedule of Activities (SoA). "
    "From the provided SoA images, your task is to extract the structural elements that define the schedule's timeline and activity categories. "
    "You must use the following USDM v4.0 entity definitions to structure your output.\n\n"
    "**Entity Definitions to Extract:**\n\n"
    "1. **Encounter:** Represents a visit or visit window (typically the main column headers).\n"
    "   - Key Attributes: `id`, `name`, `description`.\n"
    "2. **PlannedTimepoint:** Represents the specific timepoints within an encounter, often used for hierarchical columns (e.g., a 'Week 4' column header under a 'Treatment' phase).\n"
    "   - Key Attributes: `id`, `name`, `description`, `value`, `valueLabel`.\n"
    "3. **ActivityGroup:** Represents optional groupings of related activities, often indicated by a merged cell spanning multiple rows in the first column (e.g., 'Screening Assessments').\n"
    "   - Key Attributes: `id`, `name`, `activities` (a list of exact activity names belonging to the group).\n\n"
    "**Output Rules:**\n"
    "- Your output MUST be a single, valid JSON object.\n"
    "- The JSON object should have top-level keys: `encounters`, `plannedTimepoints`, and `activityGroups`. Each key should contain a list of the corresponding extracted entities.\n"
    "- Focus ONLY on extracting these structural elements. Do NOT extract individual activities that aren't part of a group, and do NOT extract checkmarks.\n"
    "- Ensure all `id` fields are unique within the document.\n"
    "- If an entity type is not present (e.g., no activity groups are found), return an empty list for that key.\n"
)

def analyze_structure(image_paths, output_path, model_name='gpt-4o'):
    print(f"[INFO] Analyzing header structure for {len(image_paths)} images with model {model_name}...")
    
    content = [{"type": "text", "text": LLM_PROMPT}]
    for img_path in image_paths:
        try:
            with open(img_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"
                    }
                })
        except Exception as e:
            print(f"[ERROR] Could not read or encode image {img_path}: {e}")
            continue

    # After the loop, check if we actually added any images.
    # The content list starts with one text element.
    if len(content) <= 1:
        print("[FATAL] No images could be read or encoded. Aborting analysis.")
        return False

    messages = [{
        "role": "user",
        "content": content
    }]

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content
        if result is None:
            # Some models return None when forced JSON fails; retry without forced format
            print("[WARN] First attempt returned None – retrying without response_format...")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=2048,
            )
            result = response.choices[0].message.content
        parsed_json = json.loads(result)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] SoA header structure analysis complete. Output saved to {output_path}")
        return True

    except Exception as e:
        print(f"[FATAL] Failed to get valid response from OpenAI API: {e}")
        print("[DEBUG] Raw response text (truncated):", str(e)[:500])
        return False

if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Analyze the hierarchical structure of SoA table headers from images.")
    parser.add_argument("--images-dir", required=True, help="Directory containing the SoA image files.")
    parser.add_argument("--output", required=True, help="Path to write the output JSON file.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use.")
    args = parser.parse_args()

    try:
        image_paths = sorted([
            os.path.join(args.images_dir, f)
            for f in os.listdir(args.images_dir)
            if f.lower().endswith('.png')
        ])
        if not image_paths:
            print(f"[ERROR] No PNG images found in {args.images_dir}", file=sys.stderr)
            exit(1)
    except FileNotFoundError:
        print(f"[ERROR] Images directory not found: {args.images_dir}", file=sys.stderr)
        exit(1)

    if not analyze_structure(image_paths, args.output, args.model):
        exit(1)
