"""
LLM Prompts for Advanced Entities Extraction.

These prompts guide the LLM to extract amendments, geographic scope, and sites.
"""

ADVANCED_EXTRACTION_PROMPT = """You are an expert at extracting protocol amendment and geographic information from clinical trial protocols.

Analyze the provided protocol content and extract advanced protocol entities.

## Required Information

### 1. Protocol Amendments
For each amendment extract:
- Amendment number
- Effective date
- Summary of changes
- Previous and new version numbers
- Reasons for amendment

### 2. Geographic Scope
- List of participating countries
- Regions (if mentioned)
- Number of planned sites (if mentioned)

### 3. Study Sites (if listed)
- Site names or numbers
- City and country

## Output Format

Return a JSON object with this exact structure:

```json
{
  "amendments": [
    {
      "number": "1",
      "effectiveDate": "2020-06-15",
      "summary": "Changed primary endpoint timing from Week 12 to Week 24",
      "previousVersion": "1.0",
      "newVersion": "2.0",
      "reasons": ["Efficacy", "Regulatory"]
    }
  ],
  "geographicScope": {
    "type": "Global",
    "countries": [
      {"name": "United States", "code": "US"},
      {"name": "Germany", "code": "DE"},
      {"name": "United Kingdom", "code": "UK"}
    ],
    "regions": ["North America", "Europe"],
    "plannedSites": 20
  },
  "sites": [
    {
      "number": "001",
      "name": "University Hospital",
      "city": "Boston",
      "country": "United States"
    }
  ]
}
```

## Rules

1. **Extract from amendment sections** - Look for "Protocol Amendment" or version history
2. **Check title page** - May contain version and date info
3. **Standard country codes** - Use ISO 3166-1 alpha-2 codes when possible
4. **Amendment reasons** - Common reasons: Safety, Efficacy, Regulatory, Administrative, Operational
5. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the advanced entities:
"""


def build_advanced_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{ADVANCED_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
