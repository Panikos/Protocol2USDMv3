import os
import sys
import fitz  # PyMuPDF
import argparse
import json

def extract_pages_as_images(pdf_path, page_numbers, output_dir="."):
    """
    Extracts specific 0-indexed pages from a PDF as images.

    Args:
        pdf_path (str): The path to the PDF file.
        page_numbers (list[int]): A list of 0-based page numbers to extract.
        output_dir (str): The directory to save the output images.

    Returns:
        list[str]: A list of paths to the created image files.
    """
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF file not found at: {pdf_path}", file=sys.stderr)
        return []
        
    image_paths = []
    try:
        doc = fitz.open(pdf_path)
        os.makedirs(output_dir, exist_ok=True)

        for page_index in page_numbers:
            # PyMuPDF uses 0-based indexing
            if 0 <= page_index < len(doc):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(dpi=300)
                # Use 1-based page number for human-readable filename
                image_path = os.path.join(output_dir, f'soa_page_{page_index + 1}.png')
                pix.save(image_path)
                image_paths.append(image_path)
                print(f"Extracted page {page_index + 1} to {image_path}")
            else:
                print(f"[WARN] Page number {page_index + 1} is out of range (1-{len(doc)}).", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Failed to extract pages from {pdf_path}: {e}", file=sys.stderr)
        return []
        
    return image_paths

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract specific pages from a PDF as high-resolution PNG images.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("--output-dir", default="output/3_soa_images", help="Directory to save the output images.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pages", nargs='+', type=int, help="One or more 1-based page numbers to extract (e.g., --pages 51 52 53).")
    group.add_argument("--pages-file", type=str, help="Path to a JSON file containing a list of 0-based page numbers under the 'soa_pages' key.")
    
    args = parser.parse_args()

    pages_to_extract = []
    if args.pages_file:
        try:
            with open(args.pages_file, 'r') as f:
                data = json.load(f)
            pages_to_extract = data['soa_pages'] # These are 0-indexed
            print(f"[INFO] Loaded {len(pages_to_extract)} page numbers from {args.pages_file}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"[ERROR] Could not read page numbers from {args.pages_file}: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.pages:
        # Convert 1-based CLI input to 0-based for the function
        pages_to_extract = [p - 1 for p in args.pages]

    image_paths = extract_pages_as_images(args.pdf_path, pages_to_extract, args.output_dir)
    
    if not image_paths:
        sys.exit(1)
