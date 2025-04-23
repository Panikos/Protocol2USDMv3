import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def encode_image_to_base64(image_path):
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def extract_soa_from_images(image_paths):
    usdm_prompt = (
        "You are an expert at extracting structured data from clinical trial protocol images. "
        "Extract the Schedule of Activities (SoA) from these protocol images and return it as a JSON object graph conforming to the USDM v4.0 model. "
        "The structure must be:\n"
        "{\n"
        "  'name': '<study name>',\n"
        "  'instanceType': 'Study',\n"
        "  'studyVersions': [\n"
        "    {\n"
        "      'studyVersionId': 'SV1',\n"
        "      'studyDesign': {\n"
        "        'timeline': {\n"
        "          'plannedTimepoints': [...],\n"
        "          'activities': [...],\n"
        "          'activityGroups': [...],\n"
        "          'activityTimepoints': [...]\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Use unique IDs for cross-referencing. Only include PlannedVisit objects if both visits and weeks are shown. Output must be valid JSON conforming to the USDM v4 OpenAPI schema. "
        "The top-level object must include both 'name' and 'instanceType' fields as shown. Use the study name from the protocol for 'name'. Output ONLY valid JSON, with no explanations, comments, or markdown."
    )
    messages = [
        {"role": "system", "content": usdm_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "The following are images of the Schedule of Activities table from a clinical trial protocol. If the table spans both images, merge them into one SoA."}
        ]}
    ]
    for image_path in image_paths:
        img_b64 = encode_image_to_base64(image_path)
        messages[1]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        })
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=4096
    )
    content = response.choices[0].message.content
    if len(content) > 3800:
        print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
    return content


if __name__ == "__main__":
    image_paths = [
        './soa_images/soa_page_53.png',
        './soa_images/soa_page_54.png'
    ]
    import json
    def clean_llm_json(raw):
        raw = raw.strip()
        # Remove code block markers
        if raw.startswith('```json'):
            raw = raw[7:]
        if raw.startswith('```'):
            raw = raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]
        # Remove anything after the last closing brace
        last_brace = raw.rfind('}')
        if last_brace != -1:
            raw = raw[:last_brace+1]
        return raw

    soa_vision = extract_soa_from_images(image_paths)
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        parsed_json = json.loads(soa_vision)
    except json.JSONDecodeError:
        cleaned = clean_llm_json(soa_vision)
        parsed_json = json.loads(cleaned)
    print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
    with open("soa_vision.json", "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2, ensure_ascii=False)
