"""
Metadata Extraction Module - Phase 2 of USDM Expansion

Extracts study identity and metadata entities from protocol title page and synopsis:
- Study
- StudyVersion  
- StudyTitle
- StudyIdentifier
- Organization
- StudyRole
- Indication
"""

from .extractor import extract_study_metadata, MetadataExtractionResult
from .schema import (
    StudyMetadata,
    StudyTitle,
    StudyIdentifier,
    Organization,
    StudyRole,
    Indication,
)

__all__ = [
    # Main extraction function
    "extract_study_metadata",
    "MetadataExtractionResult",
    # Schema classes
    "StudyMetadata",
    "StudyTitle",
    "StudyIdentifier", 
    "Organization",
    "StudyRole",
    "Indication",
]
