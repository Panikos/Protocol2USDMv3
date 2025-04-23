import os
from openai import OpenAI
from dotenv import load_dotenv
import fitz  # PyMuPDF

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set your OpenAI API key using environment variable for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def send_text_to_openai(text):
    usdm_prompt = (
        "You are an expert at extracting structured data from clinical trial protocols. "
        "Extract the Schedule of Activities (SoA) from the following protocol text and return it as a JSON object graph conforming to the USDM v4.0 model. "
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
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": usdm_prompt},
            {"role": "user", "content": text}
        ],
        max_tokens=4096
    )
    content = response.choices[0].message.content
    if len(content) > 3800:
        print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
    return content

# Path to your PDF file
pdf_path = 'c:/Users/panik/Documents/GitHub/Protcol2USDMv3/CDISC_Pilot_Study.pdf'

# Extract text and send to GPT-4o
pdf_text = extract_pdf_text(pdf_path)
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

parsed_content = send_text_to_openai(pdf_text)
import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    parsed_json = json.loads(parsed_content)
except json.JSONDecodeError:
    cleaned = clean_llm_json(parsed_content)
    parsed_json = json.loads(cleaned)
print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

# Optionally, save to file
with open("soa_text.json", "w", encoding="utf-8") as f:
    json.dump(parsed_json, f, indent=2, ensure_ascii=False)
