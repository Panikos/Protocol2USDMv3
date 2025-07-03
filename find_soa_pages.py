import os
import sys
import base64
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import fitz  # PyMuPDF
import textwrap
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIG ---
KEYWORDS = [
    "schedule of activities",
    "soa",
    "assessment schedule",
    "visit schedule",
    "study calendar",
    "assessment table",
    "timing of procedures",
    "time and events",
    "table of assessments",
    "Schedule of Events"
]
KEYWORDS = [k.lower() for k in KEYWORDS]

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- FUNCTIONS ---
def extract_page_texts(pdf_path):
    doc = fitz.open(pdf_path)
    return [page.get_text() for page in doc]

def keyword_filter(page_texts):
    candidates = []
    for i, text in enumerate(page_texts):
        text_lc = text.lower()
        if any(kw in text_lc for kw in KEYWORDS):
            candidates.append(i)
    return candidates

import time

def llm_is_soa_page(page_text, client, model, prompt_content):
    """Asks the LLM if a page contains SoA content, using the main prompt for context."""
    unique_run_id = f"RunID:{time.time()}"
    
    if prompt_content:
        system_prompt = textwrap.dedent(f"""
            You are an expert assistant specializing in clinical trial protocols. Your task is to determine if a given page from a protocol document is relevant to the Schedule of Activities (SoA).

            A page is considered **relevant** if it contains:
            1. The main SoA table itself (a grid of visits, timepoints, and procedures).
            2. **Crucial context for the SoA**, such as detailed descriptions, footnotes, or definitions for the items described in the schema below.

            Here is the schema context for the key SoA-related entities to look for:
            ---
            {prompt_content}
            ---

            Based on this, analyze the following page text.

            IMPORTANT:
            - A 'Table of Contents' page is NOT relevant, even if it lists the SoA.
            - Your response must be a single word: 'yes' or 'no'.
        """)
    else: # Fallback to the old prompt if no context is provided
        system_prompt = textwrap.dedent("""
            You are a text classification assistant. Your only task is to determine if the text from a clinical trial protocol page contains the 'Schedule of Activities' (SoA).
            The SoA can be a table, a title, or a header.
            IMPORTANT: A 'Table of Contents' page is NOT a Schedule of Activities, even if it lists the SoA as a section. If the page is a Table of Contents, respond 'no'.
            If the text contains 'Schedule of Activities', 'SoA', 'Schedule of Events', or a similar title, OR if it contains a table with visits, timepoints, and medical procedures, you must respond 'yes'.
            Otherwise, respond 'no'.
            Your response must be a single word: 'yes' or 'no'.
        """)

    user_content = f"Page Text:\n{textwrap.shorten(page_text, width=12000)}\n{unique_run_id}"
    
    params = dict(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ])

    if model != "o3":
        params["temperature"] = 0
    if model in ['o3', 'o3-mini', 'o3-mini-high']:
        params['max_completion_tokens'] = 5
    else:
        params['max_tokens'] = 5

    print(f"[DEBUG] Sending request to {model} for page adjudication...", file=sys.stderr)
    try:
        response = client.chat.completions.create(**params)
        print(f"[DEBUG] Received response from {model}.", file=sys.stderr)
        answer = response.choices[0].message.content.strip().lower()
        return answer.startswith('yes')
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}", file=sys.stderr)
        return False

def llm_is_soa_page_image(pdf_path, page_num, client, model):
    """Send image of a PDF page to OpenAI vision API and ask if it contains the SOA table."""
    import tempfile
    import fitz
    import time
    import uuid
    import shutil
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=200)
    # Ensure unique temp file name and that file is closed before pix.save
    for attempt in range(3):
        tmp_path = os.path.join(tempfile.gettempdir(), f"soa_page_{uuid.uuid4().hex}.png")
        try:
            with open(tmp_path, 'wb') as f:
                pass  # Just create and close the file
            pix.save(tmp_path)
            image_path = tmp_path
            break
        except Exception as e:
            print(f"[WARN] Failed to save pixmap to temp file (attempt {attempt+1}): {e}", file=sys.stderr)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            time.sleep(0.5)
    else:
        raise RuntimeError("[FATAL] Could not create/save temp PNG for LLM vision adjudication after 3 attempts.")
    with open(image_path, 'rb') as imgf:
        img_b64 = base64.b64encode(imgf.read()).decode('utf-8')
    image_url = f"data:image/png;base64,{img_b64}"
    unique_run_id = f"RunID:{time.time()}"
    system_prompt = (
        "You are an image classification assistant. Your only task is to determine if the image of a clinical trial protocol page contains the 'Schedule of Activities' (SoA).\n"
        "The SoA can be a table, a title, or a header.\n"
        "IMPORTANT: A 'Table of Contents' page is NOT a Schedule of Activities, even if it lists the SoA as a section. If the image shows a Table of Contents, respond 'no'.\n"
        "If the image contains the text 'Schedule of Activities', 'SoA', 'Schedule of Events', or a similar title, OR if it shows a table with visits, timepoints, and medical procedures, you must respond 'yes'.\n"
        "Otherwise, respond 'no'.\n"
        "Your response must be a single word: 'yes' or 'no'. "
        f"{unique_run_id}"
    )
    try:
        params = dict(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "low"},
                        },
                    ],
                }
            ],
        )
        # o3 does not support temperature=0, so we use the API's default.
        # For other models, set temperature to 0 for deterministic output.
        if model != "o3":
            params["temperature"] = 0
        if model in ['o3', 'o3-mini', 'o3-mini-high']:
            params['max_completion_tokens'] = 5
        else:
            params['max_tokens'] = 5
        response = client.chat.completions.create(**params)
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}", file=sys.stderr)
        # Fallback or re-raise
        raise
    answer = response.choices[0].message.content.strip().lower()
    import time
    # Robust temp file cleanup: retry up to 3 times if permission denied
    for attempt in range(3):
        try:
            os.remove(image_path)
            break
        except PermissionError as e:
            print(f"[WARN] Temp file removal failed (attempt {attempt+1}): {e}. Retrying...", file=sys.stderr)
            time.sleep(0.5)
    else:
        print(f"[ERROR] Could not remove temp file {image_path} after 3 attempts. Please check for locked files.", file=sys.stderr)
    return answer.startswith('yes')


def main():
    print("[DEBUG] find_soa_pages.py main() started", file=sys.stderr)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Find SOA pages in a PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--prompt-file", help="Path to the LLM prompt file for context")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to check with LLM if keyword filter fails")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use")
    args = parser.parse_args()

    # Ensure pdf_path is absolute
    pdf_path = args.pdf_path
    if not os.path.exists(pdf_path):
        print(f"[FATAL] PDF file not found at: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    MODEL_NAME = args.model
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}", file=sys.stderr)

    prompt_content = ""
    if args.prompt_file and os.path.exists(args.prompt_file):
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        print(f"[INFO] Loaded prompt context from {args.prompt_file}", file=sys.stderr)
    else:
        print("[WARNING] No prompt file provided or found. Using basic SoA detection.", file=sys.stderr)

    page_texts = extract_page_texts(pdf_path)
    # Log page text stats for automation/debugging
    empty_or_short = 0
    for i, text in enumerate(page_texts):
        if len(text.strip()) < 30:
            empty_or_short += 1
    if empty_or_short == len(page_texts):
        print("[WARNING] All pages are empty or too short. Consider OCR fallback for this PDF.", file=sys.stderr)

    candidates = keyword_filter(page_texts)
    print(f"[INFO] Keyword candidate pages: {[p + 1 for p in candidates]}", file=sys.stderr)
    soa_pages = []
    def log_llm(page_idx, answer, mode):
        print(f"[LLM][{mode}] Page {page_idx+1} response: {answer}", file=sys.stderr)

    adjudicated = set()
    # 1. Adjudicate keyword candidate pages
    if candidates:
        print(f"[INFO] Running LLM adjudication on keyword candidate pages...", file=sys.stderr)
        for i in candidates:
            if i in adjudicated:
                continue
            answer = llm_is_soa_page(page_texts[i], client, MODEL_NAME, prompt_content)
            log_llm(i, answer, "text")
            adjudicated.add(i)
            if answer:
                # Found the start of an SoA block.
                if i not in soa_pages:
                    soa_pages.append(i)
                
                # Keep checking subsequent pages until a "no" to find the whole block.
                next_idx = i + 1
                while next_idx < len(page_texts):
                    if next_idx in adjudicated:
                        next_idx += 1
                        continue
                    answer_next = llm_is_soa_page(page_texts[next_idx], client, MODEL_NAME, prompt_content)
                    log_llm(next_idx, answer_next, "text (contiguous)")
                    adjudicated.add(next_idx)
                    if answer_next:
                        if next_idx not in soa_pages:
                            soa_pages.append(next_idx)
                        next_idx += 1
                    else:
                        # Found the end of a contiguous block.
                        break
                
                # A contiguous block has ended. The main loop will continue to check other candidates.
                pass

    # 2. If no SOA found from text, use vision on first N pages
    if not soa_pages:
        print(f"[INFO] No SoA pages found from text. Adjudicating first {args.max_pages} pages using vision model...", file=sys.stderr)
        found_soa_vision = False
        for i in range(min(args.max_pages, len(page_texts))):
            if i in adjudicated:
                continue
            print(f"[INFO] LLM adjudicating page {i+1} (vision)...", file=sys.stderr)
            answer = llm_is_soa_page_image(pdf_path, i, client, MODEL_NAME)
            log_llm(i, answer, "vision")
            adjudicated.add(i)
            if answer:
                if i not in soa_pages:
                    soa_pages.append(i)
                found_soa_vision = True
            elif found_soa_vision:
                # We found the end of the contiguous SoA block
                print(f"[INFO] First non-SOA page after finding SOA block (vision): page {i+1}. Stopping adjudication.", file=sys.stderr)
                break

    soa_pages = sorted(list(set(soa_pages)))

    if soa_pages:
        print(f"[RESULT] SOA pages: {[p + 1 for p in soa_pages]}", file=sys.stderr)
    else:
        print("[RESULT] No SOA pages found.", file=sys.stderr)
    
    # Final output to stdout for the pipeline
    print(",".join(str(p) for p in soa_pages))

if __name__ == "__main__":
    main()