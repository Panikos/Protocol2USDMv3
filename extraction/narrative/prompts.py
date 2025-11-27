"""
LLM Prompts for Document Structure & Narrative Extraction.

These prompts guide the LLM to extract document structure and abbreviations.
"""

ABBREVIATIONS_EXTRACTION_PROMPT = """You are an expert at extracting abbreviations from clinical trial protocols.

Analyze the provided protocol content and extract ALL abbreviations and their definitions.

## Required Information

Extract abbreviations from:
1. **Abbreviations list/table** - Usually near the beginning of the protocol
2. **In-text definitions** - First use with expansion in parentheses
3. **Common clinical abbreviations** - ECG, BP, HbA1c, etc.

## Output Format

Return a JSON object with this exact structure:

```json
{
  "abbreviations": [
    {
      "abbreviation": "ECG",
      "expansion": "Electrocardiogram"
    },
    {
      "abbreviation": "HbA1c",
      "expansion": "Glycated Hemoglobin"
    },
    {
      "abbreviation": "ICF",
      "expansion": "Informed Consent Form"
    }
  ]
}
```

## Rules

1. **Extract exact text** - Use the expansion as written in the protocol
2. **Include all abbreviations** - Even common ones like BP, HR, etc.
3. **Handle variations** - "ECG/EKG" should be separate entries
4. **Case sensitive** - Preserve original case (HbA1c not HBAIC)
5. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the abbreviations:
"""


STRUCTURE_EXTRACTION_PROMPT = """You are an expert at extracting document structure from clinical trial protocols.

Analyze the provided protocol content and extract the section structure.

## Required Information

### 1. Document Information
- Protocol title
- Version number
- Version date

### 2. Major Sections
For each section extract:
- Section number (e.g., "1", "2.1", "5.1.2")
- Section title
- Section type (Synopsis, Objectives, Study Design, Eligibility, Treatment, etc.)

## Output Format

Return a JSON object with this exact structure:

```json
{
  "document": {
    "title": "A Phase 2, Open-Label Study...",
    "version": "3.0",
    "versionDate": "2020-06-15"
  },
  "sections": [
    {
      "number": "1",
      "title": "Introduction",
      "type": "Introduction"
    },
    {
      "number": "2",
      "title": "Study Objectives",
      "type": "Objectives"
    },
    {
      "number": "3",
      "title": "Study Design",
      "type": "Study Design",
      "subsections": [
        {"number": "3.1", "title": "Overview of Study Design"},
        {"number": "3.2", "title": "Rationale for Study Design"}
      ]
    }
  ]
}
```

## Section Types
Use these standard types:
- Synopsis
- Introduction
- Objectives
- Study Design
- Study Population
- Eligibility Criteria
- Treatment
- Study Procedures
- Assessments
- Safety
- Statistics
- Ethics
- References
- Appendix
- Other

## Rules

1. **Extract from TOC** - Use table of contents if available
2. **Include all levels** - Main sections and subsections
3. **Preserve numbering** - Keep original section numbers
4. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the structure:
"""


def build_abbreviations_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{ABBREVIATIONS_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_structure_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{STRUCTURE_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
