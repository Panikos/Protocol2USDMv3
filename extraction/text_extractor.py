"""
Text Extractor - Text-based SoA data extraction.

This module extracts the DATA from protocol text:
- Activities (procedures, assessments) with full details
- ActivityTimepoints (the tick matrix)

It uses the HeaderStructure from vision analysis as an ANCHOR:
- Uses the EXACT IDs from header structure for timepoints/encounters
- Maps activities to the correct timepoints using those IDs
- Prevents ID mismatches between vision and text

This is the PRIMARY data source. Vision provides structure, text provides data.

Usage:
    from extraction.text_extractor import extract_soa_from_text
    from extraction.header_analyzer import load_header_structure
    
    header = load_header_structure("4_soa_header_structure.json")
    result = extract_soa_from_text(protocol_text, header, model_name="gemini-2.5-pro")
"""

import json
import logging
from typing import Optional, List
from dataclasses import dataclass

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json
from core.usdm_types import (
    HeaderStructure, Timeline, Activity, ActivityTimepoint,
    create_wrapper_input
)
from core.provenance import ProvenanceTracker, ProvenanceSource
from core.constants import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION

logger = logging.getLogger(__name__)


def build_extraction_prompt(header_structure: HeaderStructure) -> str:
    """
    Build the text extraction prompt with embedded header structure.
    
    The header structure provides:
    - Exact IDs to use for timepoints and encounters
    - Column structure (which visits exist)
    - Row groups (how activities should be grouped)
    """
    header_json = json.dumps(header_structure.to_dict(), indent=2)
    
    return f"""You are extracting Schedule of Activities (SoA) data from a clinical trial protocol.

HEADER STRUCTURE (from visual analysis):
The following structure has been extracted from the SoA table images. 
You MUST use these EXACT IDs when referencing timepoints and encounters.

```json
{header_json}
```

YOUR TASK:
Extract the ACTIVITIES and TICK MATRIX from the protocol text.

For each activity row in the SoA table:
1. Extract the activity name and description
2. Identify which timepoints have a tick (X, ✓, or similar marker)
3. Create an activityTimepoint entry for EACH tick

CRITICAL RULES:
1. Use EXACT IDs from the header structure above for plannedTimepointId
2. Generate new sequential IDs for activities (act_1, act_2, etc.)
3. ONLY create activityTimepoints where you see an explicit tick mark
4. Do NOT infer ticks from clinical logic or "at every visit" text
5. If unsure about a tick, OMIT it (false negatives are better than false positives)
6. Preserve the activity grouping using activityGroupId from header structure

OUTPUT FORMAT:
Return a JSON object with this structure:
{{
  "activities": [
    {{
      "id": "act_1",
      "name": "Informed Consent",
      "instanceType": "Activity",
      "description": "Obtain written informed consent",
      "activityGroupId": "grp_1"
    }}
  ],
  "activityTimepoints": [
    {{
      "id": "at_1",
      "activityId": "act_1",
      "plannedTimepointId": "pt_1",
      "instanceType": "ActivityTimepoint"
    }}
  ]
}}

IMPORTANT:
- The plannedTimepointId values MUST match IDs from the header structure
- Do not create new timepoint IDs - only reference existing ones
- Include ALL activities from the SoA table
- Include ALL visible tick marks

Output ONLY the JSON object, no explanations or markdown."""


@dataclass
class TextExtractionResult:
    """Result of text-based SoA extraction."""
    activities: List[Activity]
    activity_timepoints: List[ActivityTimepoint]
    raw_response: str
    model_used: str
    success: bool
    provenance: ProvenanceTracker
    error: Optional[str] = None
    
    def to_timeline(self, header: HeaderStructure) -> Timeline:
        """Convert to Timeline by combining with header structure."""
        return Timeline(
            activities=self.activities,
            plannedTimepoints=header.plannedTimepoints,
            encounters=header.encounters,
            epochs=header.epochs,
            activityGroups=header.activityGroups,
            activityTimepoints=self.activity_timepoints,
        )


def extract_soa_from_text(
    protocol_text: str,
    header_structure: HeaderStructure,
    model_name: str = "gemini-2.5-pro",
    soa_pages: Optional[List[int]] = None,
) -> TextExtractionResult:
    """
    Extract SoA data from protocol text using header structure as anchor.
    
    Args:
        protocol_text: Full protocol text or SoA-specific text
        header_structure: Structure from vision analysis (provides IDs)
        model_name: LLM model to use
        soa_pages: Optional list of page numbers to focus on
        
    Returns:
        TextExtractionResult containing activities and ticks
        
    Example:
        >>> header = load_header_structure("header.json")
        >>> result = extract_soa_from_text(text, header)
        >>> print(f"Found {len(result.activities)} activities")
    """
    logger.info(f"Extracting SoA from text with {model_name}")
    
    provenance = ProvenanceTracker()
    provenance.metadata['model'] = model_name
    provenance.metadata['extraction_type'] = 'text'
    
    try:
        # Build prompt with header structure embedded
        prompt = build_extraction_prompt(header_structure)
        
        # Get LLM client
        client = get_llm_client(model_name)
        
        # Build messages
        messages = [
            {"role": "system", "content": "You are an expert in clinical trial protocols and CDISC USDM standards."},
            {"role": "user", "content": f"{prompt}\n\nPROTOCOL TEXT:\n\n{protocol_text}"}
        ]
        
        # Configure for JSON output
        config = LLMConfig(
            temperature=0.0,
            json_mode=True,
        )
        
        # Generate response
        response = client.generate(messages, config)
        raw_response = response.content
        
        # Parse response
        data = parse_llm_json(raw_response, fallback={})
        
        # Extract activities
        activities = [
            Activity.from_dict(a) for a in data.get('activities', [])
        ]
        
        # Extract activity timepoints
        activity_timepoints = [
            ActivityTimepoint.from_dict(at) for at in data.get('activityTimepoints', [])
        ]
        
        # Tag provenance
        provenance.tag_entities('activities', [a.to_dict() for a in activities], ProvenanceSource.TEXT)
        provenance.tag_cells_from_timepoints(
            [at.to_dict() for at in activity_timepoints], 
            ProvenanceSource.TEXT
        )
        
        logger.info(f"Extracted {len(activities)} activities, {len(activity_timepoints)} ticks")
        
        return TextExtractionResult(
            activities=activities,
            activity_timepoints=activity_timepoints,
            raw_response=raw_response,
            model_used=model_name,
            success=True,
            provenance=provenance,
        )
        
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return TextExtractionResult(
            activities=[],
            activity_timepoints=[],
            raw_response="",
            model_used=model_name,
            success=False,
            provenance=provenance,
            error=str(e),
        )


def build_usdm_output(
    extraction_result: TextExtractionResult,
    header_structure: HeaderStructure,
) -> dict:
    """
    Build complete USDM Wrapper-Input JSON from extraction results.
    
    Combines:
    - Structure from header analysis (epochs, encounters, timepoints, groups)
    - Data from text extraction (activities, ticks)
    
    Args:
        extraction_result: Result from text extraction
        header_structure: Structure from header analysis
        
    Returns:
        Complete USDM Wrapper-Input dict
    """
    timeline = extraction_result.to_timeline(header_structure)
    
    return create_wrapper_input(
        timeline=timeline,
        usdm_version=USDM_VERSION,
        system_name=SYSTEM_NAME,
        system_version=SYSTEM_VERSION,
    )


def save_extraction_result(
    result: TextExtractionResult,
    header: HeaderStructure,
    output_path: str,
    provenance_path: Optional[str] = None,
) -> None:
    """
    Save extraction result to USDM JSON file.
    
    Args:
        result: Extraction result
        header: Header structure to combine with
        output_path: Path for USDM JSON output
        provenance_path: Optional path for provenance JSON (separate file)
    """
    # Build and save USDM output
    usdm_output = build_usdm_output(result, header)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(usdm_output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved USDM output to {output_path}")
    
    # Save provenance separately if path provided
    if provenance_path:
        result.provenance.save(provenance_path)
        logger.info(f"Saved provenance to {provenance_path}")
