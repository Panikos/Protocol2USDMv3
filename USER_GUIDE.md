# Protocol2USDMv3 User Guide

**Version:** 4.0  
**Last Updated:** 2025-10-04  
**Status:** Production Ready

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Model Selection](#model-selection)
4. [Running the Pipeline](#running-the-pipeline)
5. [Understanding the Output](#understanding-the-output)
6. [Reviewing Results](#reviewing-results)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Usage](#advanced-usage)
9. [FAQ](#faq)

---

## Quick Start

For users who just want to get started quickly:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up API keys in .env file
echo "GOOGLE_API_KEY=your_key_here" > .env

# 3. Run the pipeline
python main.py input/your_protocol.pdf

# 4. Review results
streamlit run soa_streamlit_viewer.py
```

**Expected runtime:** 5-15 minutes for typical protocols (10-30 pages of SoA content)

---

## Installation

### System Requirements
- **Python:** 3.9 or higher
- **RAM:** 4GB minimum, 8GB recommended
- **Internet:** Required for API calls to OpenAI or Google
- **Operating System:** Windows, macOS, or Linux

### Step-by-Step Installation

#### 1. Clone or Download the Repository
```bash
git clone https://github.com/yourrepo/Protocol2USDMv3.git
cd Protocol2USDMv3
```

#### 2. Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

Key dependencies:
- `openai` - OpenAI API client (GPT models)
- `google-generativeai` - Google Gemini API client
- `PyMuPDF` (fitz) - PDF processing
- `pyyaml` - YAML configuration
- `streamlit` - Interactive viewer
- `pytest` - Testing framework

#### 4. Set Up API Keys

Create a `.env` file in the project root:

```bash
# For Google Gemini models (recommended, default)
GOOGLE_API_KEY=AIzaSy...

# For OpenAI models (GPT-4, GPT-5)
OPENAI_API_KEY=sk-proj-...

# Optional: Default model override
# DEFAULT_MODEL=gemini-2.5-pro
```

**Getting API Keys:**
- **Google AI Studio**: https://makersuite.google.com/app/apikey (Free tier available)
- **OpenAI**: https://platform.openai.com/api-keys (Pay-as-you-go)

#### 5. Verify Installation
```bash
# Run tests to verify everything works
pytest tests/ -v

# Should see: 93 passed in ~20s
```

---

## Model Selection

### Supported Models

The pipeline supports multiple models through a unified interface:

| Model | Provider | Speed | Cost | Quality | Recommended For |
|-------|----------|-------|------|---------|-----------------|
| **gemini-2.5-pro** | Google | Fast | Low | Excellent | **Default, best overall** |
| **gemini-2.0-flash** | Google | Very Fast | Very Low | Good | Quick previews |
| **gpt-4o** | OpenAI | Medium | Medium | Excellent | OpenAI preference |
| **gpt-5** ⚠️ | OpenAI | Medium | High | TBD | Advanced users (reasoning model) |

**Note:** GPT-5 behaves like the o-series reasoning models (no temperature control, uses different API parameters). The provider layer handles this automatically.

### How to Choose a Model

**Use Gemini 2.5 Pro (default) if:**
- ✅ You want the best quality-to-cost ratio
- ✅ You have a Google API key
- ✅ You're processing multiple protocols regularly

**Use GPT-4o if:**
- ✅ You already have OpenAI credits
- ✅ You need consistency with existing OpenAI workflows
- ✅ You're comfortable with OpenAI pricing

**Use Gemini 2.0 Flash if:**
- ✅ You need quick turnaround for testing
- ✅ Cost is a primary concern
- ✅ Quality can be slightly lower for initial drafts

### Specifying Models

```bash
# Use default (gemini-2.5-pro)
python main.py protocol.pdf

# Explicitly specify model
python main.py protocol.pdf --model gemini-2.5-pro
python main.py protocol.pdf --model gpt-4o
python main.py protocol.pdf --model gpt-5

# Set via environment variable
export DEFAULT_MODEL=gpt-4o
python main.py protocol.pdf
```

---

## Running the Pipeline

### Basic Usage

```bash
python main.py <path_to_protocol.pdf> [--model MODEL_NAME]
```

**Example:**
```bash
python main.py input/CDISC_Pilot_Study.pdf --model gemini-2.5-pro
```

### What Happens During Execution

The pipeline executes 11 steps automatically:

```
[Step 1] Generating LLM prompt...                    (~5 seconds)
[Step 2] Finding SoA pages...                        (~10 seconds)
[Step 3] Extracting pages as images...               (~5 seconds)
[Step 4] Analyzing table structure...                (~15 seconds)
[Step 5] Extracting SoA from text...                 (~60 seconds)
[Step 6] Extracting SoA from vision...               (~45 seconds)
[Step 7] Post-processing text output...              (~5 seconds)
[Step 8] Post-processing vision output...            (~5 seconds)
[Step 9] Validating against header structure...      (~2 seconds)
[Step 10] Reconciling text & vision outputs...       (~30 seconds)
[Step 11] Final schema validation...                 (~5 seconds)

Total: ~3-5 minutes (varies by protocol size)
```

### Output Location

All outputs are saved to: `output/<protocol_name>/`

```
output/CDISC_Pilot_Study/
├── 1_llm_prompt.txt                    # Generated prompt
├── 2_soa_pages.json                    # Identified SoA pages
├── 3_soa_images/                       # PNG images of SoA
│   ├── page_52.png
│   ├── page_53.png
│   └── page_54.png
├── 4_soa_header_structure.json         # Header analysis
├── 5_raw_text_soa.json                 # Raw text extraction
├── 6_raw_vision_soa.json               # Raw vision extraction
├── 7_postprocessed_text_soa.json       # Cleaned text
├── 8_postprocessed_vision_soa.json     # Cleaned vision
├── 10_reconciled_soa.json              # ⭐ FINAL OUTPUT
└── pipeline.log                        # Detailed logs
```

**Primary output:** `10_reconciled_soa.json` - This is the file to review!

---

## Understanding the Output

### USDM JSON Structure

The output follows USDM v4.0 Wrapper-Input format:

```json
{
  "usdmVersion": "4.0",
  "systemName": "Protocol2USDMv3",
  "systemVersion": "4.0",
  "study": {
    "versions": [{
      "timeline": {
        "epochs": [...],              // Study phases
        "encounters": [...],          // Visits
        "plannedTimepoints": [...],   // Timepoints
        "activities": [...],          // Procedures/assessments
        "activityTimepoints": [...],  // When activities occur
        "activityGroups": [...]       // Activity categories
      }
    }]
  }
}
```

### Key Entities

**Epochs** - Study phases (e.g., Screening, Treatment, Follow-up)
```json
{
  "id": "epoch_1",
  "name": "Treatment Period",
  "instanceType": "Epoch",
  "position": 1
}
```

**Encounters** - Visits with timing windows
```json
{
  "id": "enc_1",
  "name": "Visit 1",
  "instanceType": "Encounter",
  "epochId": "epoch_1",
  "timing": {
    "windowLabel": "Week -2"
  }
}
```

**PlannedTimepoints** - Specific timepoints when activities occur
```json
{
  "id": "pt_1",
  "name": "Visit 1",
  "instanceType": "PlannedTimepoint",
  "encounterId": "enc_1",
  "description": "Week -2"
}
```

**Activities** - Procedures, assessments, interventions
```json
{
  "id": "act_1",
  "name": "Vital Signs",
  "instanceType": "Activity"
}
```

**ActivityTimepoints** - Mapping of which activities occur at which timepoints
```json
{
  "id": "at_1",
  "instanceType": "ActivityTimepoint",
  "activityId": "act_1",
  "plannedTimepointId": "pt_1"
}
```

---

## Reviewing Results

### Using the Streamlit Viewer

The interactive viewer provides a visual SoA table for review:

```bash
streamlit run soa_streamlit_viewer.py
```

**Browser opens at:** http://localhost:8501

### Viewer Features

1. **Run Selection** (Sidebar)
   - Browse all pipeline runs
   - Select date/time of run to review
   - Switch between files (raw, processed, final)

2. **Visual SoA Table**
   - Color-coded epoch bands
   - Visit/encounter groupings
   - Activity rows with timepoint checkmarks
   - Matches protocol SoA layout

3. **Filtering** (Sidebar)
   - Filter activities by name
   - Filter timepoints by name
   - Show/hide orphaned columns
   - Show/hide epochs/encounters

4. **Quality Indicators**
   - Conflict warnings (if present)
   - Orphaned timepoints (optional display)
   - Provenance tags (text/vision/both)

### Manual Review Checklist

When reviewing `10_reconciled_soa.json`:

- [ ] **All visits present?** Compare to protocol SoA table
- [ ] **Visit names clean?** No timing text like "Week -2" in names
- [ ] **Activities complete?** All procedures/assessments captured
- [ ] **Timing accurate?** WindowLabel and descriptions match protocol
- [ ] **Activity occurrences?** Check marks (✓) in correct columns
- [ ] **No schema errors?** Final validation step passed

---

## Troubleshooting

### Common Issues

#### Issue 1: API Key Not Found
**Error:** `ValueError: GOOGLE_API_KEY environment variable not set`

**Solution:**
```bash
# Check .env file exists
ls .env

# Verify key is set
cat .env | grep API_KEY

# Restart terminal/IDE to reload environment
```

#### Issue 2: Parse Errors
**Error:** `[FATAL] Model 'gemini-2.5-pro' failed: ...`

**What happens:**
- Pipeline automatically retries with stricter prompt
- Falls back to legacy code if needed
- Logs show retry attempts

**Check logs:**
```bash
grep "\[RETRY\]" output/YOUR_PROTOCOL/pipeline.log
grep "\[STATISTICS\]" output/YOUR_PROTOCOL/pipeline.log
```

**Expected statistics:**
```
[STATISTICS] Chunk Processing Results:
  Total chunks: 3
  Successful: 3 (100.0%)
  Failed: 0
```

#### Issue 3: Missing Visits
**Symptom:** Not all visits from protocol appear in output

**Causes:**
- SoA pages not correctly identified (check Step 2)
- Table structure too complex for LLM
- Text extraction quality issues

**Solutions:**
```bash
# Check identified pages
cat output/YOUR_PROTOCOL/2_soa_pages.json

# Review images
ls output/YOUR_PROTOCOL/3_soa_images/

# Compare raw text vs vision outputs
# Text: 5_raw_text_soa.json
# Vision: 6_raw_vision_soa.json
```

#### Issue 4: Schema Validation Errors
**Error:** Final validation reports schema violations

**What to check:**
```bash
# View validation output (Step 11)
grep "Schema validation" output/YOUR_PROTOCOL/pipeline.log

# Common issues:
# - Missing required fields (should be auto-fixed)
# - Invalid cross-references
# - Malformed Code objects
```

**Solutions:**
- Post-processing should fix most issues automatically
- Check `7_postprocessed_*` files for normalization logs
- Review `[POST-PROCESS]` log entries

---

## Advanced Usage

### Customizing Prompts

Prompts are stored as YAML templates in `prompts/`:

```bash
# Edit the SoA extraction prompt
vim prompts/soa_extraction.yaml

# After editing, prompts are automatically reloaded
python main.py protocol.pdf
```

**Template structure:**
```yaml
metadata:
  name: soa_extraction
  version: 2.0
  task_type: extraction

system_prompt: |
  Your instructions here...
  Use {variables} for dynamic content

user_prompt: |
  Process this data: {protocol_text}
```

### Running Individual Steps

You can run pipeline steps individually for debugging:

```bash
# Step 1: Generate prompt
python generate_soa_llm_prompt.py --output output/test/

# Step 2: Find SoA pages
python find_soa_pages.py input/protocol.pdf --output output/test/

# Step 5: Extract from text (requires previous steps)
python send_pdf_to_llm.py input/protocol.pdf \
  --prompt output/test/1_llm_prompt.txt \
  --model gemini-2.5-pro \
  --output output/test/5_raw_text_soa.json
```

### Batch Processing

Process multiple protocols:

```bash
# Create batch script
for pdf in input/*.pdf; do
    echo "Processing $pdf..."
    python main.py "$pdf" --model gemini-2.5-pro
done
```

### Testing New Models

When a new model becomes available:

```bash
# No code changes needed!
python main.py protocol.pdf --model gpt-5

# Provider layer auto-detects:
# - "gpt" pattern → OpenAI
# - "gemini" pattern → Google
```

---

## FAQ

### Q: Which model should I use?
**A:** Use `gemini-2.5-pro` (default). It offers the best balance of quality, speed, and cost.

### Q: How long does the pipeline take?
**A:** 3-5 minutes for typical protocols. Large protocols (50+ SoA pages) may take 10-15 minutes.

### Q: Can I run offline?
**A:** No, the pipeline requires internet access to call LLM APIs.

### Q: How much does it cost?
**A:** Depends on model:
- Gemini 2.5 Pro: ~$0.10-0.50 per protocol
- GPT-4o: ~$0.50-2.00 per protocol
- GPT-5: TBD when available

### Q: What if extraction quality is poor?
**A:** Try these steps:
1. Check that correct SoA pages were identified (Step 2)
2. Review image quality (Step 3)
3. Try a different model (e.g., switch between Gemini and GPT)
4. Check protocol PDF quality (text-based vs scanned)

### Q: Can I modify the output format?
**A:** The output format is USDM v4.0 standard and should not be modified. However, you can:
- Add custom extensions under separate keys
- Post-process for downstream systems
- Export to other formats using the viewer

### Q: How do I report issues?
**A:** 
1. Check `pipeline.log` for error details
2. Run tests: `pytest tests/ -v`
3. Capture logs and example output
4. Contact repository maintainer

### Q: What about HIPAA/PHI compliance?
**A:** 
- API calls send protocol content to cloud providers
- Ensure protocols are de-identified before processing
- Review provider data usage policies:
  - OpenAI: https://openai.com/policies/privacy-policy
  - Google: https://ai.google.dev/terms

### Q: Can I run this in a production environment?
**A:** Yes! The pipeline is production-ready:
- ✅ 93 tests (100% passing)
- ✅ Defensive error handling
- ✅ Automatic retry and fallback
- ✅ Comprehensive logging
- ✅ Schema validation
- ✅ Backward compatible

---

## Support & Resources

### Documentation
- `README.md` - Quick start and overview
- `USER_GUIDE.md` - This file (comprehensive guide)
- `IMPLEMENTATION_COMPLETE.md` - Technical details (Phases 1-3)
- `MULTI_MODEL_IMPLEMENTATION.md` - Provider abstraction details
- `WINDSURF_RULES.md` - Development standards

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific suites
pytest tests/test_llm_providers.py -v
pytest tests/test_prompt_templates.py -v
pytest tests/test_normalization.py -v
```

### Logs
- `output/<protocol>/pipeline.log` - Detailed execution log
- `[DEBUG]` - Low-level details
- `[INFO]` - Progress updates
- `[WARNING]` - Non-fatal issues
- `[FATAL]` - Fatal errors

### Key Files
- `.env` - API keys (keep secure!)
- `requirements.txt` - Dependencies
- `soa_entity_mapping.json` - USDM entity definitions
- `USDM OpenAPI schema/` - Official schema files

---

## Version History

- **v4.0** (2025-10-04) - Multi-model abstraction, prompt optimization
- **v3.0** (2025-07-14) - Header-aware extraction, validation
- **v2.0** (2025-07-13) - Provenance tagging, QC post-processing
- **v1.0** (2025-06-01) - Initial release

---

**Need Help?** Contact: [Repository Maintainer]

**Last Updated:** 2025-10-04 16:30 BST
