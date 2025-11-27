"""
Document Structure & Narrative Extraction Module - Phase 7 of USDM Expansion

Extracts document structure elements from protocol:
- NarrativeContent (section text)
- NarrativeContentItem (subsections)
- Abbreviation
- StudyDefinitionDocument
"""

from .extractor import (
    extract_narrative_structure,
    NarrativeExtractionResult,
)
from .schema import (
    NarrativeData,
    NarrativeContent,
    NarrativeContentItem,
    Abbreviation,
    StudyDefinitionDocument,
)

__all__ = [
    # Main extraction function
    "extract_narrative_structure",
    "NarrativeExtractionResult",
    # Schema classes
    "NarrativeData",
    "NarrativeContent",
    "NarrativeContentItem",
    "Abbreviation",
    "StudyDefinitionDocument",
]
