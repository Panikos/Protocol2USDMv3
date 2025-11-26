"""
Header Analyzer - Vision-based SoA structure extraction.

This module extracts ONLY the structural information from SoA table images:
- Epochs (study phases from column headers)
- Encounters (visits from column headers)
- PlannedTimepoints (timepoints from column headers)
- ActivityGroups (row section headers)

It does NOT extract:
- Activity details (names, descriptions) - this is text extraction's job
- Tick marks (activity-timepoint matrix) - this is text extraction's job

The output (HeaderStructure) provides the ANCHOR for text extraction,
ensuring text extraction uses the correct IDs and structure.

Usage:
    from extraction.header_analyzer import analyze_soa_headers
    
    result = analyze_soa_headers(image_paths, model_name="gemini-2.5-pro")
    header_structure = result.structure  # Use this to guide text extraction
"""

import json
import base64
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json
from core.usdm_types import HeaderStructure, Epoch, Encounter, PlannedTimepoint, ActivityGroup

logger = logging.getLogger(__name__)


# Focused prompt for STRUCTURE extraction only
HEADER_ANALYSIS_PROMPT = """You are analyzing a Schedule of Activities (SoA) table from a clinical trial protocol.

Your task is to extract ONLY the STRUCTURE of the table - the column headers and row group headers.
Do NOT extract the activity details or tick marks - only the structural elements.

EXTRACT:
1. **Epochs** - Study phases (e.g., "Screening", "Treatment", "Follow-up") 
   - These typically span multiple columns as merged header cells
   
2. **Encounters** - Visit names (e.g., "Visit 1", "Baseline", "Week 4")
   - These are individual column headers representing visits
   
3. **PlannedTimepoints** - Timing information for each encounter
   - Include timing details like "Day -14", "Week 0", "Day 28"
   - Link each timepoint to its encounter
   
4. **ActivityGroups** - Row section headers (e.g., "Safety Assessments", "Efficacy", "Labs")
   - These are the bold/highlighted rows that group related activities

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{
  "columnHierarchy": {
    "epochs": [
      {"id": "epoch_1", "name": "Screening", "position": 1},
      {"id": "epoch_2", "name": "Treatment", "position": 2}
    ],
    "encounters": [
      {"id": "enc_1", "name": "Visit 1", "epochId": "epoch_1"},
      {"id": "enc_2", "name": "Visit 2", "epochId": "epoch_2"}
    ],
    "plannedTimepoints": [
      {"id": "pt_1", "name": "Visit 1", "encounterId": "enc_1", "valueLabel": "Day -14", "description": "Screening visit"},
      {"id": "pt_2", "name": "Visit 2", "encounterId": "enc_2", "valueLabel": "Day 1", "description": "Baseline"}
    ]
  },
  "rowGroups": [
    {"id": "grp_1", "name": "Informed Consent"},
    {"id": "grp_2", "name": "Safety Assessments"},
    {"id": "grp_3", "name": "Efficacy Assessments"}
  ]
}

RULES:
- Use snake_case IDs with sequential numbering (epoch_1, enc_1, pt_1, grp_1)
- Every encounter must reference its parent epoch via epochId
- Every plannedTimepoint must reference its encounter via encounterId
- The name and valueLabel for plannedTimepoints should preserve the exact text from the table
- Include ALL columns and row groups visible in the table
- For multi-page tables, combine all pages into one unified structure
- If epochs are not explicitly shown, create a single "Study Period" epoch

Output ONLY the JSON object, no explanations or markdown."""


@dataclass
class HeaderAnalysisResult:
    """Result of header structure analysis."""
    structure: HeaderStructure
    raw_response: str
    model_used: str
    image_count: int
    success: bool
    error: Optional[str] = None
    
    def to_dict(self):
        return {
            'structure': self.structure.to_dict() if self.structure else None,
            'model_used': self.model_used,
            'image_count': self.image_count,
            'success': self.success,
            'error': self.error,
        }


def encode_image(image_path: str) -> str:
    """Encode image to base64 data URL."""
    with open(image_path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    
    # Determine MIME type
    suffix = Path(image_path).suffix.lower()
    mime_type = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }.get(suffix, 'image/png')
    
    return f"data:{mime_type};base64,{data}"


def analyze_soa_headers(
    image_paths: List[str],
    model_name: str = "gemini-2.5-pro",
    custom_prompt: Optional[str] = None,
) -> HeaderAnalysisResult:
    """
    Analyze SoA table images to extract structural information.
    
    This function extracts ONLY the structure (headers, groups) - not the full SoA data.
    The resulting HeaderStructure is used to anchor text extraction.
    
    Args:
        image_paths: List of paths to SoA table images
        model_name: LLM model to use (must support vision)
        custom_prompt: Optional custom prompt to override default
        
    Returns:
        HeaderAnalysisResult containing the extracted structure
        
    Example:
        >>> result = analyze_soa_headers(["soa_page1.png", "soa_page2.png"])
        >>> if result.success:
        ...     print(f"Found {len(result.structure.encounters)} encounters")
    """
    if not image_paths:
        return HeaderAnalysisResult(
            structure=None,
            raw_response="",
            model_used=model_name,
            image_count=0,
            success=False,
            error="No images provided"
        )
    
    logger.info(f"Analyzing {len(image_paths)} SoA images with {model_name}")
    
    try:
        # Build prompt
        prompt = custom_prompt or HEADER_ANALYSIS_PROMPT
        
        # For Gemini models, use the generative AI library directly
        if 'gemini' in model_name.lower():
            return _analyze_with_gemini(image_paths, model_name, prompt)
        else:
            return _analyze_with_openai(image_paths, model_name, prompt)
            
    except Exception as e:
        logger.error(f"Header analysis failed: {e}")
        return HeaderAnalysisResult(
            structure=None,
            raw_response="",
            model_used=model_name,
            image_count=len(image_paths),
            success=False,
            error=str(e)
        )


def _analyze_with_gemini(
    image_paths: List[str], 
    model_name: str, 
    prompt: str
) -> HeaderAnalysisResult:
    """Analyze using Google Gemini."""
    import google.generativeai as genai
    from PIL import Image
    import io
    import os
    
    # Configure API
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    # Build content with images
    content_parts = [prompt]
    
    for img_path in image_paths:
        img = Image.open(img_path)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        content_parts.append({
            'inline_data': {
                'mime_type': 'image/png',
                'data': base64.b64encode(img_bytes.getvalue()).decode('utf-8')
            }
        })
    
    # Generate response
    response = model.generate_content(
        content_parts,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )
    )
    
    raw_response = response.text or ""
    
    # Parse response
    data = parse_llm_json(raw_response, fallback={})
    structure = HeaderStructure.from_dict(data)
    
    return HeaderAnalysisResult(
        structure=structure,
        raw_response=raw_response,
        model_used=model_name,
        image_count=len(image_paths),
        success=True
    )


def _analyze_with_openai(
    image_paths: List[str], 
    model_name: str, 
    prompt: str
) -> HeaderAnalysisResult:
    """Analyze using OpenAI GPT-4 Vision."""
    from openai import OpenAI
    import os
    from core.constants import REASONING_MODELS
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    
    # Build message content with images
    content = [{"type": "text", "text": prompt}]
    
    for img_path in image_paths:
        data_url = encode_image(img_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url}
        })
    
    # Build parameters - handle reasoning models differently
    is_reasoning = any(rm in model_name.lower() for rm in ['o1', 'o3', 'gpt-5'])
    
    params = {
        "model": model_name,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"},
    }
    
    if is_reasoning:
        params["max_completion_tokens"] = 4096
        # Reasoning models don't support temperature
    else:
        params["max_tokens"] = 4096
        params["temperature"] = 0.1
    
    # Generate response
    response = client.chat.completions.create(**params)
    
    raw_response = response.choices[0].message.content or ""
    
    # Parse response
    data = parse_llm_json(raw_response, fallback={})
    structure = HeaderStructure.from_dict(data)
    
    return HeaderAnalysisResult(
        structure=structure,
        raw_response=raw_response,
        model_used=model_name,
        image_count=len(image_paths),
        success=True
    )


def save_header_structure(structure: HeaderStructure, output_path: str) -> None:
    """
    Save header structure to JSON file.
    
    Args:
        structure: HeaderStructure to save
        output_path: Path to output JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info(f"Saved header structure to {output_path}")


def load_header_structure(input_path: str) -> HeaderStructure:
    """
    Load header structure from JSON file.
    
    Args:
        input_path: Path to input JSON file
        
    Returns:
        Loaded HeaderStructure
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return HeaderStructure.from_dict(data)
