# Protocol2USDMv3

## Overview
This project automates the extraction and structuring of the Schedule of Activities (SoA) from clinical trial protocol PDFs, producing output conformant to the USDM v4.0 model. It uses a hybrid workflow with both text and vision LLMs, validates output against the USDM schema, and supports advanced LLM-based reconciliation.

## Features
- **Automated SoA Extraction**: Identifies and extracts SoA tables from protocol PDFs using keyword search, LLM text, and LLM vision analysis.
- **Dual-Path Workflow**: Extracts both text-based and image-based SoA representations.
- **LLM Adjudication & Reconciliation**: Uses GPT-4o for both adjudicating candidate pages and merging text/vision outputs.
- **Validation**: Validates output against the USDM OpenAPI schema and (stub) v4 CORE rule set.
- **Packaging**: CLI interface, requirements.txt, and modular scripts for easy deployment.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
1. Place your protocol PDF in the project directory.
2. Ensure your `.env` file contains your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...
   ```
3. Run the main workflow:
   ```bash
   python main.py --pdf_path <your_protocol.pdf>
   ```
4. Outputs:
   - `soa_text.json`: SoA extracted from text.
   - `soa_vision.json`: SoA extracted from images (vision).
   - `soa_final.json`: LLM-adjudicated, merged SoA.
   - (Stub) HTML/Markdown rendering for review.

## Project Structure
- `main.py` — Orchestrates the workflow.
- `find_soa_pages.py` — Finds candidate SoA pages.
- `extract_pdf_pages_as_images.py` — Extracts PDF pages as images.
- `vision_extract_soa.py` — LLM vision-based SoA extraction.
- `send_pdf_to_openai.py` — LLM text-based SoA extraction.
- `reconcile_soa_llm.py` — LLM-based reconciliation of text/vision outputs.
- `validate_usdm.py` — Validates output against USDM schema.

## Requirements
See `requirements.txt` for all dependencies.

## Notes
- The workflow is fully automated and robust to both text-based and image-based PDFs.
- For best results, use GPT-4o or a model with vision capabilities for image-based adjudication.
- CORE rule validation is currently a stub; integrate your rule set as needed.

## License
MIT
