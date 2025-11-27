"""
LLM Prompts for Objectives & Endpoints Extraction.

These prompts guide the LLM to extract study objectives and endpoints
from protocol synopsis and objectives sections.
"""

OBJECTIVES_EXTRACTION_PROMPT = """You are an expert at extracting study objectives and endpoints from clinical trial protocols.

Analyze the provided protocol section and extract ALL objectives and their associated endpoints.

## Required Information

### 1. Study Objectives
Extract objectives organized by level:

**Primary Objective(s)**
- The main purpose of the study
- What the study is designed to evaluate

**Secondary Objective(s)**
- Additional goals beyond the primary objective
- Often related to safety, tolerability, or additional efficacy measures

**Exploratory Objective(s)** (if present)
- Hypothesis-generating objectives
- Biomarker or mechanistic objectives

### 2. Endpoints
For each objective, identify the associated endpoint(s):

**Primary Endpoint(s)**
- The main outcome measure
- Used to determine study success

**Secondary Endpoint(s)**
- Supporting outcome measures
- May address safety, tolerability, PK, PD

**Exploratory Endpoint(s)** (if present)
- Additional measures for hypothesis generation

### 3. Estimands (if described, ICH E9(R1))
If the protocol describes estimands, extract:
- Population
- Treatment condition
- Variable (endpoint)
- Intercurrent events and their handling strategies
- Summary measure

## Output Format

Return a JSON object with this exact structure:

```json
{
  "primaryObjectives": [
    {
      "text": "Full text of the primary objective",
      "endpoints": [
        {
          "text": "Full text of the primary endpoint",
          "purpose": "Efficacy"
        }
      ]
    }
  ],
  "secondaryObjectives": [
    {
      "text": "Full text of the secondary objective",
      "endpoints": [
        {
          "text": "Full text of the secondary endpoint",
          "purpose": "Safety"
        }
      ]
    }
  ],
  "exploratoryObjectives": [
    {
      "text": "Full text of the exploratory objective",
      "endpoints": [
        {
          "text": "Full text of the exploratory endpoint",
          "purpose": "Pharmacodynamic"
        }
      ]
    }
  ],
  "estimands": [
    {
      "name": "Primary Estimand",
      "population": "ITT population",
      "treatment": "ALXN1840 vs placebo",
      "variable": "Change from baseline in copper balance",
      "intercurrentEvents": [
        {
          "event": "Treatment discontinuation",
          "strategy": "Treatment Policy"
        }
      ],
      "summaryMeasure": "Difference in means"
    }
  ]
}
```

## Rules

1. **Extract exact text** - Copy objective and endpoint text verbatim
2. **Match endpoints to objectives** - Associate each endpoint with its parent objective
3. **Classify correctly** - Primary, Secondary, Exploratory based on protocol labeling
4. **Purpose categories** - Use: Efficacy, Safety, Tolerability, Pharmacokinetic, Pharmacodynamic, Biomarker, Quality of Life
5. **Be complete** - Extract ALL objectives and endpoints mentioned
6. **Handle variations** - "Primary efficacy objective" = Primary, "Key secondary" = Secondary
7. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the objectives and endpoints:
"""


OBJECTIVES_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study objectives and endpoints.

Look for pages that contain:
1. **Synopsis** - Often has objectives and endpoints summary table
2. **Objectives section** - Usually Section 2 or 3
3. **Endpoints section** - May be combined with objectives or separate
4. **Statistical considerations** - May contain estimand framework

Return a JSON object:
```json
{
  "objectives_pages": [page_numbers],
  "synopsis_page": page_number,
  "endpoints_pages": [page_numbers],
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_objectives_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{OBJECTIVES_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_page_finder_prompt() -> str:
    """Build prompt for finding objectives pages."""
    return OBJECTIVES_PAGE_FINDER_PROMPT
