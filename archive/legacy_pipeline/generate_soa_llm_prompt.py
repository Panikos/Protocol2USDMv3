import json
import os
from pathlib import Path
import argparse
import re

NAMING_RULE = (
    """
    NAMING & TIMING RULE (USDM 4.0 ALIGNED)
    
    1. Dual-Object Requirement:
       • For each planned visit/timepoint you must create **two linked objects**:
         - an Encounter object (class: Encounter) and
         - a PlannedTimepoint (or TimePoint) object (class: PlannedTimepoint or TimePoint).
       • The linking must use a consistent identifier/reference (e.g., id or URI) so that the two objects are programmatically associated.

    2. Naming (Semantic Identity):
       • The attribute Encounter.name **and** PlannedTimepoint.name must be **identical** (exact string match).
       • Each name must contain **only the Visit Label**, e.g. "Visit 1", "Baseline", "Follow-up 1". Do **not** embed timing information (e.g., “Week 4”, “Day 28”) in the name field.
       • The Visit Label should follow your sponsor’s naming pattern or controlled vocabulary and be unique in the context of (studyVersion, armId, epochId) as required.
       • If multiple Arms/Epochs exist and share visit numbers, then either include the context (e.g., “Arm A Visit 1”) in the label or ensure the object carries separate attributes (armId, epochId) to differentiate.

    3. Timing Metadata:
       • Timing information must be captured in **exactly one** location (choose one of):
           a) Preferred: Encounter.timing.windowLabel plus, if applicable, Encounter.timing.windowLower / windowUpper / unit / anchorEvent.
           b) Acceptable fallback: PlannedTimepoint.description (only if timing cannot be placed on Encounter and the description still reflects structured timing semantics).
       • Timing must reference an **anchorEvent** (e.g., “RandomisationDate”, “FirstDoseDate”) and specify unit (e.g., “DAYS”, “WEEKS”). Numeric bounds: windowLower (e.g. –2), windowUpper (e.g. +2).
       • Example:
         - Encounter.name = "Visit 1"
         - Encounter.timing.anchorEvent = "FirstDoseDate"
         - Encounter.timing.windowLabel = "Day 1 ± 2"
         - Encounter.timing.windowLower = –2
         - Encounter.timing.windowUpper = +2
         - Encounter.timing.unit = "DAYS"
       • If using fallback:
         - Encounter.timing may be blank.
         - PlannedTimepoint.name = "Visit 1"
         - PlannedTimepoint.description = "Day 1 ±2 Days from FirstDoseDate"

    4. Unscheduled or Exception Visits:
       • For visits that are unscheduled (e.g., adverse event triggered) apply the same rule: use a semantic label such as “Unscheduled AE Visit”.
       • Use the same dual-object pattern (Encounter + PlannedTimepoint). Timing metadata: may use windowLabel = “Unscheduled – as needed post-AE” or description in PlannedTimepoint.
       • Ensure object includes visitType attribute set to “Unscheduled” (or equivalent) in your data model.

    5. Uniqueness & Versioning:
       • Within a given StudyVersion (per USDM 4.0 versioning model), each combination (Encounter.name + armId + epochId) must be unique.
       • When a protocol amendment changes timing or labels, do not rename the name field solely for timing; instead update timing metadata and maintain object versioning per StudyVersion or Amendment objects.
       • Ensure each object has a unique identifier (id/uri) that remains persistent.

    6. Validation Governance:
       • Implement machine-executable validation rules:
         – Encounter.name == PlannedTimepoint.name
         – name field does *not* contain timing keywords (DAY, WEEK, WKS, MONTH, ±, etc)
         – Exactly one of (Encounter.timing.windowLabel OR PlannedTimepoint.description) is populated for timing metadata
         – If windowLower/windowUpper present then unit is valid per USDM timing value set
         – armId/epochId context uniqueness enforced
       • Document this rule in your Study Metadata Governance Guide; track version history of the rule set.

    """
)

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
        
        # Include core SoA-related schema entities from USDM v4.0
        SCHEMA_ENTITIES_TO_INCLUDE = [
            "Wrapper-Input",                # Root wrapper for study definitions (verify exact name)
            "Wrapper-Output",               # The output counterpart (may be needed)
            "Study-Input",                  # Study definition input (verify name)
            "StudyVersion-Input",           # Study version structure (verify)
            "ScheduleTimeline-Input",       # Timeline / schedule entity (verify name)
            "StudyEpoch-Input",             # Epoch/phase structure (verify name)
            "Encounter-Input",              # Visit/encounter entity (verify name)
            "PlannedTimepoint-Input",       # Added: Many SoA models have a TimePoint entity
            "Activity-Input",               # Procedures and assessments
            "ActivityTimepoint-Input",      # Added: mapping activity to timepoint
            "ActivityGroup-Input",          # Added: grouping of activities
            # Add any additional schema names you identify in the USDM_API.json
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

MINI_EXAMPLE_FALLBACK = (
    """
    **Mini Example (fallback split – timing on PlannedTimepoint):**

    Encounter snippet
    ```json
    {
      "id": "enc-2",
      "instanceType": "Encounter",
      "name": "Visit 2",
      "armId": "Arm A",
      "epochId": "Epoch 1",
      "type": {
        "code": "C25426",
        "decode": "Visit"
      }
      // No timing fields here because timing will be on the PlannedTimepoint
    }
    ```

    Linked PlannedTimepoint snippet
    ```json
    {
      "id": "pt-2",
      "instanceType": "PlannedTimepoint",
      "name": "Visit 2",
      "encounterId": "enc-2",
      "description": "Week 4 from FirstDoseDate ±7 days",
      "value": 28,
      "valueLabel": "Week 4",
      "windowLabel": "±7 days",
      "windowLower": -7,
      "windowUpper": 7,
      "unit": "DAYS",
      "relativeFromScheduledInstanceId": "enc-2",
      "type": { "code": "C99073", "decode": "Fixed Reference" },
      "relativeToFrom": { "code": "C99074", "decode": "Start to Start" },
      "instanceType": "PlannedTimepoint"
    }
    ```
    """
)

MINI_EXAMPLE = MINI_EXAMPLE_FALLBACK

PLANNEDTIMEPOINT_GUIDANCE = """
════════════════════════════════════════════════════════════════════
 PLANNEDTIMEPOINT FIELD GUIDANCE (USDM 4.0 aligned)
════════════════════════════════════════════════════════════════════

The PlannedTimepoint entity is a critical construct in the study-definition model, representing the scheduled moment or interval when a subject’s Encounter occurs or an Activity is planned. Accurate population ensures downstream interoperability, automation and submission-readiness.

**Required Fields:**

1. **id** (string)  
   A unique identifier for this timepoint (e.g., "pt_1", "pt_week4").

2. **instanceType** (string)  
   Must equal “PlannedTimepoint” (or the exact value defined in your USDM implementation) to comply with schema type constraints.

3. **name** (string)  
   This must match the associated Encounter.name exactly (for example "Visit 3", "Screening Visit").  
   - Do NOT embed timing information (such as “Day 1”, “Week 4”) in the name.  
   - Timing metadata must be captured separately (see section on Timing).  
   - This field supports semantic identity (what the visit is) rather than when it occurs.

4. **encounterId** (string)  
   The identifier of the associated Encounter object (one-to-one linkage).  
   Ensures the two objects (Encounter + PlannedTimepoint) remain linked per design.

5. **value** (number)  
   Numeric time offset relative to a defined anchor event (see anchorEvent).  
   - Negative values for times before the anchor (e.g., –7 for “Day –7”).  
   - Zero for the anchor point (e.g., baseline, first dose).  
   - Positive for times after the anchor (e.g., 14 for “Week 2”).  
   - Use the unit defined in the unit attribute; do not assume conversion unless specified.

6. **unit** (string)  
   Unit of the value and window bounds (e.g., “DAYS”, “WEEKS”, “MONTHS”).  
   Must match the value-set defined by USDM for timing units.

7. **valueLabel** (string)  
   Human-readable time label (e.g., "Day –7", "Week 2", "Month 6").  
   Should reflect value + unit in plain form for readability.

8. **anchorEvent** (string)  
   The study milestone from which ‘value’ is offset (e.g., “RandomisationDate”, “FirstDoseDate”).  
   This is crucial to ensure the timepoint is anchored in study logic.

9. **type** (object)  
   A code object indicating the kind of timepoint. For example:  
   - Scheduled visits: `{ "code": "C99073", "decode": "Fixed Reference" }`  
   - Relative timepoints: `{ "code": "C99072", "decode": "After" }` or  
     `{ "code": "C99071", "decode": "Before" }`  
   Use the exact code list defined in USDM controlled terminology.

10. **relativeToFrom** (object)  
    Defines how the offset is measured (e.g., start to start). Example:  
    `{ "code": "C99074", "decode": "Start to Start" }`  
    Use values defined in USDM value-sets.

**Optional Fields (Visit Windows):**

- **windowLabel** (string)  
  Human label for the allowable window around the timepoint (e.g., “±3 days”, “±1 week”).  
- **windowLower** (number)  
  Lower bound of the window (in same unit as value). Example: –3 for “±3 days”.  
- **windowUpper** (number)  
  Upper bound of the window (in same unit as value). Example: +3 for “±3 days”.

**Example – Simple Timepoint:**
```json
{
  "id": "pt_screening",
  "instanceType": "PlannedTimepoint",
  "name": "Screening Visit",
  "encounterId": "enc_screening",
  "value": -7,
  "unit": "DAYS",
  "valueLabel": "Day -7",
  "anchorEvent": "FirstDoseDate",
  "type": { "code": "C99073", "decode": "Fixed Reference" },
  "relativeToFrom": { "code": "C99074", "decode": "Start to Start" }
}
"""

# Complex type guidance for Encounter
ENCOUNTER_TYPE_GUIDANCE = """
======================================================================
 ENCOUNTER TYPE FIELD GUIDANCE (USDM 4.0 aligned)
======================================================================

The Encounter entity represents a subject’s visit or interaction in the study-design Schedule of Activities (SoA). Accurate population of its ‘type’ field is essential for semantic clarity, interoperability, and automation downstream.

**Key Considerations:**
- The `type` field is a **complex datatype** (Code object) that classifies what kind of visit/encounter this is.
- Use the official USDM (or sponsor-governed) controlled terminology for code values and their human-readable decoding.
- Maintain consistency with the Visit Label (Encounter.name) and the attached PlannedTimepoint object to support machine-linkage and avoid ambiguity.

**Required ‘type’ Field Structure:**
```json
{
  "type": {
    "code": "<ControlledTermCode>",
    "decode": "<Human-ReadableLabel>"
  }
}
"""

JSON_OUTPUT_RULES = """
======================================================================
 REQUIRED OUTPUT (JSON ONLY)
======================================================================
- Return one JSON object that conforms to the USDM Wrapper-Input schema.
- Set "usdmVersion" to "4.0.0".
- Top-level keys MUST include: "study" and "usdmVersion".
- No prose, no Markdown, no code fences. The string must be directly loadable by json.loads().

Bad example:  "Here is your JSON:\n{ ... }"
Good example: { ... }

======================================================================
 MODELING RULES
======================================================================
- Use stable, unique IDs for all entities and maintain cross-references.
- The set of activities, plannedTimepoints, encounters, epochs, arms, and activityTimepoints in your output must be derivable from the SoA table body and its headers. Do not create new entities that are not clearly supported by these sources.
- Do not invent assessments, visits, windows, or epochs that are not implied by the SoA.
- When data is missing or ambiguous, use empty arrays/objects or omit the entity rather than hallucinating values.
- For activityTimepoints (the matrix linking activities to plannedTimepoints), ONLY create an entry when the SoA table visibly contains a tick or marker in that cell (for example an "X" or a check mark symbol). Do not infer additional ticks from general statements such as "at each visit" or from clinical expectations; if a cell is ambiguous or unclear, leave it empty.
- Normalize repeated labels (for example "Visit 3" versus "Visit 3.1") consistently across Encounter and PlannedTimepoint.
- Keep all activities in timeline.activities, even if some are unscheduled.
- Every visit should produce exactly one Encounter and one PlannedTimepoint with matching names.
"""

# Full prompt template (kept for reference / future use)
FULL_PROMPT_TEMPLATE = """
======================================================================
 OBJECTIVE
======================================================================
You are an expert at extracting structured data from clinical trial protocols.
Your task is to extract the Schedule of Activities (SoA) and return it as a JSON object graph conforming to the USDM v4.0 model.

======================================================================
 HARD CONSTRAINTS (MUST FOLLOW)
======================================================================
- All entities and values must be derived only from the provided SoA table pages and the associated header structure.
- Do not create any activities, plannedTimepoints, encounters, epochs, arms, or activityTimepoints that are not clearly supported by the SoA table body or its headers.
- For activityTimepoints, only create entries where the SoA table cell visibly contains a tick or marker (for example "X" or a check mark symbol). Never infer ticks from phrases like "at each visit" or from clinical expectations.
- If information is ambiguous or missing, leave fields empty or omit the entity instead of guessing.
- Output exactly one JSON object that conforms to the USDM Wrapper-Input schema, with no extra commentary or explanation.

======================================================================
 USDM WRAPPER-INPUT SCHEMA (AUTHORITATIVE)
======================================================================
The JSON you produce MUST validate against this schema structure:

{usdm_schema_text}

======================================================================
 STUDY DESIGN CLASSIFICATION
======================================================================
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

======================================================================
 ENTITY DEFINITIONS
======================================================================

{entity_instructions}

{naming_rule}

{mini_example}

======================================================================
 OUTPUT REQUIREMENTS
======================================================================

- Use unique IDs for all cross-referencing.
- The output MUST be a single JSON object that exactly matches the **Wrapper-Input** schema (top-level keys: `study`, `usdmVersion`).
- The `studyDesigns` object must also contain the `epochs` array. The `epochs` array should contain `StudyEpoch` objects. `StudyEpoch` objects contain `encounters`, which in turn contain `plannedTimepoints`. The `timeline` object should still contain the full list of `activities`.
- Include empty arrays/objects for any optional fields that are not present in the protocol.
- Set `usdmVersion` to `4.0.0`.

{json_output_rules}
"""

# Lean prompt template focused only on SoA timeline extraction, updated with better entity descriptions.
MINIMAL_PROMPT_TEMPLATE = """
======================================================================
 OBJECTIVE
======================================================================
You are an expert at extracting the Schedule of Activities (SoA) from a clinical trial protocol and converting it to a structured JSON object compliant with USDM v4.0.

Your task is to analyze the provided SoA table(s) and generate a JSON object containing the full timeline of study events.

======================================================================
 HARD CONSTRAINTS (MUST FOLLOW)
======================================================================
- All entities and values must be derived only from the provided SoA table pages and the associated header structure.
- Do not create any activities, plannedTimepoints, encounters, epochs, arms, or activityTimepoints that are not clearly supported by the SoA table body or its headers.
- For activityTimepoints, only create entries where the SoA table cell visibly contains a tick or marker (for example "X" or a check mark symbol). Never infer ticks from phrases like "at each visit" or from clinical expectations.
- If information is ambiguous or missing, leave fields empty or omit the entity instead of guessing.
- Output exactly one JSON object that conforms to the USDM Wrapper-Input schema, with no extra commentary or explanation.

======================================================================
 USDM WRAPPER-INPUT SCHEMA (AUTHORITATIVE)
======================================================================
The JSON you produce MUST validate against this schema structure:

{usdm_schema_text}

======================================================================
 KEY CONCEPTS AND ENTITY RELATIONSHIPS
======================================================================

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

======================================================================
 EXAMPLE OUTPUT FORMAT
======================================================================

To ensure you produce the correct output, here is a small, valid example of the JSON structure. Your output MUST follow this format exactly.

```json
{json_example}
```

======================================================================
 DETAILED SCHEMA DEFINITIONS
======================================================================

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
