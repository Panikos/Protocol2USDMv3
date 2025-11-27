"""
Objectives & Endpoints Extraction Module - Phase 3 of USDM Expansion

Extracts study objectives and endpoints from protocol:
- Objective (Primary, Secondary, Exploratory)
- Endpoint
- Estimand (ICH E9(R1))
- IntercurrentEvent
"""

from .extractor import (
    extract_objectives_endpoints,
    ObjectivesExtractionResult,
)
from .schema import (
    Objective,
    Endpoint,
    Estimand,
    IntercurrentEvent,
    ObjectivesData,
    ObjectiveLevel,
    EndpointLevel,
)

__all__ = [
    # Main extraction function
    "extract_objectives_endpoints",
    "ObjectivesExtractionResult",
    # Schema classes
    "Objective",
    "Endpoint",
    "Estimand",
    "IntercurrentEvent",
    "ObjectivesData",
    "ObjectiveLevel",
    "EndpointLevel",
]
