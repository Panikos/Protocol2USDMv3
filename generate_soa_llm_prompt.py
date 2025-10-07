import json
import os
from pathlib import Path
import argparse
import re

NAMING_RULE = (
    "**Naming vs. Timing Rule**\n\n"
    "For every visit you must output **two linked objects**: an `Encounter` and a `PlannedTimepoint` (PT).\n\n"
    "1. `Encounter.name` **and** `PlannedTimepoint.name` **must be identical** and contain ONLY the visit label — e.g., `\"Visit 1\"`. **Do NOT** include timing details such as weeks or days.\n"
    "2. Put timing information (e.g., `\"Week -2\"`, `\"Day 1 ±2\"`) in *exactly one* of these places:\n"
    "   • Preferred: `Encounter.timing.windowLabel` (and use `timing.windowLower/Upper` if you have numeric bounds).\n"
    "   • Acceptable fallback: `PlannedTimepoint.description` if a window label is not applicable.\n"
    "3. Never repeat the timing text inside the `name` field.\n")

MAPPING_PATH = "soa_entity_mapping.json"
SCHEMA_PATH = "USDM OpenAPI schema/USDM_API.json"

# PROMPT CHANGELOG:
# 2025-10-04: Added schema anchoring + JSON-only fences (v1.1)
# Initial version with naming vs. timing rule (v1.0)

def load_usdm_schema_text(schema_path: str, max_tokens: int = 12000) -> str:
    """
    Load OpenAPI/JSON schema text and compact it for prompting.
    Focuses on the Wrapper-Input component to keep token budget manageable.
    
    Args:
        schema_path: Path to USDM OpenAPI schema JSON file
        max_tokens: Maximum characters to return (rough token budget: 1 token ≈ 4 chars)
    
    Returns:
        Minified schema text suitable for embedding in prompts
    """
    p = Path(schema_path)
    if not p.exists():
        print(f"[WARNING] Schema file not found: {schema_path}. Skipping schema embedding.")
        return "[Schema file not available]"
    
    try:
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            schema_data = json.load(f)
        
        # Extract just the Wrapper-Input and all SoA-related schemas
        components = schema_data.get('components', {}).get('schemas', {})
        
        # Include all SoA-related schemas that exist in USDM
        SCHEMA_ENTITIES_TO_INCLUDE = [
            "Wrapper-Input",
            "Study-Input",
            "StudyVersion-Input",
            "ScheduleTimeline-Input",        # NEW - provides timeline structure  
            "StudyEpoch-Input",              # NEW - study phases (actual name in schema)
            "Encounter-Input",               # NEW - visits
            "Activity-Input",                # NEW - procedures/assessments
            # Note: PlannedTimepoint, ActivityTimepoint, ActivityGroup don't exist as
            # separate Input schemas - they're embedded in the timeline structure
        ]
        
        # Build schema subset with all SoA entities
        minimal_schema = {
            name: components.get(name, {})
            for name in SCHEMA_ENTITIES_TO_INCLUDE
            if name in components
        }
        
        # Serialize and minify
        schema_json = json.dumps(minimal_schema, separators=(',', ':'))
        
        # Light minification: collapse excessive whitespace
        schema_json = re.sub(r'\s+', ' ', schema_json)
        
        # Truncate at entity boundaries if needed (not mid-field)
        if len(schema_json) > max_tokens * 4:  # rough 1 token ≈ 4 chars
            print(f"[WARNING] Schema length ({len(schema_json)} chars) exceeds budget. Truncating...")
            # Find last complete entity before limit
            truncate_pos = max_tokens * 4
            last_brace = schema_json.rfind('}', 0, truncate_pos)
            if last_brace > 0:
                schema_json = schema_json[:last_brace + 1] + "}"
            else:
                schema_json = schema_json[:truncate_pos] + "...}}"
            print(f"[INFO] Schema truncated to ~{max_tokens} tokens")
        else:
            print(f"[INFO] Schema size: {len(schema_json)} chars (~{len(schema_json) // 4} tokens)")
        
        return schema_json
    
    except Exception as e:
        print(f"[WARNING] Could not load schema from {schema_path}: {e}")
        return "[Schema load error]"

MINI_EXAMPLE = (
    "**Mini Example (correct split):**\n\n"
    "Encounter snippet\n"
    "```json\n"
    "{ \"id\": \"enc-1\", \"name\": \"Visit 1\",\n"
    "  \"timing\": { \"windowLabel\": \"Week -2\" } }\n"
    "```\n\n"
    "Linked PlannedTimepoint snippet\n"
    "```json\n"
    "{ \"id\": \"pt-1\", \"encounterId\": \"enc-1\",\n"
    "  \"name\": \"Visit 1\", \"description\": \"Week -2\" }\n"
    "```\n")

# Detailed PlannedTimepoint guidance for complex temporal fields
PLANNEDTIMEPOINT_GUIDANCE = """
════════════════════════════════════════════════════════════════════
 PLANNEDTIMEPOINT FIELD GUIDANCE
════════════════════════════════════════════════════════════════════

PlannedTimepoint is one of the most complex entities. Here's how to populate its required fields:

**Required Fields:**

1. **id** (string): Unique identifier (e.g., "pt_1", "pt_week4")

2. **name** (string): MUST match the Encounter name exactly (e.g., "Visit 3", "Screening Visit")
   - Do NOT include timing information in the name
   - Timing goes in `description` or `Encounter.timing.windowLabel`

3. **encounterId** (string): Reference to the associated Encounter's ID

4. **value** (number): Numeric time offset
   - Negative for times before baseline (e.g., -7 for "Day -7")
   - Zero for baseline
   - Positive for times after baseline (e.g., 14 for "Week 2")
   - Use days as the unit (Week 2 = 14, Month 1 = 30)

5. **valueLabel** (string): Human-readable time label (e.g., "Day -7", "Week 2", "Month 6")

6. **relativeFromScheduledInstanceId** (string): Usually the encounterId for visit-based timepoints

7. **type** (object): Code indicating the timepoint type
   - For scheduled visits: `{"code": "C99073", "decode": "Fixed Reference"}`
   - For relative timepoints: `{"code": "C99072", "decode": "After"}` or `{"code": "C99071", "decode": "Before"}`

8. **relativeToFrom** (object): How the timing is measured
   - Most common: `{"code": "C99074", "decode": "Start to Start"}`
   - Other options: "End to End", "Start to End", "End to Start"

**Optional Fields for Visit Windows:**

- **windowLabel** (string): Window description (e.g., "±3 days", "±1 week")
- **windowLower** (number): Lower bound in days (e.g., -3 for "±3 days")
- **windowUpper** (number): Upper bound in days (e.g., 3 for "±3 days")

**Example - Simple Timepoint:**
```json
{
  "id": "pt_screening",
  "name": "Screening Visit",
  "description": "Day -7",
  "encounterId": "enc_screening",
  "value": -7,
  "valueLabel": "Day -7",
  "relativeFromScheduledInstanceId": "enc_screening",
  "type": {"code": "C99073", "decode": "Fixed Reference"},
  "relativeToFrom": {"code": "C99074", "decode": "Start to Start"},
  "instanceType": "PlannedTimepoint"
}
```

**Example - With Visit Window:**
```json
{
  "id": "pt_week4",
  "name": "Visit 5",
  "description": "Week 4",
  "encounterId": "enc_week4",
  "value": 28,
  "valueLabel": "Week 4",
  "windowLabel": "±7 days",
  "windowLower": -7,
  "windowUpper": 7,
  "relativeFromScheduledInstanceId": "enc_week4",
  "type": {"code": "C99073", "decode": "Fixed Reference"},
  "relativeToFrom": {"code": "C99074", "decode": "Start to Start"},
  "instanceType": "PlannedTimepoint"
}
```

**Common Patterns:**
- Screening visits: Negative values (Day -14, Day -7)
- Baseline/Randomization: value = 0, valueLabel = "Day 1" or "Baseline"
- Follow-up visits: Positive values (Week 2 = 14 days, Week 4 = 28 days)
- Early Termination (ET): Often relative timepoint
- Unscheduled visits: May not have fixed value

**Critical Rule:** ALWAYS ensure PlannedTimepoint.name matches its Encounter.name exactly!
"""

# Complex type guidance for Encounter
ENCOUNTER_TYPE_GUIDANCE = """
════════════════════════════════════════════════════════════════════
 ENCOUNTER TYPE FIELD GUIDANCE
════════════════════════════════════════════════════════════════════

The Encounter entity has a required `type` field that is a complex datatype (Code object).

**Required Structure:**
```json
{
  "type": {
    "code": "C25426",
    "decode": "Visit"
  }
}
```

For clinical trial SoAs, the type is almost always "Visit".

**Full Encounter Example:**
```json
{
  "id": "enc_1",
  "name": "Screening Visit",
  "description": "Initial screening assessment",
  "epochId": "epoch_screening",
  "type": {
    "code": "C25426",
    "decode": "Visit"
  },
  "timing": {
    "windowLabel": "Day -7"
  },
  "instanceType": "Encounter"
}
```
"""

# JSON-only output fences with positive/negative examples
JSON_OUTPUT_RULES = """
════════════════════════════════════════════════════════════════════
 REQUIRED OUTPUT (JSON ONLY)
════════════════════════════════════════════════════════════════════
- Return **one** JSON object that **conforms to the USDM Wrapper-Input schema**.
- Set "usdmVersion" to "4.0.0".
- Top-level keys MUST include: "study", "usdmVersion".
- **No prose, no Markdown, no code fences**. The string must be directly loadable by `json.loads()`.

❌ Bad: "Here is your JSON:\n{ ... }"
✅ Good: { ... }

════════════════════════════════════════════════════════════════════
 MODELING RULES
════════════════════════════════════════════════════════════════════
- Use **stable, unique IDs** for all entities and maintain cross-references.
- Do **not invent** assessments, visits, windows, or epochs that are not implied by the SoA.
- When data is missing, **use empty arrays/objects** rather than hallucinating values.
- Normalize repeated labels (e.g., "Visit 3", "Visit 3.1") consistently across `Encounter` + `PlannedTimepoint`.
- Keep all activities in `timeline.activities`, even if some are unscheduled.
- Every visit should produce exactly ONE `Encounter` + ONE `PlannedTimepoint` with matching names.
"""

# Full prompt template (kept for reference / future use)
FULL_PROMPT_TEMPLATE = """
════════════════════════════════════════════════════════════════════
 OBJECTIVE
════════════════════════════════════════════════════════════════════
You are an expert at extracting structured data from clinical trial protocols.
Your task is to extract the Schedule of Activities (SoA) and return it as a JSON object graph conforming to the USDM v4.0 model.

════════════════════════════════════════════════════════════════════
 USDM WRAPPER-INPUT SCHEMA (AUTHORITATIVE)
════════════════════════════════════════════════════════════════════
The JSON you produce MUST validate against this schema structure:

{usdm_schema_text}

════════════════════════════════════════════════════════════════════
 STUDY DESIGN CLASSIFICATION
════════════════════════════════════════════════════════════════════
1.  **Analyze and Classify the Study Design:** First, determine if the study is an **Interventional** or **Observational** study based on the protocol description.
2.  **Generate the Correct StudyDesign Object:** The `study.versions[0].studyDesigns` array must contain exactly ONE study design object. Based on your classification, you MUST generate either an `InterventionalStudyDesign` or an `ObservationalStudyDesign` object.

    *   **If Interventional:**
        *   Set `instanceType` to `InterventionalStudyDesign`.
        *   You MUST include the `trialType` attribute.
        *   Only include the fields listed below for `InterventionalStudyDesign`.

    *   **If Observational:**
        *   Set `instanceType` to `ObservationalStudyDesign`.
        *   You MUST include the `observationalStudyModel` attribute.
        *   Only include the fields listed below for `ObservationalStudyDesign`.

════════════════════════════════════════════════════════════════════
 ENTITY DEFINITIONS
════════════════════════════════════════════════════════════════════

{entity_instructions}

{naming_rule}

{mini_example}

════════════════════════════════════════════════════════════════════
 OUTPUT REQUIREMENTS
════════════════════════════════════════════════════════════════════

- Use unique IDs for all cross-referencing.
- The output MUST be a single JSON object that exactly matches the **Wrapper-Input** schema (top-level keys: `study`, `usdmVersion`).
- The `studyDesigns` object must also contain the `epochs` array. The `epochs` array should contain `StudyEpoch` objects. `StudyEpoch` objects contain `encounters`, which in turn contain `plannedTimepoints`. The `timeline` object should still contain the full list of `activities`.
- Include empty arrays/objects for any optional fields that are not present in the protocol.
- Set `usdmVersion` to `4.0.0`.

{json_output_rules}
"""

# Lean prompt template focused only on SoA timeline extraction, updated with better entity descriptions.
MINIMAL_PROMPT_TEMPLATE = """
════════════════════════════════════════════════════════════════════
 OBJECTIVE
════════════════════════════════════════════════════════════════════
You are an expert at extracting the Schedule of Activities (SoA) from a clinical trial protocol and converting it to a structured JSON object compliant with USDM v4.0.

Your task is to analyze the provided SoA table(s) and generate a JSON object containing the full timeline of study events.

════════════════════════════════════════════════════════════════════
 USDM WRAPPER-INPUT SCHEMA (AUTHORITATIVE)
════════════════════════════════════════════════════════════════════
The JSON you produce MUST validate against this schema structure:

{usdm_schema_text}

════════════════════════════════════════════════════════════════════
 KEY CONCEPTS AND ENTITY RELATIONSHIPS
════════════════════════════════════════════════════════════════════

The SoA is structured around a few core entities. Understanding their relationships is crucial for correct extraction:

*   **Epochs:** These are the major phases of the study (e.g., Screening, Treatment, Follow-up).
*   **Encounters:** These represent the specific visits or time windows within an Epoch (e.g., "Screening Visit", "Week 4 Visit").
*   **PlannedTimepoints:** These are the precise moments or intervals when activities happen. They are often linked to Encounters. (e.g., "Day 1", "Week 4").
*   **Activities:** These are the individual procedures or assessments performed (e.g., "Physical Exam", "Blood Draw").
*   **ActivityTimepoints:** This is the mapping that links an Activity to a PlannedTimepoint, indicating *what* happens *when*.
*   **ActivityGroups:** These are optional groupings for related activities (e.g., "Vital Signs"). When an activity belongs to a group, you **MUST** set the `activityGroupId` field on the Activity object to the ID of the corresponding ActivityGroup.

{naming_rule}

{mini_example}

{plannedtimepoint_guidance}

{encounter_type_guidance}

════════════════════════════════════════════════════════════════════
 EXAMPLE OUTPUT FORMAT
════════════════════════════════════════════════════════════════════

To ensure you produce the correct output, here is a small, valid example of the JSON structure. Your output MUST follow this format exactly.

```json
{json_example}
```

════════════════════════════════════════════════════════════════════
 DETAILED SCHEMA DEFINITIONS
════════════════════════════════════════════════════════════════════

Below are the specific fields you must use for each entity. Do not invent new fields or entity types.

{entity_instructions}

{json_output_rules}
"""

def generate_entity_instructions(mapping):
    lines = []
    for entity, sections in mapping.items():
        lines.append(f"For {entity}:")
        for section in ["attributes", "relationships", "complex_datatype_relationships"]:
            if section in sections:
                for field, meta in sections[section].items():
                    allowed = ""
                    if 'allowed_values' in meta and meta['allowed_values']:
                        allowed_vals = ', '.join(f"{v['term']}" for v in meta['allowed_values'])
                        allowed = f" (allowed: {allowed_vals})"
                    required_text = " (required)" if meta.get('required') else ""
                    lines.append(f"  - {field} [{meta.get('role', section)}]{allowed}{required_text}")
        lines.append("")
    return '\n'.join(lines)

# Entities that are strictly required for the SoA timeline
SOA_CORE_ENTITIES = {
    "Activity",
    "PlannedTimepoint",
    "ActivityGroup",
    "ActivityTimepoint",
    "Encounter",
    "Epoch",
    "StudyArm",
    "StudyElement"
}

# Simple grouping heuristic – can be made data-driven later
ENTITY_GROUPS = {
    "soa_core": set(SOA_CORE_ENTITIES),
    "study_design": {
        "StudyVersion",
        "InterventionalStudyDesign",
        "ObservationalStudyDesign",
        "StudyEpoch",
        "Encounter"
    },
    "interventions": {
        "Administration",
        "AdministrableProduct",
        "MedicalDevice",
        "Substance"
    },
    "eligibility": {
        "EligibilityCriterion",
        "EligibilityCriterionItem",
        "EligibilityCriterionGroup"
    }
}

def filter_mapping(mapping, allowed_entities):
    """Return a copy of mapping containing only the allowed entities."""
    return {k: v for k, v in mapping.items() if k in allowed_entities}

def write_prompt(path: Path, template: str, **kwargs):
    path.write_text(template.format(**kwargs), encoding="utf-8")
    print(f"[PROMPT] Wrote {path}")

def main():
    parser = argparse.ArgumentParser(description="Generate LLM prompts from the SoA entity mapping.")
    parser.add_argument("--output", default="output/1_llm_prompt.txt", help="Path to write the minimal SoA prompt file.")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define paths for other generated files based on the primary output path
    full_prompt_path = output_dir / "1_llm_prompt_full.txt"
    groups_path = output_dir / "1_llm_entity_groups.json"

    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # --- Load the one-shot example ---
    example_path = Path("soa_prompt_example.json")
    if not example_path.exists():
        raise FileNotFoundError(f"Could not find the prompt example file at {example_path}")
    example_json_str = example_path.read_text(encoding="utf-8")

    # --- Load USDM schema for embedding in prompts ---
    usdm_schema_text = load_usdm_schema_text(SCHEMA_PATH)
    print(f"[INFO] Loaded USDM schema: {len(usdm_schema_text)} characters")
    
    # --- write minimal SoA prompt ---
    minimal_mapping = filter_mapping(mapping, SOA_CORE_ENTITIES)
    minimal_instr = generate_entity_instructions(minimal_mapping)
    write_prompt(
        output_path, 
        MINIMAL_PROMPT_TEMPLATE, 
        entity_instructions=minimal_instr, 
        json_example=example_json_str, 
        naming_rule=NAMING_RULE, 
        mini_example=MINI_EXAMPLE,
        plannedtimepoint_guidance=PLANNEDTIMEPOINT_GUIDANCE,
        encounter_type_guidance=ENCOUNTER_TYPE_GUIDANCE,
        usdm_schema_text=usdm_schema_text,
        json_output_rules=JSON_OUTPUT_RULES
    )

    # --- keep full prompt for future richer extraction steps (doesn't need the example) ---
    full_instr = generate_entity_instructions(mapping)
    write_prompt(
        full_prompt_path, 
        FULL_PROMPT_TEMPLATE, 
        entity_instructions=full_instr, 
        naming_rule=NAMING_RULE, 
        mini_example=MINI_EXAMPLE,
        usdm_schema_text=usdm_schema_text,
        json_output_rules=JSON_OUTPUT_RULES
    )

    # --- write grouped entity catalogue ---
    grouped = {}
    for group, ents in ENTITY_GROUPS.items():
        grouped[group] = {e: mapping[e] for e in ents if e in mapping}
    # anything not assigned already
    other = {k: v for k, v in mapping.items() if all(k not in gset for gset in ENTITY_GROUPS.values())}
    grouped["other"] = other
    with open(groups_path, "w", encoding="utf-8") as gf:
        json.dump(grouped, gf, indent=2)
    print(f"[SUCCESS] Wrote grouped entity definitions to {groups_path}")

if __name__ == "__main__":
    main()
