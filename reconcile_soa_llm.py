import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

LLM_PROMPT = (
    "You are an expert in clinical trial data curation. "
    "You will be given two JSON objects, each representing a Schedule of Activities (SoA) extracted from a clinical trial protocol. "
    "Both are intended to conform to the USDM v4.0 model. "
    "Compare and reconcile the two objects, resolving any discrepancies by using your best judgment and the USDM v4.0 standard. "
    "Output a single, unified SoA JSON object that is fully valid and best reflects the protocol's intent. "
    "Output ONLY the JSON, with no comments or explanations."
)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def reconcile_soa(text_path, vision_path, output_path):
    text_soa = load_json(text_path)
    vision_soa = load_json(vision_path)
    user_content = (
        "TEXT-EXTRACTED SoA JSON:\n" + json.dumps(text_soa, ensure_ascii=False, indent=2) +
        "\nVISION-EXTRACTED SoA JSON:\n" + json.dumps(vision_soa, ensure_ascii=False, indent=2)
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": LLM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        max_tokens=4096
    )
    result = response.choices[0].message.content
    # Clean up: remove code block markers, trailing text
    result = result.strip()
    if result.startswith('```json'):
        result = result[7:]
    if result.startswith('```'):
        result = result[3:]
    if result.endswith('```'):
        result = result[:-3]
    last_brace = result.rfind('}')
    if last_brace != -1:
        result = result[:last_brace+1]
    parsed = json.loads(result)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] LLM-reconciled SoA written to {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM-based reconciliation of SoA JSONs.")
    parser.add_argument("--text", default="soa_text.json", help="Path to text-extracted SoA JSON")
    parser.add_argument("--vision", default="soa_vision.json", help="Path to vision-extracted SoA JSON")
    parser.add_argument("--output", default="soa_final.json", help="Path to write reconciled SoA JSON")
    args = parser.parse_args()
    reconcile_soa(args.text, args.vision, args.output)
