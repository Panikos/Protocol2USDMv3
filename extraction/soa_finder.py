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
    prompt = """Analyze these protocol pages and identify ALL pages that contain a Schedule of Activities (SoA) table.

An SoA table typically has:
- Column headers with visit names (Visit 1, Visit 2, etc.) or time points (Day -7, Day 1, Week 4, etc.)
- Row headers with procedure/activity names (e.g., "Informed consent", "Physical examination", "Blood sampling")
- A grid with checkmarks (X, ✓) indicating which activities occur at which visits

**CRITICAL: SoA tables span MULTIPLE PAGES (typically 2-4 pages). You MUST identify ALL pages.**

How to identify SoA CONTINUATION pages (pages 2, 3, etc. of the table):
- Same column structure as the first page (Days, Visits, etc.)
- Activity/procedure names in the left column
- Grid of X marks continuing from previous page
- May NOT have "Schedule of Activities" title - just table content
- Look for: "Safety Assessments", "Laboratory", "PK/PD", "Balance assessments", etc.

PAGES TO ANALYZE:
{pages}

Return a JSON object with:
{{
  "soa_pages": [list of ALL page numbers containing SoA table content],
  "confidence": "high" or "medium" or "low",
  "notes": "brief explanation including how many pages the table spans"
}}

**Do NOT miss continuation pages. If page N has the SoA title, check if pages N+1, N+2 continue the same table.**""".format(
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
    
    # Find pages with SoA title (these are anchor pages)
    title_pages = _find_soa_title_pages(pdf_path)
    logger.info(f"Title pages: {title_pages}")
    
    # Combine heuristic and title pages
    all_candidates = list(set(heuristic_pages + title_pages))
    
    # Pre-expand candidates to include ±2 adjacent pages BEFORE LLM analysis
    # This ensures the LLM sees potential continuation pages
    expanded_candidates = _pre_expand_candidates(all_candidates, pdf_path)
    logger.info(f"Expanded candidates for LLM: {sorted(expanded_candidates)}")
    
    if not use_llm or not model_name:
        final_pages = _expand_adjacent_pages(expanded_candidates, pdf_path)
        return sorted(final_pages)[:10]
    
    # Second pass: LLM refinement (now sees adjacent pages)
    llm_pages = find_soa_pages_llm(pdf_path, model_name, expanded_candidates)
    
    if llm_pages:
        # LLM already saw pre-expanded candidates (±2 pages), so trust its selection
        # No additional expansion needed - LLM has already identified all SoA pages
        return sorted(llm_pages)
    
    # Fallback to heuristics if LLM fails
    final_pages = _expand_adjacent_pages(all_candidates, pdf_path)
    return sorted(final_pages)[:10]


def _pre_expand_candidates(pages: List[int], pdf_path: str, radius: int = 2) -> List[int]:
    """
    Pre-expand candidate pages by ±radius before LLM analysis.
    
    This ensures the LLM sees potential continuation pages that
    weren't caught by heuristics.
    
    Args:
        pages: Initial candidate pages
        pdf_path: Path to PDF
        radius: Number of pages to add on each side (default ±2)
    """
    if not pages:
        return pages
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    
    expanded = set(pages)
    for page in pages:
        for offset in range(-radius, radius + 1):
            new_page = page + offset
            if 0 <= new_page < total_pages:
                expanded.add(new_page)
    
    return list(expanded)


def _find_soa_title_pages(pdf_path: str) -> List[int]:
    """
    Find pages that contain actual SoA table (not just mentions of it).
    
    Looks for:
    - "Table X: Schedule of Activities" pattern (actual table title)
    - Combined presence of title AND table structure (column headers like Day, Visit)
    """
    doc = fitz.open(pdf_path)
    title_pages = []
    
    # Patterns for actual table titles (not TOC or references)
    # Requires "Table X:" format which indicates actual table caption
    table_title_patterns = [
        r'table\s+\d+[:\.]?\s*schedule\s+of\s+(activities|assessments)',  # "Table 1: Schedule of..."
    ]
    
    # Patterns for table structure (columns/headers)
    structure_patterns = [
        r'\bday\s*[-+]?\d+',
        r'\bweek\s*[-+]?\d+', 
        r'\bvisit\s*\d+',
        r'\bscreening\b.*\btreatment\b',  # Multiple epochs on same page
        r'\binpatient\b',
        r'\boutpatient\b',
    ]
    
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().lower()
        
        # Method 1: Explicit table title pattern
        for pattern in table_title_patterns:
            if re.search(pattern, text):
                title_pages.append(page_num)
                logger.debug(f"Page {page_num + 1}: Found table title pattern")
                break
        else:
            # Method 2: "Schedule of Activities" + significant table structure
            if re.search(r'schedule\s+of\s+(activities|assessments)', text):
                structure_count = sum(
                    1 for p in structure_patterns if re.search(p, text)
                )
                # Need both the title AND substantial table structure
                if structure_count >= 3:
                    title_pages.append(page_num)
                    logger.debug(f"Page {page_num + 1}: Found title + {structure_count} structure indicators")
    
    doc.close()
    return title_pages


def _expand_conservative(pages: List[int], pdf_path: str, model_name: str = None) -> List[int]:
    """
    Conservative page expansion with vision validation.
    
    For each candidate expansion page (±1 from detected range), uses vision
    to verify it actually contains SoA table content before including it.
    
    Args:
        pages: LLM-identified SoA pages
        pdf_path: Path to PDF
        model_name: LLM model for vision validation (optional)
    """
    if not pages:
        return pages
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    expanded = set(pages)
    sorted_pages = sorted(pages)
    
    # Fill gaps between detected pages (these are definitely part of SoA)
    if len(sorted_pages) >= 2:
        for i in range(len(sorted_pages) - 1):
            start, end = sorted_pages[i], sorted_pages[i + 1]
            for gap_page in range(start + 1, end):
                expanded.add(gap_page)
    
    # Candidate pages to validate: ±1 from detected range
    min_page = min(sorted_pages)
    max_page = max(sorted_pages)
    
    candidates = []
    if min_page - 1 >= 0:
        candidates.append(min_page - 1)
    if max_page + 1 < total_pages:
        candidates.append(max_page + 1)
    
    # If no model provided, just add candidates without validation
    if not model_name or not candidates:
        for c in candidates:
            expanded.add(c)
        doc.close()
        return list(expanded)
    
    # Validate each candidate with vision
    import tempfile
    import os
    
    for page_num in candidates:
        # Render page to image
        page = doc[page_num]
        pix = page.get_pixmap(dpi=100)  # Lower DPI for quick check
        
        # Create temp file path without keeping handle open
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.png')
        os.close(tmp_fd)  # Close the file descriptor immediately
        
        try:
            pix.save(tmp_path)
            is_soa = _validate_page_is_soa(tmp_path, model_name)
            if is_soa:
                expanded.add(page_num)
                logger.info(f"Vision confirmed page {page_num + 1} is part of SoA")
            else:
                logger.info(f"Vision rejected page {page_num + 1} - not SoA table")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # Ignore cleanup errors on Windows
    
    doc.close()
    return list(expanded)


def _validate_page_is_soa(image_path: str, model_name: str) -> bool:
    """
    Use vision to check if a page contains SoA table content.
    
    Returns True if the page appears to be part of a Schedule of Activities table.
    """
    from core.llm_client import get_llm_client, LLMConfig
    from core.json_utils import parse_llm_json
    import base64
    
    # Encode image
    with open(image_path, 'rb') as f:
        img_data = base64.standard_b64encode(f.read()).decode('utf-8')
    
    prompt = """Look at this page image. Is it part of a Schedule of Activities (SoA) table?

A SoA table typically has:
- Column headers with visit names (Day 1, Week 2, Visit 3, etc.)
- Row labels with activity/procedure names
- A grid of tick marks (X, ✓) or empty cells

Answer in JSON format:
{"is_soa_table": true/false, "confidence": "high/medium/low", "reason": "brief explanation"}"""

    client = get_llm_client(model_name)
    
    # Build vision message
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}}
        ]}
    ]
    
    config = LLMConfig(temperature=0.0, json_mode=True, max_tokens=200)
    
    try:
        response = client.generate(messages, config)
        result = parse_llm_json(response.content, fallback={})
        return result.get('is_soa_table', False) and result.get('confidence') in ['high', 'medium']
    except Exception as e:
        logger.warning(f"Vision validation failed: {e}")
        return True  # Default to including page if validation fails


def _expand_adjacent_pages(pages: List[int], pdf_path: str) -> List[int]:
    """
    Expand page list to include adjacent pages and fill gaps.
    
    SoA tables often span multiple pages, so if we find page N,
    we should also check page N+1 (and potentially N-1) for table continuation.
    Also fills in any gaps between detected pages (e.g., if 13 and 15 are detected, include 14).
    
    NOTE: This is the aggressive expansion used for heuristic-only detection.
    When LLM provides high-confidence pages, use _expand_conservative instead.
    """
    if not pages:
        return pages
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    expanded = set(pages)
    
    # Step 1: Fill in gaps between detected pages
    # If pages 13 and 15 are detected, page 14 is definitely part of the table
    if len(pages) >= 2:
        sorted_pages = sorted(pages)
        for i in range(len(sorted_pages) - 1):
            start, end = sorted_pages[i], sorted_pages[i + 1]
            # Fill gaps of up to 2 pages (handles single-page gaps like 13->15)
            if end - start <= 3:
                for gap_page in range(start + 1, end):
                    if gap_page not in expanded:
                        expanded.add(gap_page)
                        logger.info(f"Filled gap: added page {gap_page + 1} (1-indexed) between pages {start + 1} and {end + 1}")
    
    # Step 2: Iteratively expand to adjacent pages until no more additions
    prev_size = 0
    while len(expanded) > prev_size:
        prev_size = len(expanded)
        new_pages = set()
        
        for page_num in list(expanded):
            # Check next page (table continuation)
            if page_num + 1 < total_pages and page_num + 1 not in expanded:
                next_text = doc[page_num + 1].get_text().lower()
                # Check if next page looks like a table continuation
                has_table_content = any(
                    re.search(pattern, next_text)
                    for pattern in [r'\bday\s*[-+]?\d+', r'\bweek\s*[-+]?\d+', r'\bvisit\s*\d+', r'screening', r'baseline', r'\bx\b']
                )
                if has_table_content:
                    new_pages.add(page_num + 1)
                    logger.debug(f"Added adjacent page {page_num + 2} (1-indexed) - continuation of page {page_num + 1}")
            
            # Check previous page (table may start earlier)
            if page_num - 1 >= 0 and page_num - 1 not in expanded:
                prev_text = doc[page_num - 1].get_text().lower()
                # More permissive check - any table content or SoA title
                has_table_content = (
                    re.search(r'schedule\s+of\s+(activities|assessments)', prev_text) or
                    any(re.search(pattern, prev_text) for pattern in [r'\bday\s*[-+]?\d+', r'\bweek\s*[-+]?\d+', r'\bvisit\s*\d+'])
                )
                if has_table_content:
                    new_pages.add(page_num - 1)
                    logger.debug(f"Added page {page_num} (1-indexed) - precedes page {page_num + 1}")
        
        expanded.update(new_pages)
    
    doc.close()
    return list(expanded)


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
            img_path = os.path.join(output_dir, f"soa_page_{page_num + 1:03d}.png")  # 1-indexed for human readability
            pix.save(img_path)
            image_paths.append(img_path)
            logger.debug(f"Saved page {page_num} to {img_path}")
    
    doc.close()
    return image_paths
