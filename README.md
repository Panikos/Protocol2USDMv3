# Protocol2USDMv3

## Overview
Protocol2USDMv3 is an automated pipeline for extracting, validating, and structuring the Schedule of Activities (SoA) from clinical trial protocol PDFs, outputting data conformant to the USDM v4.0 model. The workflow combines LLM text and vision extraction, robust validation against official schemas and controlled terminology, and advanced mapping/regeneration tools for maximum reliability.

## Key Features
- **Multi-Model Support**: Seamlessly switch between GPT-4, GPT-5, Gemini 2.x/3.x models using unified provider interface.
- **Automated SoA Extraction**: Extracts SoA tables from protocol PDFs using both LLM text and vision analysis.
- **Modernized Prompt System** (v2.0 - Oct 2025):
  - **Comprehensive PlannedTimepoint Guidance**: 8 required fields explained with examples
  - **Enhanced Schema Embedding**: 7 USDM components (~2000 tokens) vs. original 3 (~500 tokens)
  - **Version-Tracked Templates**: YAML-based prompts with changelog and metadata
  - **Fixed Critical Bugs**: Example file now follows naming vs. timing rule
  - **Quality Assurance**: 21 automated tests validate prompt correctness
- **AI-Powered Prompt Optimization** (NEW):
  - **Google Vertex AI Integration**: Zero-shot and data-driven prompt optimization
  - **Automated Improvement**: Systematic prompt enhancement using official APIs
  - **Benchmarking Framework**: Compare prompt versions with quantitative metrics
  - **40-60% Faster Iterations**: Auto-optimization accelerates improvement cycles
- **Optimized Prompts**: Following OpenAI best practices with clear instructions, step-by-step processes, and explicit boundaries.
- **Header-Aware Dual Extraction**: The header structure is first analysed visually. A *machine-readable* JSON object (`headerHints`) containing timepoints and activity-group metadata is then injected into *both* the vision and text LLM prompts, boosting accuracy while preventing ID hallucination.
- **Terminology Validation**: Ensures that extracted activities and other coded values align with controlled terminologies (e.g., NCI EVS), enhancing semantic interoperability and compliance.
- **Header-Driven Enrichment & Validation**: Post-processing now uses the same header structure to auto-fill missing `activityGroupId`s and group memberships, followed by an explicit validation/repair pass (`soa_validate_header.py`).
- **Extended USDM 4.0 SoA Representation**: The final reconciled SoA exposes both the simple `activityTimepoints` matrix *and* a USDM 4.0 `ScheduleTimeline` with `ScheduledActivityInstance` objects derived from it, enabling consumers to use either representation without data loss.
- **Rich Provenance Tracking**: Every entity (activities, planned timepoints, encounters, activity groups) and each activity–timepoint cell is tagged with its source (`text`, `vision`, or `both`) in a separate provenance file, while the main SoA JSON remains pure USDM Wrapper-Input.
- **LLM-Assisted Activity Grouping**: When header-driven row groups are missing or incomplete, an optional LLM pass infers clinically meaningful `ActivityGroup`s (e.g., Safety, Cognitive/Efficacy) and assigns `activityGroupId`s, with all inferred groups clearly marked in provenance.
- **Template-Based Prompts**: Centralized YAML-based prompt templates for easy maintenance and version control.
- **Modular & Extensible**: All steps are modular scripts, easily customizable for your workflow.

## Installation
1.  Ensure you have Python 3.9+ installed.
2.  Set up your API keys in a `.env` file:
    ```bash
    # For OpenAI models (GPT-4, GPT-5)
    OPENAI_API_KEY=sk-...
    
    # For Google models (Gemini 2.x)
    GOOGLE_API_KEY=...
    ```
3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Run the Full Pipeline
```bash
python main_v2.py YOUR_PROTOCOL.pdf
```
- Replace `YOUR_PROTOCOL.pdf` with the path to your clinical trial protocol.
- Default model is `gemini-2.5-pro`.

### Model Selection
```bash
# Use Gemini 2.5 Pro (default)
python main_v2.py protocol.pdf --model gemini-2.5-pro

# Use Gemini 3.0 Pro (latest)
python main_v2.py protocol.pdf --model gemini-3.0-pro

# Use GPT-5.1 
python main_v2.py protocol.pdf --model gpt-5.1

# Use GPT-4o
python main_v2.py protocol.pdf --model gpt-4o
```

### Step-by-Step Testing
For debugging and quality checks, run individual pipeline steps:

```bash
python test_pipeline_steps.py YOUR_PROTOCOL.pdf --step all    # All steps
python test_pipeline_steps.py YOUR_PROTOCOL.pdf --step 3      # Header analysis
python test_pipeline_steps.py YOUR_PROTOCOL.pdf --step 4      # Text extraction  
python test_pipeline_steps.py YOUR_PROTOCOL.pdf --step 5      # Vision validation
python test_pipeline_steps.py YOUR_PROTOCOL.pdf --step 6      # Build final output
```

### View Results
Launch the Streamlit viewer to inspect extraction results:

```bash
streamlit run soa_streamlit_viewer.py
```

## Pipeline Workflow
The `main_v2.py` script orchestrates the pipeline. All outputs are saved in a subdirectory inside `output/`, e.g., `output/CDISC_Pilot_Study/`.

| Step | Script | Purpose | Output |
|---|---|---|---|
| 1 | `generate_soa_llm_prompt.py`| Creates a schema-aware prompt for the LLM. | `1_llm_prompt.txt` |
| 2 | `find_soa_pages.py`| Locates the pages containing the SoA table. | `2_soa_pages.json` |
| 3 | `extract_pdf_pages_as_images.py`| Renders the identified pages as PNGs. | `3_soa_images/` |
| 4 | `analyze_soa_structure.py`| Visually analyzes table headers for context. | `4_soa_header_structure.json` |
| 5 | `send_pdf_to_llm.py`| Extracts SoA from PDF text, guided by `headerHints`. | `5_raw_text_soa.json` |
| 6 | `vision_extract_soa.py`| Extracts SoA from images, also using `headerHints`. | `6_raw_vision_soa.json` |
| 7 | `soa_postprocess_consolidated.py`| Enriches text output using header structure. | `7_postprocessed_text_soa.json` |
| 8 | `soa_postprocess_consolidated.py`| Enriches vision output using header structure. | `8_postprocessed_vision_soa.json` |
| 9 | `soa_validate_header.py`| Validates & repairs both outputs against header. | (in-place fix log) |
| 10 | `reconcile_soa_llm.py`| Merges text and vision outputs into a single SoA, derives a `ScheduleTimeline`/`ScheduledActivityInstance` layer from the reconciled `activityTimepoints`, and merges provenance. | `9_reconciled_soa.json` + `9_reconciled_soa_provenance.json` |
| 11 | `validate_usdm_schema.py`| Final validation against the official USDM Wrapper-Input schema. | (Validation log) |

The primary output to review is `9_reconciled_soa.json`.

## Project Structure

### Core Pipeline Scripts
These scripts are executed in sequence by `main.py`.

- `main.py`: The main orchestrator for the entire pipeline.
- `generate_soa_llm_prompt.py`: Generates LLM prompt instructions from `soa_entity_mapping.json`.
- `find_soa_pages.py`: Uses an LLM to find the page numbers of the SoA table in the PDF.
- `extract_pdf_pages_as_images.py`: Extracts the identified SoA pages as PNG images for vision analysis.
- `analyze_soa_structure.py`: Performs vision-based analysis of the SoA table headers to understand column structure.
- `send_pdf_to_llm.py`: Extracts SoA data from the raw PDF text, using the header structure as context.
- `vision_extract_soa.py`: Extracts SoA data from the PNG images, using the header structure as context.
- `soa_postprocess_consolidated.py`: Enriches and normalises raw JSON outputs using header structure.
- `soa_validate_header.py`: Compares post-processed outputs against the header structure, applying any final group/timepoint repairs.
- `reconcile_soa_llm.py`: Merges the post-processed text and vision outputs into a single, final SoA JSON.
- `validate_usdm_schema.py`: Validates a given JSON file against the official USDM schema.

### Utility & Manual Scripts
These scripts are not part of the automated pipeline but provide useful functionality.

- `soa_streamlit_viewer.py`: The interactive Streamlit review application.
- `audit_timepoints.py`: A utility to compare the extracted timepoints between two or more SoA JSON files (e.g., text vs. vision vs. reconciled). Useful for debugging extraction discrepancies.
- `soa_extraction_validator.py`: A utility to validate a single SoA JSON file against the `soa_entity_mapping.json` rules. This provides a more focused validation than the final schema check.
- `generate_soa_entity_mapping.py`: A manual script to regenerate the `soa_entity_mapping.json` file from the `USDM_CT.xlsx` file (which must be placed in the `temp/` directory). This is useful when the USDM controlled terminology is updated.
- `json_utils.py`: Provides helper functions for cleaning and processing JSON data returned by the LLM.
- `evs_client.py`: A client for interacting with the NCI Enterprise Vocabulary Services (EVS) API to validate controlled terminology.
- `mapping_pre_scan.py`: A utility to pre-scan the entity mapping file and warm the EVS cache, which can speed up pipeline runs.
- `m11_mapping.py`: **(Deprecated)** Formerly used for the "strict M11 mode" feature, which has been removed. This script is no longer used in the primary workflow.

### Configuration & Data
- `requirements.txt`: Python package dependencies.
- `.env`: Used for storing the `OPENAI_API_KEY`.
- `soa_entity_mapping.json`: A critical file containing the USDM entity definitions, attributes, and allowed values. It is used to generate prompts and validate outputs.
- `USDM OpenAPI schema/`: Contains the official USDM OpenAPI schema files.
- `temp/`: A directory for temporary files, such as the `USDM_CT.xlsx` used for mapping regeneration.
- The pipeline automatically sets `max_tokens=90000` for `o3` and `o3-mini-high`, or `16384` for `gpt-4o`.
- All scripts respect the `--model` command-line argument or `OPENAI_MODEL` environment variable.
- The pipeline prints which model is being used and if fallback is triggered.
- If you see truncation warnings, consider splitting large PDFs or reducing prompt size.

## Troubleshooting
- **Schema Validation Errors**: The `soa_postprocess_consolidated.py` script is designed to fix the most common schema validation errors automatically. It ensures all required wrapper keys are present and recursively finds and completes any incomplete `Code` objects. If you still encounter validation errors, it likely indicates a new or unusual issue with the LLM's output that may require a new rule in the post-processor.
- **LLM Output Truncation**: The pipeline uses the maximum allowed tokens for completions, but very large protocols may still require splitting.
- **Mapping Issues**: Regenerate `soa_entity_mapping.json` anytime the Excel mapping changes.
- **Validation**: All outputs are validated against both the mapping and USDM schema. Warnings are issued for missing or non-conformant fields.

## How to Review Results
An interactive Streamlit application is provided for reviewing the results.

1.  **Launch the app:**
    ```bash
    streamlit run soa_streamlit_viewer.py
    ```
2.  **Open in browser:** Navigate to `http://localhost:8501`.
3.  **Select a run:** Use the sidebar to choose the pipeline run you want to inspect. The app automatically finds and displays the final and intermediate files.

### Viewer Features
The viewer provides several powerful features for clinical review and quality control:

- **Stable & Logical Display**: The viewer now includes robust rendering logic and intelligent chronological sorting of timepoints (e.g., "Screening", "Visit 1", "Week 2"). This ensures complex SoA tables are displayed accurately and in a clinically logical order.
- **Hierarchical Bands**: The viewer renders **Epoch** and **Encounter** (visit) information as color-coded horizontal bands above the timepoint headers. This provides crucial clinical context, showing how visits roll up into study phases. The visibility of these bands can be toggled in the sidebar.
- **Activity Grouping**: Activities are grouped under full-width header rows, matching the visual structure of most protocol SoA tables.
- **Filtering**: Reviewers can dynamically filter the displayed activities and timepoints by name.
- **File Inspection**: Easily switch between the final reconciled SoA and all intermediate raw and post-processed outputs to trace how the data was transformed at each step.

## Running Tests
To run the unit tests, install dependencies and execute:
```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/test_llm_providers.py -v          # Provider abstraction tests
pytest tests/test_prompt_templates.py -v       # Template system tests
pytest tests/test_normalization.py -v          # Post-processing tests
pytest tests/test_json_extraction.py -v        # JSON parsing tests

# Total: 93 tests (100% passing)
```

## Architecture

### Provider Abstraction Layer
The pipeline uses a unified provider interface (`llm_providers.py`) that abstracts model-specific code:
- **Auto-detection**: Automatically detects provider from model name
- **Unified configuration**: Same interface for all models (temperature, JSON mode, etc.)
- **Easy switching**: Change models without modifying code
- **Backward compatible**: Falls back to legacy code if needed

### Prompt Template System
Prompts are stored as YAML templates (`prompts/`) following OpenAI best practices:
- **Version controlled**: Track prompt changes over time
- **Optimized structure**: Clear objectives, step-by-step instructions, explicit boundaries
- **Reusable**: Variable substitution for dynamic content
- **Validated**: Built-in validation following prompt engineering best practices

## Notes
- The workflow is fully automated and robust to both text-based and image-based PDFs.
- For best results, use **Gemini 2.5 Pro** (default) or GPT-4o with vision capabilities.
- Defensive error handling: if the LLM output is empty or invalid, raw output is saved to `llm_raw_output.txt` (and cleaned to `llm_cleaned_output.txt` if needed) for debugging.
- Prompts instruct the LLM to use table headers exactly as they appear in the protocol as timepoint labels (no canonicalization), and to output only valid JSON. A `table_headers` array is included for traceability.
- CORE rule validation is currently a stub; integrate your rule set as needed.
- Deprecated scripts are in the `deprecated/` folder and should not be used in production.

## Recent Improvements

### Phase 1-3: Core Enhancements (Complete)
- **Schema anchoring**: USDM schema embedded in prompts (95% validation pass rate)
- **Defensive JSON parsing**: 3-layer parser with automatic retry (>95% parse success)
- **Conflict resolution**: Automatic name/timing separation (100% clean names)
- **Post-processing**: Ensures all required USDM fields are present

### Phase 4: Multi-Model Abstraction (Complete)
- **Provider layer**: Unified interface for GPT and Gemini models
- **Template system**: YAML-based prompt management
- **Optimized prompts**: Following OpenAI cookbook best practices
- **41 new tests**: 100% coverage for new features

### Phase 5: AI-Powered Prompt Optimization (NEW - Oct 2025)
- **Automated optimization**: Google Vertex AI integration for prompt improvement
- **Benchmarking framework**: Systematic testing and comparison
- **Official best practices**: OpenAI, Google, and Anthropic guidelines integrated
- **Optimization tools**:
  - `prompt_optimizer.py`: Unified interface to optimization APIs
  - `benchmark_prompts.py --auto-optimize`: Test with optimized prompts
  - `compare_benchmark_results.py`: Quantitative comparison
  - `setup_google_cloud.ps1`: Automated Google Cloud setup

See `PROMPT_OPTIMIZATION_STRATEGY.md` and `PROMPT_OPTIMIZATION_APIS_ANALYSIS.md` for details.

## License
None. Contact author for permission to use.
