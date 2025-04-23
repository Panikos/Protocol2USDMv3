import os
import sys
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

def llm_is_soa_page(page_text, client):
    prompt = (
        "You are an expert in clinical trial protocol parsing. "
        "Does the following page contain the Schedule of Activities (SoA) table for a clinical trial protocol? "
        "Reply only 'yes' or 'no'.\n\n"
        f"Page Text:\n{textwrap.shorten(page_text, width=3500)}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt}
        ],
        max_tokens=5
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer.startswith('yes')

def llm_is_soa_page_image(pdf_path, page_num, client):
    """Send image of a PDF page to OpenAI vision API and ask if it contains the SOA table."""
    import tempfile
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=200)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        pix.save(tmp.name)
        image_path = tmp.name
    prompt = (
        "You are an expert in clinical trial protocol parsing. "
        "Does this image contain the Schedule of Activities (SoA) table for a clinical trial protocol? "
        "Reply only 'yes' or 'no'."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"file://{image_path}"}}
            ]}
        ],
        max_tokens=5
    )
    answer = response.choices[0].message.content.strip().lower()
    os.remove(image_path)
    return answer.startswith('yes')

def main():
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Find SOA pages in a PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to check with LLM if keyword filter fails")
    args = parser.parse_args()

    page_texts = extract_page_texts(args.pdf_path)
    # Log page text stats for automation/debugging
    empty_or_short = 0
    for i, text in enumerate(page_texts):
        snippet = text[:100].replace('\n', ' ')
        print(f"[PAGE {i+1}] Length: {len(text)} | Preview: '{snippet}'")
        if len(text.strip()) < 30:
            empty_or_short += 1
    if empty_or_short == len(page_texts):
        print("[WARNING] All pages are empty or too short. Consider OCR fallback for this PDF.")

    candidates = keyword_filter(page_texts)
    print(f"[INFO] Keyword candidate pages: {candidates}")
    soa_pages = []
    def log_llm(page_idx, answer, mode):
        print(f"[LLM][{mode}] Page {page_idx+1} response: {answer}")

    if candidates:
        print("[INFO] Using TEXT+KEYWORD+LLM adjudication.")
        # Optionally, also check the following page for each candidate
        next_pages = set()
        for i in candidates:
            next_pages.add(i)
            if i+1 < len(page_texts):
                next_pages.add(i+1)
        for i in sorted(next_pages):
            print(f"[INFO] LLM adjudicating page {i+1} (text)...")
            answer = llm_is_soa_page(page_texts[i], client)
            log_llm(i, answer, "text")
            if answer:
                soa_pages.append(i)
    else:
        print(f"[WARNING] No keyword candidates found. Falling back to VISION LLM adjudication for first {args.max_pages} pages.")
        for i in range(min(args.max_pages, len(page_texts))):
            print(f"[INFO] LLM adjudicating page {i+1} (vision)...")
            answer = llm_is_soa_page_image(args.pdf_path, i, client)
            log_llm(i, answer, "vision")
            if answer:
                soa_pages.append(i)
    print(f"[RESULT] SOA pages: {soa_pages}")
    print(",".join(str(p) for p in soa_pages))

if __name__ == "__main__":
    main()
