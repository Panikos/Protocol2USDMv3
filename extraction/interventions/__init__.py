"""
Interventions & Products Extraction Module - Phase 5 of USDM Expansion

Extracts study interventions and products from protocol:
- StudyIntervention
- AdministrableProduct
- Administration (dose, route, frequency)
- MedicalDevice
- Substance
"""

from .extractor import (
    extract_interventions,
    InterventionsExtractionResult,
)
from .schema import (
    InterventionsData,
    StudyIntervention,
    AdministrableProduct,
    Administration,
    MedicalDevice,
    Substance,
    RouteOfAdministration,
    DoseForm,
)

__all__ = [
    # Main extraction function
    "extract_interventions",
    "InterventionsExtractionResult",
    # Schema classes
    "InterventionsData",
    "StudyIntervention",
    "AdministrableProduct",
    "Administration",
    "MedicalDevice",
    "Substance",
    "RouteOfAdministration",
    "DoseForm",
]
