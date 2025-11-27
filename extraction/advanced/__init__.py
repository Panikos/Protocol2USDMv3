"""
Advanced Entities Extraction Module - Phase 8 of USDM Expansion

Extracts advanced protocol entities:
- StudyAmendment (protocol amendments)
- Condition (conditional logic)
- TransitionRule (workflow rules)
- GeographicScope (countries, regions)
"""

from .extractor import (
    extract_advanced_entities,
    AdvancedExtractionResult,
)
from .schema import (
    AdvancedData,
    StudyAmendment,
    AmendmentReason,
    GeographicScope,
    Country,
    StudySite,
)

__all__ = [
    # Main extraction function
    "extract_advanced_entities",
    "AdvancedExtractionResult",
    # Schema classes
    "AdvancedData",
    "StudyAmendment",
    "AmendmentReason",
    "GeographicScope",
    "Country",
    "StudySite",
]
