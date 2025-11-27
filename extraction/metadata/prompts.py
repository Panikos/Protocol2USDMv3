"""
LLM Prompts for Study Metadata Extraction.

These prompts guide the LLM to extract study identity and metadata
from protocol title pages and synopsis sections.
"""

METADATA_EXTRACTION_PROMPT = """You are an expert at extracting study metadata from clinical trial protocols.

Analyze the provided protocol pages (title page, synopsis, or first few pages) and extract the following information:

## Required Information

### 1. Study Titles
Extract ALL title variations found:
- **Official Study Title**: Full formal title (usually the longest)
- **Brief Study Title**: Short version for registries
- **Study Acronym**: If present (e.g., "REGEN-COV", "KEYNOTE-001")
- **Scientific Study Title**: Technical title if different from official

### 2. Study Identifiers
Extract ALL identifier numbers:
- **NCT Number**: ClinicalTrials.gov ID (format: NCT########)
- **Sponsor Protocol Number**: Company internal ID
- **EudraCT Number**: European registry (format: ####-######-##)
- **IND/IDE Number**: FDA application numbers
- **Any other registry IDs**

### 3. Organizations
Identify organizations involved:
- **Sponsor**: Company/institution funding the study
- **Co-Sponsors**: If any
- **CRO**: Contract Research Organization if mentioned
- **Regulatory references**: FDA, EMA, etc.

### 4. Study Phase
- Phase 1, Phase 2, Phase 3, Phase 4
- Combined phases: Phase 1/2, Phase 2/3
- Or "Not Applicable" for observational studies

### 5. Indication/Disease
- Primary disease or condition being studied
- Is it a rare/orphan disease?
- Medical coding if present (ICD, MedDRA)

### 6. Study Type
- Interventional or Observational

### 7. Protocol Version
- Version number (e.g., "1.0", "2.0", "Amendment 3")
- Protocol date
- Amendment information if applicable

## Output Format

Return a JSON object with this exact structure:

```json
{
  "titles": [
    {"type": "Official Study Title", "text": "..."},
    {"type": "Brief Study Title", "text": "..."},
    {"type": "Study Acronym", "text": "..."}
  ],
  "identifiers": [
    {"type": "NCT Number", "value": "NCT########", "registry": "ClinicalTrials.gov"},
    {"type": "Sponsor Protocol Number", "value": "...", "registry": "Sponsor"}
  ],
  "organizations": [
    {"name": "...", "role": "Sponsor", "type": "Pharmaceutical Company"},
    {"name": "...", "role": "CRO", "type": "Contract Research Organization"}
  ],
  "studyPhase": "Phase 2",
  "indication": {
    "name": "...",
    "description": "...",
    "isRareDisease": false
  },
  "studyType": "Interventional",
  "protocolVersion": {
    "version": "1.0",
    "date": "2020-01-15",
    "amendment": null
  }
}
```

## Rules

1. **Extract exactly what you see** - do not infer or guess information not present
2. **Use null** for fields where information is not found
3. **Preserve exact text** for titles and identifiers
4. **Be case-sensitive** for identifiers (NCT numbers, protocol IDs)
5. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the metadata:
"""


TITLE_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study metadata.

Look for pages that contain:
1. **Title Page**: Usually page 1, contains study title, sponsor, protocol number
2. **Synopsis/Summary**: Usually pages 2-5, contains study overview
3. **Protocol Information Table**: Often on title page or page 2

Return a JSON object:
```json
{
  "title_page": [page_numbers],
  "synopsis_pages": [page_numbers],
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_metadata_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{METADATA_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_vision_extraction_prompt() -> str:
    """Build prompt for vision-based extraction from title page images."""
    return """Analyze this protocol title page image and extract study metadata.

Extract:
1. All study titles (official, brief, acronym)
2. All identifier numbers (NCT, protocol number, EudraCT, etc.)
3. Sponsor and other organizations
4. Study phase
5. Indication/disease
6. Protocol version and date

Return a JSON object with the extracted information. Use null for any fields not visible.
Return ONLY valid JSON, no explanations.

JSON structure:
{
  "titles": [...],
  "identifiers": [...],
  "organizations": [...],
  "studyPhase": "...",
  "indication": {...},
  "studyType": "...",
  "protocolVersion": {...}
}
"""
