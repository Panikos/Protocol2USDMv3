import os
import sys
import argparse
import io
import json
import re  # Regular expressions for text parsing
import fitz  # PyMuPDF for PDF text extraction
from p2u_constants import USDM_VERSION

# Ensure all output is UTF-8 safe for Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
import sys
import io
import argparse

# Ensure Windows console can print UTF-8
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Optional provider abstraction
try:
    from llm_providers import LLMProviderFactory
    PROVIDER_LAYER_AVAILABLE = True
except ImportError:
    print("[WARNING] Provider layer not available, using legacy direct API calls")
    PROVIDER_LAYER_AVAILABLE = False

# Prompt template system
try:
    from prompt_templates import PromptTemplate
    TEMPLATES_AVAILABLE = True
except ImportError:
    print("[WARNING] PromptTemplate not available, will use file-based prompts")
    TEMPLATES_AVAILABLE = False

# Load text extraction template
def load_text_extraction_template():
    """Load text extraction prompt from YAML template (v2.0) or return None for file-based fallback."""
    if TEMPLATES_AVAILABLE:
        try:
            template = PromptTemplate.load("soa_extraction", "prompts")
            print(f"[INFO] Loaded text extraction template v{template.metadata.version}")
            return template
        except Exception as e:
            print(f"[WARNING] Could not load YAML template: {e}. Using file-based prompts.")
    return None

TEXT_EXTRACTION_TEMPLATE = load_text_extraction_template()

# Fallback system message (v1.0 - deprecated but kept for backward compatibility)
FALLBACK_SYSTEM_MESSAGE = (
    "You are an expert medical writer specializing in clinical trial protocols. "
    "When extracting text, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. "
    "Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. "
    "Do NOT output any markdown, explanation, or additional text."
)

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# LEGACY: Keep old clients for backward compatibility during transition
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
except:
    openai_client = None

try:
    import google.generativeai as genai
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if google_api_key:
        genai.configure(api_key=google_api_key)
except:
    google_api_key = None

def extract_pdf_text(pdf_path, page_numbers=None):
    doc = fitz.open(pdf_path)
    text = ""
    # If page_numbers are specified, extract text only from those pages
    if page_numbers:
        for page_num in page_numbers:
            if 0 <= page_num < len(doc):
                text += doc[page_num].get_text()
    else:
        # Otherwise, extract text from all pages
        for page in doc:
            text += page.get_text()
    return text

def split_into_sections(text):
    # Try to split by section headers (e.g., numbered, all-caps, or 'Schedule of Activities')
    # Fallback: split by double newlines
    section_pattern = re.compile(r"(^\s*\d+\.\s+.+$|^[A-Z][A-Z\s\-]{6,}$|^Schedule of Activities.*$)", re.MULTILINE)
    matches = list(section_pattern.finditer(text))
    if not matches:
        # fallback: split by paragraphs
        return [s.strip() for s in text.split('\n\n') if s.strip()]
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return sections

def chunk_sections(sections, max_chars=75000):
    chunks = []
    current = []
    current_len = 0
    for sec in sections:
        if current_len + len(sec) > max_chars and current:
            chunks.append('\n\n'.join(current))
            current = [sec]
            current_len = len(sec)
        else:
            current.append(sec)
            current_len += len(sec)
    if current:
        chunks.append('\n\n'.join(current))
    return chunks

def send_text_to_llm(text, usdm_prompt, model_name, use_provider_layer=True):
    """
    Send text to LLM for processing.
    
    Args:
        text: Protocol text to analyze
        usdm_prompt: USDM extraction prompt
        model_name: Model identifier (e.g., 'gpt-4o', 'gemini-2.5-pro')
        use_provider_layer: If True, use new provider abstraction (default: True)
    
    Returns:
        Raw LLM output text
    """
    print(f"[DEBUG] Length of extracted PDF text: {len(text)}")
    print(f"[DEBUG] Length of prompt: {len(usdm_prompt)}")
    print(f"[DEBUG] Total prompt+text length: {len(usdm_prompt) + len(text)}")
    
    # Use template system (v2.0) or fallback to hardcoded message (v1.0)
    if TEXT_EXTRACTION_TEMPLATE:
        # v2.0: The YAML template expects the full prompt content to be in variables
        # Since we already have the assembled prompt from the file, we treat it as protocol_text
        messages = [
            {"role": "system", "content": TEXT_EXTRACTION_TEMPLATE.system_prompt},
            {"role": "user", "content": f"{usdm_prompt}\n\nHere is the protocol text to analyze:\n\n---\n\n{text}"}
        ]
    else:
        # v1.0: Use fallback hardcoded message
        messages = [
            {"role": "system", "content": FALLBACK_SYSTEM_MESSAGE},
            {"role": "user", "content": f"{usdm_prompt}\n\nHere is the protocol text to analyze:\n\n---\n\n{text}"}
        ]
    
    # NEW: Use provider abstraction layer
    if use_provider_layer:
        try:
            print(f"[INFO] Using provider layer for model: {model_name}")
            
            # Auto-detect and create provider
            provider = LLMProviderFactory.auto_detect(model_name)
            
            # Configure for JSON output
            config = LLMConfig(
                temperature=0.0,
                json_mode=True,
                max_tokens=None  # Use model defaults
            )
            
            # Generate response
            response = provider.generate(messages, config)
            
            # print(f"[DEBUG] Raw LLM output:\n{response.content}")  # Commented out - too verbose
            print(f"[ACTUAL_MODEL_USED] {model_name}")
            if response.usage:
                print(f"[USAGE] Tokens: {response.usage}")
            
            return response.content
        
        except Exception as e:
            print(f"[WARNING] Provider layer failed: {e}. Falling back to legacy code.")
            use_provider_layer = False
    
    # LEGACY: Original implementation (kept for backward compatibility)
    if not use_provider_layer:
        try:
            if 'gemini' in model_name.lower():
                print(f"[INFO] Using Google Gemini model (legacy): {model_name}")
                if not google_api_key:
                    raise ValueError("GOOGLE_API_KEY environment variable not set.")
                model = genai.GenerativeModel(model_name)
                full_prompt = f"{messages[0]['content']}\n\n{messages[1]['content']}"
                response = model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                result = response.text
            else:
                print(f"[INFO] Using OpenAI model (legacy): {model_name}")
                params = {
                    "model": model_name,
                    "messages": messages,
                    "response_format": {"type": "json_object"}
                }
                if model_name not in ['o3', 'o3-mini', 'o3-mini-high']:
                    params["temperature"] = 0.0
                
                response = openai_client.chat.completions.create(**params)
                result = response.choices[0].message.content

            # print(f"[DEBUG] Raw LLM output:\n{result}")  # Commented out - too verbose
            print(f"[ACTUAL_MODEL_USED] {model_name}")
            return result
        except Exception as e:
            print(f"[FATAL] Model '{model_name}' failed: {e}")
            raise RuntimeError(f"Model '{model_name}' failed: {e}")

def clean_llm_json(raw):
    # Remove markdown code block fences
    cleaned = re.sub(r"^```json\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)
    # Remove leading/trailing whitespace that might affect parsing
    cleaned = cleaned.strip()
    # Attempt to fix trailing commas in objects and arrays
    cleaned = re.sub(r",(\s*[]}])", r"\1", cleaned)
    return cleaned

def extract_json_str(s: str) -> str:
    """
    Defensive JSON extractor with three-layer parsing strategy:
    1. Fast path: Try direct parse
    2. Strip code fences, fix trailing commas, remove prose
    3. Extract first {...} block and fix trailing commas
    
    Raises ValueError if no valid JSON object found.
    
    Args:
        s: Raw string from LLM that should contain JSON
    
    Returns:
        Clean JSON string ready for json.loads()
    """
    import json
    
    # Layer 1: Fast path - try direct parse
    try:
        json.loads(s)
        return s
    except Exception:
        pass
    
    # Layer 2: Remove code fences and markdown
    s2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", s.strip(), flags=re.MULTILINE)
    
    # Fix trailing commas before attempting parse
    s2 = re.sub(r",\s*([}\]])", r"\1", s2)
    
    try:
        json.loads(s2)
        return s2
    except Exception:
        pass
    
    # Layer 2b: Remove leading prose like "Here is the JSON:"
    # Only do this if there's text before a brace
    if '{' in s2:
        start_idx = s2.find('{')
        if start_idx > 0:
            s2 = s2[start_idx:]
            # Fix trailing commas again after extraction
            s2 = re.sub(r",\s*([}\]])", r"\1", s2)
            try:
                json.loads(s2)
                return s2
            except Exception:
                pass
    
    # Layer 3: Extract first {...} block (greedy match)
    m = re.search(r"\{.*\}", s2, flags=re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object found in LLM output (length: {len(s)})")
    
    candidate = m.group(0)
    
    # Fix trailing commas one more time
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    
    # Validate before returning
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError as e:
        raise ValueError(f"Extracted JSON block is invalid: {e}")

def call_with_retry(call_fn, text_chunk, prompt, model_name, max_attempts=2):
    """
    Execute LLM call with automatic retry on parse failure.
    Each retry tightens the prompt with stricter JSON-only reminders.
    
    Args:
        call_fn: Function to call (send_text_to_llm)
        text_chunk: Text to process
        prompt: Base prompt
        model_name: LLM model name
        max_attempts: Maximum retry attempts (default 2)
    
    Returns:
        Clean JSON string ready for parsing
    
    Raises:
        Last exception if all attempts fail
    """
    last_err = None
    local_prompt = prompt
    
    for attempt in range(max_attempts):
        if attempt > 0:
            print(f"[RETRY] Attempt {attempt + 1}/{max_attempts} with stricter prompt")
        
        try:
            raw_output = call_fn(text_chunk, local_prompt, model_name)
            
            # Try to extract clean JSON
            clean_json = extract_json_str(raw_output)
            
            if attempt > 0:
                print(f"[SUCCESS] Retry attempt {attempt + 1} succeeded")
            
            return clean_json
            
        except Exception as e:
            last_err = e
            print(f"[WARNING] Attempt {attempt + 1} failed: {e}")
            
            # Tighten the prompt for next retry
            if attempt < max_attempts - 1:
                local_prompt = local_prompt + (
                    "\n\n"
                    "═══════════════════════════════════════════════════════════════════════\n"
                    " STRICT REMINDER (RETRY)\n"
                    "═══════════════════════════════════════════════════════════════════════\n"
                    "The previous response could not be parsed. Please fix the following:\n"
                    "- Return ONE JSON object ONLY\n"
                    "- NO prose, explanations, or markdown\n"
                    "- NO code fences (```)\n"
                    "- Output must be directly loadable by json.loads()\n"
                    "- Ensure all commas, braces, and brackets are balanced\n"
                )
    
    # All attempts exhausted
    raise last_err

def merge_soa_jsons(soa_parts):
    """
    Merges multiple SoA JSON parts from chunked LLM calls into a single,
    valid USDM JSON object based on the v4.0.0 timeline structure.
    Handles re-indexing of all entity IDs to prevent collisions.
    """
    if not soa_parts:
        return None

    # Entity types as they appear in the LLM's timeline output
    ENTITY_TYPES = [
        'epochs',
        'encounters',
        'plannedTimepoints',
        'activities',
        'activityTimepoints',
        'activityGroups'
    ]

    # --- PASS 1: Collect all unique entities and create ID mappings ---
    id_maps = {entity_type: {} for entity_type in ENTITY_TYPES}
    all_entities = {entity_type: [] for entity_type in ENTITY_TYPES}
    id_counters = {entity_type: 1 for entity_type in ENTITY_TYPES}

    for part in soa_parts:
        # Check for the expected nested structure
        if not (
            'study' in part and
            'versions' in part['study'] and
            isinstance(part['study']['versions'], list) and
            len(part['study']['versions']) > 0 and
            'timeline' in part['study']['versions'][0]
        ):
            continue
        
        timeline = part['study']['versions'][0]['timeline']
        for entity_type in ENTITY_TYPES:
            if entity_type in timeline and isinstance(timeline[entity_type], list):
                for entity in timeline[entity_type]:
                    if not isinstance(entity, dict):
                        continue
                    old_id = entity.get('id')
                    if old_id is None:
                        continue

                    # Add entity if its ID hasn't been seen before
                    def _alt(id_str: str) -> str | None:
                        m = re.match(r"(encounter|enc)[-_](\d+)", id_str)
                        if m:
                            full = f"encounter-{m.group(2)}"
                            short = f"enc_{m.group(2)}"
                            return short if id_str == full else full
                        m2 = re.match(r"epoch[-_](\d+)", id_str)
                        if m2:
                            return f"epoch_{m2.group(1)}" if '-' in id_str else f"epoch-{m2.group(1)}"
                        return None
                    # Ensure both the original ID and a possible alias (e.g. enc_1 ↔ encounter-1) map to the same canonical new ID
                    existing_map = id_maps[entity_type]
                    if old_id not in existing_map:
                        # Generate canonical new ID (singular entity prefix)
                        new_prefix = entity_type.replace('ies', 'y').rstrip('s')  # epochs → epoch, activities → activit…
                        new_id = f"{new_prefix}-{id_counters[entity_type]}"
                        id_counters[entity_type] += 1
                        existing_map[old_id] = new_id

                        alt = _alt(old_id)
                        if alt:
                            existing_map[alt] = new_id

                        all_entities[entity_type].append(entity)
                    else:
                        # We already assigned a new ID for this entity elsewhere – still register alias if needed
                        alt = _alt(old_id)
                        if alt and alt not in existing_map:
                            existing_map[alt] = existing_map[old_id]

    # --- PASS 2: Rewrite IDs and foreign keys in collected entities ---
    final_timeline = {entity_type: [] for entity_type in ENTITY_TYPES}

    for entity_type, entities in all_entities.items():
        for entity in entities:
            # Update the primary ID of the entity itself
            old_id = entity.get('id')
            if old_id in id_maps[entity_type]:
                entity['id'] = id_maps[entity_type][old_id]

            # Update foreign key references within the entity based on new schema
                        # Encounter -> Epoch and PlannedTimepoint
            if entity_type == 'encounters':
                # epochId reference
                fk_epoch = 'epochId'
                if fk_epoch in entity and entity.get(fk_epoch) in id_maps.get('epochs', {}):
                    entity[fk_epoch] = id_maps['epochs'][entity[fk_epoch]]
                # scheduledAtId (legacy naming)
                fk_sched = 'scheduledAtId'
                if fk_sched in entity and entity.get(fk_sched) in id_maps.get('plannedTimepoints', {}):
                    entity[fk_sched] = id_maps['plannedTimepoints'][entity[fk_sched]]
            
                        # PlannedTimepoint -> Encounter
            if entity_type == 'plannedTimepoints':
                fk_enc = 'encounterId'
                if fk_enc in entity and entity.get(fk_enc) in id_maps.get('encounters', {}):
                    entity[fk_enc] = id_maps['encounters'][entity[fk_enc]]

            # ActivityTimepoint -> Activity and PlannedTimepoint
            if entity_type == 'activityTimepoints':
                fk_activity = 'activityId'
                if fk_activity in entity and entity.get(fk_activity) in id_maps.get('activities', {}):
                    entity[fk_activity] = id_maps['activities'][entity[fk_activity]]
                
                fk_timepoint = 'plannedTimepointId'
                if fk_timepoint in entity and entity.get(fk_timepoint) in id_maps.get('plannedTimepoints', {}):
                    entity[fk_timepoint] = id_maps['plannedTimepoints'][entity[fk_timepoint]]

            # ActivityGroup -> Activity
            if entity_type == 'activityGroups':
                if 'activities' in entity and isinstance(entity.get('activities'), list):
                    entity['activities'] = [id_maps.get('activities', {}).get(aid, aid) for aid in entity['activities']]

            final_timeline[entity_type].append(entity)

    # Construct the final merged JSON in the new timeline format
    final_json = {
        "study": {
            "versions": [
                {
                    "timeline": {key: val for key, val in final_timeline.items() if val}
                }
            ]
        },
        "usdmVersion": USDM_VERSION # Carry over version
    }

    return final_json

def get_llm_prompt(prompt_file, header_structure_file):
    # Base prompt is always loaded
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    except FileNotFoundError:
        print(f"[FATAL] Prompt file not found: {prompt_file}")
        raise

    # Dynamically add header and activity group structure info
    try:
        with open(header_structure_file, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)
        
        # Create machine-readable header hints
        hints = {
            "timepoints": [
                {
                    "id": tp.get("id"),
                    "labelPrimary": tp.get("primary_name"),
                    "labelSecondary": tp.get("secondary_name")
                } for tp in structure_data.get("timepoints", [])
            ],
            "activityGroups": [
                {
                    "id": ag.get("id"),
                    "name": ag.get("group_name"),
                    "activities": ag.get("activities", [])
                } for ag in structure_data.get("activity_groups", [])
            ]
        }
        header_prompt_part = (
            "\n\nThe following JSON object (headerHints) describes the detected table structure. "
            "Use the information strictly to assign correct IDs and groupings. "
            "You may copy values but do NOT invent new IDs.\n" +
            "```json\n" + json.dumps({"headerHints": hints}, indent=2) + "\n```\n"
        )
        return base_prompt + header_prompt_part

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"[FATAL] Could not read or parse header structure file {header_structure_file}: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Extract SoA from a PDF using text-based LLM.")
    parser.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
    parser.add_argument("--output", required=True, help="Path to write the output JSON file.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use (e.g., 'gpt-4-turbo', 'gpt-4o').")
    parser.add_argument("--prompt-file", required=True, help="Path to the LLM prompt file.")
    parser.add_argument("--header-structure-file", required=True, help="Path to the header structure JSON file.")
    parser.add_argument("--soa-pages-file", required=False, help="Optional path to a JSON file containing a list of 0-based SoA page numbers. If not provided, the entire PDF will be processed.")
    args = parser.parse_args()

    MODEL_NAME = args.model
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = MODEL_NAME
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

    # Build the dynamic prompt
    usdm_prompt = get_llm_prompt(args.prompt_file, args.header_structure_file)

    page_numbers = None
    if args.soa_pages_file:
        try:
            with open(args.soa_pages_file, 'r') as f:
                data = json.load(f)
            page_numbers = data['soa_pages'] # These are 0-indexed
            print(f"[INFO] Extracting text from {len(page_numbers)} pages specified in {args.soa_pages_file}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"[FATAL] Could not read page numbers from {args.soa_pages_file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[INFO] No SoA pages file provided. Extracting text from the entire PDF.")

    pdf_text = extract_pdf_text(args.pdf_path, page_numbers=page_numbers)
    if not pdf_text:
        print("[FATAL] No text could be extracted from the specified pages.", file=sys.stderr)
        sys.exit(1)
        
    sections = split_into_sections(pdf_text)
    chunks = chunk_sections(sections)
    print(f"[INFO] Split text into {len(chunks)} chunks to send to LLM.")

    all_soa_parts = []
    chunk_retry_count = 0
    
    for i, chunk in enumerate(chunks):
        print(f"[INFO] Sending chunk {i+1}/{len(chunks)} to LLM...")
        
        try:
            # Use defensive parser with retry
            clean_json_str = call_with_retry(
                send_text_to_llm, 
                chunk, 
                usdm_prompt, 
                args.model, 
                max_attempts=2
            )
            
            # Parse the clean JSON
            parsed_json = json.loads(clean_json_str)
            
            # Validate structure - handle both direct and Wrapper-Input formats
            study = parsed_json.get('study')
            if not study:
                # Check for Wrapper-Input format
                wrapper = parsed_json.get('Wrapper-Input', {})
                study = wrapper.get('study', {})
                if study:
                    # Normalize to direct format for merge function
                    parsed_json = {
                        'study': study,
                        'usdmVersion': wrapper.get('usdmVersion', '4.0'),
                        'systemName': wrapper.get('systemName'),
                        'systemVersion': wrapper.get('systemVersion')
                    }
            
            if not study or ('versions' not in study and 'studyVersions' not in study):
                print(f"[WARNING] Chunk {i+1} parsed but lacks SoA data (study.versions). Skipping.")
                print(f"[DEBUG] Available keys at root: {list(parsed_json.keys())}")
                continue
            
            all_soa_parts.append(parsed_json)
            print(f"[SUCCESS] Chunk {i+1}/{len(chunks)} processed successfully")
            
        except ValueError as e:
            # extract_json_str failed to find JSON
            print(f"[WARNING] Chunk {i+1} extraction failed: {e}")
            chunk_retry_count += 1
            continue
            
        except json.JSONDecodeError as e:
            # Even cleaned JSON couldn't parse
            print(f"[WARNING] Chunk {i+1} JSON decode failed: {e}")
            chunk_retry_count += 1
            continue
            
        except Exception as e:
            # Other errors (LLM API failures, etc.)
            print(f"[ERROR] Chunk {i+1} processing failed: {e}")
            chunk_retry_count += 1
            continue
    
    # Report statistics
    total_chunks = len(chunks)
    success_chunks = len(all_soa_parts)
    failed_chunks = chunk_retry_count
    success_rate = (success_chunks / total_chunks * 100) if total_chunks > 0 else 0
    
    print(f"\n[STATISTICS] Chunk Processing Results:")
    print(f"  Total chunks: {total_chunks}")
    print(f"  Successful: {success_chunks} ({success_rate:.1f}%)")
    print(f"  Failed: {failed_chunks}")
    print(f"  Retries triggered: {chunk_retry_count}")

    if not all_soa_parts:
        print("[FATAL] No valid SoA JSON could be extracted from any text chunk.")
        sys.exit(1)

    print(f"[INFO] Successfully extracted SoA data from {len(all_soa_parts)} chunks. Merging...")
    final_json = merge_soa_jsons(all_soa_parts)

    # Provenance tagging (text source)
    def _tag(container_key, items):
        cm = final_json.setdefault('p2uProvenance', {}).setdefault(container_key, {})
        for obj in items:
            if isinstance(obj, dict) and obj.get('id'):
                cm[obj['id']] = 'text'
    
    # Get study object - handle both direct and Wrapper-Input formats
    study = final_json.get('study')
    if not study:
        wrapper = final_json.get('Wrapper-Input', {})
        study = wrapper.get('study', {})
    
    tl = study.get('versions', [{}])[0].get('timeline', {}) if isinstance(final_json, dict) else {}
    _tag('plannedTimepoints', tl.get('plannedTimepoints', []))
    _tag('activities', tl.get('activities', []))
    _tag('encounters', tl.get('encounters', []))

    if not final_json:
        print("[FATAL] Merging of SoA chunks failed.")
        sys.exit(1)

    # Ensure the final study object has the required keys for validation
    if 'study' in final_json and 'attributes' not in final_json['study']:
        final_json['study']['attributes'] = {}
    if 'study' in final_json and 'relationships' not in final_json['study']:
        final_json['study']['relationships'] = {}

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[FATAL] Could not write output to {args.output}: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[SUCCESS] Merged SoA output from all LLM chunks written to {args.output}")

if __name__ == "__main__":
    main()
