import os
import fitz  # PyMuPDF

# Extract specific pages from a PDF as images (pages are 1-indexed for user, 0-indexed for PyMuPDF)
def extract_pages_as_images(pdf_path, page_numbers, output_dir):
    doc = fitz.open(pdf_path)
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    for page_num in page_numbers:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        image_path = os.path.join(output_dir, f'soa_page_{page_num+1}.png')
        pix.save(image_path)
        image_paths.append(image_path)
    return image_paths

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract specific PDF pages as images.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("page_numbers", help="Comma-separated list of 0-based page numbers (e.g. 52,53)")
    parser.add_argument("output_dir", help="Directory to save images", default="./soa_images", nargs='?')
    args = parser.parse_args()

    page_numbers = [int(x) for x in args.page_numbers.split(",") if x.strip()]
    image_paths = extract_pages_as_images(args.pdf_path, page_numbers, args.output_dir)
    print(",".join(image_paths))
