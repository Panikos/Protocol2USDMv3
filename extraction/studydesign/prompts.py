"""
LLM Prompts for Study Design Structure Extraction.

These prompts guide the LLM to extract study design elements
from protocol synopsis and study design sections.
"""

STUDY_DESIGN_EXTRACTION_PROMPT = """You are an expert at extracting study design information from clinical trial protocols.

Analyze the provided protocol section and extract the study design structure.

## Required Information

### 1. Study Design Type
- Is this Interventional or Observational?
- If Interventional: Treatment, Prevention, Diagnostic, Supportive Care, Screening, Health Services Research, Basic Science?

### 2. Blinding
- Open Label, Single Blind, Double Blind, Triple Blind, or Quadruple Blind?
- Who is blinded? (Subject, Investigator, Outcome Assessor, Caregiver, Data Analyst)

### 3. Randomization
- Randomized or Non-Randomized?
- Allocation ratio (e.g., 1:1, 2:1, 1:1:1)
- Stratification factors (e.g., age, disease severity, site)

### 4. Control Type
- Placebo, Active Control, Dose Comparison, No Treatment, Historical Control?

### 5. Study Arms
Extract all treatment arms:
- Arm name
- Arm type (Experimental, Active Comparator, Placebo Comparator, No Intervention)
- Description of treatment in that arm

### 6. Study Cohorts (if any)
Sub-populations within the study:
- Cohort name
- Defining characteristic

### 7. Study Phases/Epochs (if described)
- Screening, Treatment, Follow-up, etc.

## Output Format

Return a JSON object with this exact structure:

```json
{
  "studyDesign": {
    "type": "Interventional",
    "trialIntentTypes": ["Treatment"],
    "blinding": {
      "schema": "Open Label",
      "maskedRoles": []
    },
    "randomization": {
      "type": "Non-Randomized",
      "allocationRatio": null,
      "stratificationFactors": []
    },
    "controlType": null,
    "therapeuticAreas": ["Hepatology"]
  },
  "arms": [
    {
      "name": "ALXN1840 15 mg",
      "type": "Experimental Arm",
      "description": "Participants receive ALXN1840 15 mg once daily"
    },
    {
      "name": "ALXN1840 30 mg", 
      "type": "Experimental Arm",
      "description": "Participants receive ALXN1840 30 mg once daily"
    }
  ],
  "cohorts": [
    {
      "name": "Treatment-naive",
      "characteristic": "Participants who have not received prior WD therapy"
    },
    {
      "name": "Previously treated",
      "characteristic": "Participants with prior chelator or zinc therapy"
    }
  ],
  "epochs": [
    {"name": "Screening", "description": "Up to 21 days"},
    {"name": "Treatment", "description": "24 weeks"},
    {"name": "Follow-up", "description": "4 weeks after last dose"}
  ]
}
```

## Rules

1. **Extract from design section** - Usually Section 3 or Synopsis
2. **Classify arms correctly** - Experimental vs Comparator based on study drug vs control
3. **Identify cohorts** - Sub-groups based on prior treatment, disease severity, etc.
4. **Use standard terminology** - Use USDM-compliant codes where possible
5. **Be complete** - Extract all arms even if they seem similar
6. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the study design:
"""


DESIGN_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study design information.

Look for pages that contain:
1. **Synopsis** - Usually has study design overview table
2. **Study Design section** - Usually Section 3
3. **Randomization/Blinding description**
4. **Treatment arms description**

Return a JSON object:
```json
{
  "design_pages": [page_numbers],
  "synopsis_page": page_number,
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_study_design_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{STUDY_DESIGN_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_page_finder_prompt() -> str:
    """Build prompt for finding study design pages."""
    return DESIGN_PAGE_FINDER_PROMPT
