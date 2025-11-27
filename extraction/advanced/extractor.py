"""
Advanced Entities Extractor - Phase 8 of USDM Expansion

Extracts amendments, geographic scope, and sites from protocol.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    AdvancedData,
    StudyAmendment,
    AmendmentReason,
    GeographicScope,
    Country,
    StudySite,
    AmendmentScope,
)
from .prompts import build_advanced_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class AdvancedExtractionResult:
    """Result of advanced entities extraction."""
    success: bool
    data: Optional[AdvancedData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_advanced_pages(
    pdf_path: str,
    max_pages: int = 30,
) -> List[int]:
    """
    Find pages containing amendment history, geographic scope, or sites.
    """
    import fitz
    
    keywords = [
        r'amendment\s+history',
        r'protocol\s+amendment',
        r'version\s+history',
        r'participating\s+countries',
        r'geographic\s+scope',
        r'study\s+sites?',
        r'investigator\s+sites?',
        r'investigational\s+sites?',
    ]
    
    pattern = re.compile('|'.join(keywords), re.IGNORECASE)
    
    found_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages)
        
        # Always include first few pages (title, amendment info often there)
        found_pages = [0, 1, 2]
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            if pattern.search(text) and page_num not in found_pages:
                found_pages.append(page_num)
        
        doc.close()
        found_pages = sorted(set(found_pages))
        
        logger.info(f"Found {len(found_pages)} advanced entity pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        found_pages = list(range(min(10, max_pages)))
        
    return found_pages


def extract_advanced_entities(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
) -> AdvancedExtractionResult:
    """
    Extract advanced entities from a protocol PDF.
    """
    result = AdvancedExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect pages if not specified
        if pages is None:
            pages = find_advanced_pages(pdf_path)
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Call LLM for extraction
        logger.info("Extracting advanced entities with LLM...")
        prompt = build_advanced_extraction_prompt(protocol_text)
        
        response = call_llm(prompt=prompt, model_name=model_name, json_mode=True)
        
        if 'error' in response:
            result.error = response['error']
            return result
        
        # Parse response
        raw_response = _parse_json_response(response.get('response', ''))
        if not raw_response:
            result.error = "Failed to parse LLM response as JSON"
            return result
        
        result.raw_response = raw_response
        
        # Convert to structured data
        result.data = _build_advanced_data(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {len(result.data.amendments)} amendments, "
                f"{len(result.data.countries)} countries"
            )
        
    except Exception as e:
        logger.error(f"Advanced extraction failed: {e}")
        result.error = str(e)
        
    return result


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _build_advanced_data(raw: Dict[str, Any]) -> AdvancedData:
    """Build AdvancedData from raw extraction results."""
    
    if raw is None:
        return AdvancedData()
    
    amendments = []
    amendment_reasons = []
    countries = []
    sites = []
    geo_scope = None
    
    # Process amendments
    amendments_raw = raw.get('amendments') or []
    for i, amend in enumerate(amendments_raw):
        if not isinstance(amend, dict):
            continue
        
        # Process reasons
        reason_ids = []
        reasons_raw = amend.get('reasons') or []
        for j, reason in enumerate(reasons_raw):
            reason_id = f"ar_{i+1}_{j+1}"
            reason_ids.append(reason_id)
            amendment_reasons.append(AmendmentReason(
                id=reason_id,
                code=reason.upper() if isinstance(reason, str) else "OTHER",
                description=reason if isinstance(reason, str) else str(reason),
            ))
        
        amendments.append(StudyAmendment(
            id=f"amend_{i+1}",
            number=str(amend.get('number', i+1)),
            summary=amend.get('summary'),
            effective_date=amend.get('effectiveDate'),
            previous_version=amend.get('previousVersion'),
            new_version=amend.get('newVersion'),
            reason_ids=reason_ids,
        ))
    
    # Process geographic scope
    geo_data = raw.get('geographicScope') or {}
    if isinstance(geo_data, dict) and geo_data:
        country_ids = []
        
        countries_raw = geo_data.get('countries') or []
        for i, country in enumerate(countries_raw):
            if isinstance(country, dict):
                country_id = f"country_{i+1}"
                country_ids.append(country_id)
                countries.append(Country(
                    id=country_id,
                    name=country.get('name', f'Country {i+1}'),
                    code=country.get('code'),
                ))
            elif isinstance(country, str):
                country_id = f"country_{i+1}"
                country_ids.append(country_id)
                countries.append(Country(
                    id=country_id,
                    name=country,
                ))
        
        geo_scope = GeographicScope(
            id="geo_1",
            name="Study Geographic Scope",
            scope_type=geo_data.get('type') or 'Global',
            country_ids=country_ids,
            regions=geo_data.get('regions') or [],
        )
    
    # Process sites
    sites_raw = raw.get('sites') or []
    for i, site in enumerate(sites_raw):
        if not isinstance(site, dict):
            continue
        
        # Find country ID
        country_id = None
        site_country = site.get('country', '')
        for c in countries:
            if c.name.lower() == site_country.lower():
                country_id = c.id
                break
        
        sites.append(StudySite(
            id=f"site_{i+1}",
            name=site.get('name', f'Site {i+1}'),
            site_number=site.get('number'),
            country_id=country_id,
            city=site.get('city'),
        ))
    
    return AdvancedData(
        amendments=amendments,
        amendment_reasons=amendment_reasons,
        geographic_scope=geo_scope,
        countries=countries,
        sites=sites,
    )


def save_advanced_result(
    result: AdvancedExtractionResult,
    output_path: str,
) -> None:
    """Save advanced extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["advanced"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved advanced entities to {output_path}")
