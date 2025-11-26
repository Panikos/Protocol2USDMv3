"""Simple programmatic API for running the Protocol2USDMv3 pipeline.

This module exposes a small helper for invoking the existing main.py
pipeline orchestration from Python code or tests without launching
Streamlit or exiting the process.
"""

import os
import sys
from typing import Optional

# Ensure repository root is on sys.path when imported from tests
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from main import process_single_pdf, MODEL_NAME


def run_pipeline(pdf_path: str, model: Optional[str] = None, launch_viewer: bool = False) -> str:
    """Run the full SoA extraction pipeline on a single PDF.

    Args:
        pdf_path: Path to the protocol PDF.
        model: Optional model name. If None, uses the default MODEL_NAME
            from main.py (currently "gpt-5.1").
        launch_viewer: Whether to launch the Streamlit viewer. Defaults
            to False for programmatic usage.

    Returns:
        Path to the final reconciled SoA JSON file.

    Raises:
        RuntimeError: If the pipeline fails at any step.
    """
    model_name = model or MODEL_NAME
    return process_single_pdf(pdf_path, model_name, launch_viewer=launch_viewer, exit_on_failure=False)
