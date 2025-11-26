"""
SoA Page Finder - Locate Schedule of Activities pages in protocol PDFs.

This module identifies which pages contain the SoA table(s) using:
1. Text-based heuristics (searching for "Schedule of Activities", table markers)
2. LLM-assisted page identification

Usage:
    from extraction.soa_finder import find_soa_pages
    
    pages = find_soa_pages(pdf_path, model_name="gemini-2.5-pro")
    print(f"SoA found on pages: {pages}")
"""

import os
import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


# Keywords that indicate SoA presence
SOA_KEYWORDS = [
    "schedule of activities",
    "schedule of assessments",
    "study schedule",
    "visit schedule",
    "study procedures",
    "time and events",
]

# Table structure indicators
TABLE_INDICATORS = [
    r'\bvisit\s*\d+',
    r'\bweek\s*[-+]?\d+',
    r'\bday\s*[-+]?\d+',
    r'\bscreening\b',
    r'\bbaseline\b',
    r'\bend\s*of\s*treatment',
    r'\bfollow[-\s]*up\b',
]


@dataclass
class PageScore:
    """Score for how likely a page contains SoA."""
    page_num: int
    keyword_score: float
    table_score: float
    total_score: float
    text_snippet: str


def find_soa_pages_heuristic(pdf_path: str, top_n: int = 5) -> List[int]:
    """
    Find SoA pages using text heuristics.
    
    Args:
        pdf_path: Path to PDF file
        top_n: Number of top-scoring pages to return
        
    Returns:
        List of 0-indexed page numbers likely containing SoA
    """
    doc = fitz.open(pdf_path)
    scores: List[PageScore] = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().lower()
        
        # Score keywords
        keyword_score = 0.0
        for kw in SOA_KEYWORDS:
            if kw in text:
                keyword_score += 2.0
        
        # Score table indicators
        table_score = 0.0
        for pattern in TABLE_INDICATORS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            table_score += len(matches) * 0.5
        
        # Bonus for having multiple column-like structures
        # (rough heuristic based on repeated patterns)
        visit_matches = re.findall(r'visit\s*\d+', text, re.IGNORECASE)
        if len(visit_matches) >= 3:
            table_score += 3.0
        
        total_score = keyword_score + table_score
        
        if total_score > 0:
            # Get a snippet for debugging
            snippet_start = text.find("schedule")
            if snippet_start == -1:
                snippet_start = 0
            snippet = text[snippet_start:snippet_start+100].replace('\n', ' ')
            
            scores.append(PageScore(
                page_num=page_num,
                keyword_score=keyword_score,
                table_score=table_score,
                total_score=total_score,
                text_snippet=snippet,
            ))
    
    doc.close()
    
    # Sort by score descending
    scores.sort(key=lambda x: x.total_score, reverse=True)
    
    # Return top N pages
    return [s.page_num for s in scores[:top_n]]


def find_soa_pages_llm(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    candidate_pages: Optional[List[int]] = None,
) -> List[int]:
    """
    Find SoA pages using LLM analysis.
    
    Args:
        pdf_path: Path to PDF file
        model_name: LLM model to use
        candidate_pages: Optional list of candidate pages to evaluate
                        (if None, evaluates all pages)
        
    Returns:
        List of 0-indexed page numbers containing SoA
    """
    doc = fitz.open(pdf_path)
    
    # If no candidates provided, use heuristics to narrow down
    if candidate_pages is None:
        candidate_pages = find_soa_pages_heuristic(pdf_path, top_n=10)
        if not candidate_pages:
            candidate_pages = list(range(min(30, len(doc))))  # Check first 30 pages
    
    # Extract text from candidate pages
    page_texts = []
    for page_num in candidate_pages:
        if 0 <= page_num < len(doc):
            text = doc[page_num].get_text()[:2000]  # Limit text per page
            page_texts.append(f"PAGE {page_num}:\n{text}")
    
    doc.close()
    
    if not page_texts:
        return []
    
    # Build prompt
    prompt = """Analyze these protocol pages and identify which ones contain a Schedule of Activities (SoA) table.

An SoA table typically has:
- Column headers with visit names (Visit 1, Visit 2, etc.) or time points (Week 0, Day 1, etc.)
- Row headers with procedure/activity names
- Checkmarks or X marks indicating which activities occur at which visits

PAGES TO ANALYZE:
{pages}

Return a JSON object with:
{{
  "soa_pages": [list of page numbers that contain SoA tables],
  "confidence": "high" or "medium" or "low",
  "notes": "brief explanation"
}}

Only include pages that clearly contain SoA table content.""".format(
        pages="\n\n---\n\n".join(page_texts)
    )
    
    try:
        client = get_llm_client(model_name)
        response = client.generate(
            messages=[{"role": "user", "content": prompt}],
            config=LLMConfig(temperature=0.0, json_mode=True),
        )
        
        data = parse_llm_json(response.content, fallback={})
        pages = data.get("soa_pages", [])
        
        logger.info(f"LLM identified SoA on pages: {pages} (confidence: {data.get('confidence', 'unknown')})")
        
        return [int(p) for p in pages if isinstance(p, (int, float))]
        
    except Exception as e:
        logger.warning(f"LLM page finding failed: {e}. Falling back to heuristics.")
        return candidate_pages[:5]  # Return top 5 heuristic candidates


def find_soa_pages(
    pdf_path: str,
    model_name: Optional[str] = None,
    use_llm: bool = True,
) -> List[int]:
    """
    Find pages containing Schedule of Activities table.
    
    This is the main entry point for SoA page detection.
    
    Args:
        pdf_path: Path to protocol PDF
        model_name: LLM model for enhanced detection (optional)
        use_llm: Whether to use LLM-assisted detection
        
    Returns:
        List of 0-indexed page numbers containing SoA
        
    Example:
        >>> pages = find_soa_pages("protocol.pdf")
        >>> print(f"Found SoA on pages: {pages}")
    """
    logger.info(f"Finding SoA pages in: {pdf_path}")
    
    # First pass: heuristic detection
    heuristic_pages = find_soa_pages_heuristic(pdf_path, top_n=10)
    logger.info(f"Heuristic candidates: {heuristic_pages}")
    
    if not use_llm or not model_name:
        return heuristic_pages[:5]
    
    # Second pass: LLM refinement
    llm_pages = find_soa_pages_llm(pdf_path, model_name, heuristic_pages)
    
    if llm_pages:
        return llm_pages
    
    # Fallback to heuristics if LLM fails
    return heuristic_pages[:5]


def extract_soa_text(pdf_path: str, page_numbers: List[int]) -> str:
    """
    Extract text from specified SoA pages.
    
    Args:
        pdf_path: Path to PDF file
        page_numbers: List of 0-indexed page numbers
        
    Returns:
        Combined text from specified pages
    """
    doc = fitz.open(pdf_path)
    texts = []
    
    for page_num in page_numbers:
        if 0 <= page_num < len(doc):
            texts.append(doc[page_num].get_text())
    
    doc.close()
    return "\n\n---PAGE BREAK---\n\n".join(texts)


def extract_soa_images(
    pdf_path: str,
    page_numbers: List[int],
    output_dir: str,
    dpi: int = 150,
) -> List[str]:
    """
    Extract SoA pages as images.
    
    Args:
        pdf_path: Path to PDF file
        page_numbers: List of 0-indexed page numbers
        output_dir: Directory to save images
        dpi: Resolution for image extraction
        
    Returns:
        List of paths to extracted images
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths = []
    
    for page_num in page_numbers:
        if 0 <= page_num < len(doc):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            img_path = os.path.join(output_dir, f"soa_page_{page_num:03d}.png")
            pix.save(img_path)
            image_paths.append(img_path)
            logger.debug(f"Saved page {page_num} to {img_path}")
    
    doc.close()
    return image_paths
