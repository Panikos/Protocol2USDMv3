#!/usr/bin/env python3
"""
Protocol2USDM v2 - Simplified Pipeline

This is a cleaner, modular implementation of the SoA extraction pipeline.
It follows the original architectural intent:
- Vision extracts STRUCTURE (headers, groups)
- Text extracts DATA (activities, ticks) using structure as anchor
- Vision validates text extraction
- Output is schema-compliant USDM JSON

Usage:
    python main_v2.py protocol.pdf [--model gemini-2.5-pro] [--no-validate]
    
Compared to main.py, this version:
- Uses modular extraction components from extraction/
- Has cleaner separation of concerns
- Produces simpler, more debuggable output
- Follows the original design intent
"""

import argparse
import logging
import os
import sys
import json
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Import from new modular structure
from extraction import run_from_files, PipelineConfig, PipelineResult
from extraction.pipeline import enrich_terminology, validate_schema, run_cdisc_conformance
from core.constants import DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(
        description="Extract Schedule of Activities from clinical protocol PDF (v2 - Simplified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main_v2.py protocol.pdf
    python main_v2.py protocol.pdf --model gemini-2.5-pro
    python main_v2.py protocol.pdf --no-validate
    python main_v2.py protocol.pdf --pages 52,53,54
        """
    )
    
    parser.add_argument(
        "pdf_path",
        help="Path to the clinical protocol PDF"
    )
    
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"LLM model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: output/<protocol_name>)"
    )
    
    parser.add_argument(
        "--pages", "-p",
        help="Comma-separated SoA page numbers (0-indexed). If not provided, will analyze all pages."
    )
    
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip vision validation step"
    )
    
    parser.add_argument(
        "--keep-hallucinations",
        action="store_true",
        help="Don't remove probable hallucinations from output"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for removing hallucinations (default: 0.7)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--view",
        action="store_true",
        help="Launch Streamlit viewer after extraction"
    )
    
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Don't launch Streamlit viewer (default behavior)"
    )
    
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich activities with NCI terminology codes (Step 7)"
    )
    
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate output against USDM schema (Step 8)"
    )
    
    parser.add_argument(
        "--conformance",
        action="store_true",
        help="Run CDISC CORE conformance rules (Step 9)"
    )
    
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline including enrichment, validation, and conformance (Steps 7-9)"
    )
    
    args = parser.parse_args()
    
    # Validate PDF path
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    # Set up output directory
    protocol_name = Path(args.pdf_path).stem
    output_dir = args.output_dir or os.path.join("output", protocol_name)
    
    # Parse page numbers if provided
    soa_pages = None
    if args.pages:
        try:
            soa_pages = [int(p.strip()) for p in args.pages.split(",")]
            logger.info(f"Using specified SoA pages: {soa_pages}")
        except ValueError:
            logger.error(f"Invalid page numbers: {args.pages}")
            sys.exit(1)
    
    # Configure pipeline
    config = PipelineConfig(
        model_name=args.model,
        validate_with_vision=not args.no_validate,
        remove_hallucinations=not args.keep_hallucinations,
        hallucination_confidence_threshold=args.confidence_threshold,
        save_intermediate=True,
    )
    
    # Print configuration
    logger.info("="*60)
    logger.info("Protocol2USDM v2 - Simplified Pipeline")
    logger.info("="*60)
    logger.info(f"Input PDF: {args.pdf_path}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Vision Validation: {'Enabled' if config.validate_with_vision else 'Disabled'}")
    logger.info("="*60)
    
    # Run pipeline
    try:
        result = run_from_files(
            pdf_path=args.pdf_path,
            output_dir=output_dir,
            soa_pages=soa_pages,
            config=config,
        )
        
        # Print results
        print()
        logger.info("="*60)
        if result.success:
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        else:
            logger.error("PIPELINE COMPLETED WITH ERRORS")
        logger.info("="*60)
        
        logger.info(f"Activities extracted: {result.activities_count}")
        logger.info(f"Timepoints: {result.timepoints_count}")
        logger.info(f"Ticks: {result.ticks_count}")
        
        if result.validated:
            logger.info(f"Hallucinations removed: {result.hallucinations_removed}")
            logger.info(f"Possibly missed ticks: {result.missed_ticks_found}")
        
        if result.output_path:
            logger.info(f"Output: {result.output_path}")
        if result.provenance_path:
            logger.info(f"Provenance: {result.provenance_path}")
        
        if result.errors:
            logger.warning("Errors encountered:")
            for err in result.errors:
                logger.warning(f"  - {err}")
        
        logger.info("="*60)
        
        # Run post-processing steps if requested
        if result.success and result.output_path:
            run_enrich = args.enrich or args.full
            run_validate = args.validate_schema or args.full
            run_conform = args.conformance or args.full
            
            if run_enrich:
                logger.info("\n--- Step 7: Terminology Enrichment ---")
                enrich_result = enrich_terminology(result.output_path)
                logger.info(f"Enriched {enrich_result.get('enriched', 0)}/{enrich_result.get('total', 0)} activities")
            
            if run_validate:
                logger.info("\n--- Step 8: Schema Validation ---")
                schema_result = validate_schema(result.output_path)
                if schema_result.get('valid'):
                    logger.info("✓ Schema validation PASSED")
                else:
                    logger.warning(f"Schema validation found {len(schema_result.get('issues', []))} issues")
                # Save result
                schema_path = os.path.join(output_dir, "step8_schema_validation.json")
                with open(schema_path, 'w') as f:
                    json.dump(schema_result, f, indent=2)
            
            if run_conform:
                logger.info("\n--- Step 9: CDISC Conformance ---")
                conform_result = run_cdisc_conformance(result.output_path, output_dir)
                if conform_result.get('success'):
                    logger.info(f"✓ Conformance report: {conform_result.get('output')}")
                elif conform_result.get('error'):
                    logger.warning(f"Conformance check skipped: {conform_result.get('error')}")
        
        # Launch Streamlit viewer if requested
        if args.view and result.success and result.output_path:
            launch_viewer(result.output_path)
        
        # Exit with appropriate code
        sys.exit(0 if result.success else 1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def launch_viewer(soa_path: str):
    """Launch the Streamlit SoA viewer."""
    import subprocess
    
    viewer_script = os.path.join(os.path.dirname(__file__), "soa_streamlit_viewer.py")
    
    if not os.path.exists(viewer_script):
        logger.warning(f"Viewer not found: {viewer_script}")
        return
    
    logger.info(f"Launching SoA viewer...")
    
    try:
        subprocess.Popen(
            ["streamlit", "run", viewer_script, "--", soa_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning(f"Could not launch viewer: {e}")
        logger.info(f"Run manually: streamlit run soa_viewer.py -- {soa_path}")


if __name__ == "__main__":
    main()
