import subprocess
import sys
import os
import json

def run_script(script, args=None):
    """Run a script and return (success, output)"""
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[SUCCESS] {script} output:\n{result.stdout}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {script} failed:\n{e.stderr}")
        return False, e.stderr

def validate_json(json_path):
    """Validate a JSON file against the USDM OpenAPI schema."""
    success, _ = run_script("validate_usdm.py", [json_path])
    return success

def main():
    # Set protocol PDF path here for all steps
    PDF_PATH = "c:/Users/panik/Documents/GitHub/Protcol2USDMv3/CDISC_Pilot_Study.pdf"
    SOA_IMAGES_DIR = "./soa_images"

    # 1. Extract SoA from text (PDF)
    print("\n[STEP 1] Extracting SoA from PDF text...")
    success, _ = run_script("send_pdf_to_openai.py")
    if not success:
        print("[FATAL] Text extraction failed. Aborting.")
        return

    # 2. Validate soa_text.json
    print("\n[STEP 2] Validating soa_text.json...")
    if not validate_json("soa_text.json"):
        print("[FATAL] soa_text.json is invalid. Aborting.")
        return

    # 3. Find SOA pages
    print("\n[STEP 3] Identifying SOA pages in PDF...")
    result = subprocess.run([sys.executable, "find_soa_pages.py", PDF_PATH], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] SOA page identification failed:", result.stderr)
        return
    # The last line with comma-separated page numbers is the output
    page_line = result.stdout.strip().split("\n")[-1]
    if not page_line or not any(x.isdigit() for x in page_line.split(",")):
        print("[FATAL] No SOA pages found.")
        return
    soa_pages = [int(x) for x in page_line.split(",") if x.strip().isdigit()]
    print(f"[INFO] SOA pages: {soa_pages}")

    # 4. Extract those pages as images
    print("\n[STEP 4] Extracting SOA pages as images...")
    page_str = ",".join(str(p) for p in soa_pages)
    result = subprocess.run([sys.executable, "extract_pdf_pages_as_images.py", PDF_PATH, page_str, SOA_IMAGES_DIR], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] Image extraction failed:", result.stderr)
        return
    image_paths = [x for x in result.stdout.strip().split(",") if x]
    print(f"[INFO] Extracted images: {image_paths}")

    # 5. Extract SoA from images (vision)
    print("\n[STEP 5] Extracting SoA from protocol images...")
    # Write image paths to a file or set as input in vision_extract_soa.py as needed
    # For now, assume vision_extract_soa.py reads from SOA_IMAGES_DIR
    success, _ = run_script("vision_extract_soa.py")
    if not success:
        print("[FATAL] Vision extraction failed. Aborting.")
        return

    # 6. Validate soa_vision.json
    print("\n[STEP 6] Validating soa_vision.json...")
    if not validate_json("soa_vision.json"):
        print("[FATAL] soa_vision.json is invalid. Aborting.")
        return

    # 7. LLM-based reconciliation
    print("\n[STEP 7] LLM-based reconciliation of text and vision outputs...")
    result = subprocess.run([sys.executable, "reconcile_soa_llm.py", "--text", "soa_text.json", "--vision", "soa_vision.json", "--output", "soa_final.json"], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] LLM reconciliation failed:", result.stderr)
        return
    print(result.stdout)

    # 8. Validate against CORE rule set (stub)
    print("\n[STEP 8] Validating soa_final.json against USDM v4 CORE rules (stub)...")
    # TODO: Implement actual CORE rule validation logic or call
    # For now, just check if file exists and is valid JSON
    try:
        with open("soa_final.json", "r", encoding="utf-8") as f:
            soa_final = json.load(f)
        print("[SUCCESS] soa_final.json is valid JSON. (CORE rules validation stub)")
    except Exception as e:
        print(f"[FATAL] soa_final.json failed validation: {e}")
        return

    # 9. Render round-trip SoA for review
    print("\n[STEP 9] Rendering SoA for review...")
    result = subprocess.run([sys.executable, "render_soa_html.py", "--soa", "soa_final.json", "--output", "soa_final.html"], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] SoA rendering failed:", result.stderr)
        return
    print(result.stdout)
    print("[INFO] Final SoA rendered to soa_final.html. Open this file in your browser for review.")

    print("\n[ALL STEPS COMPLETE]")

if __name__ == "__main__":
    main()
