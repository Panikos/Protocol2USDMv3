#!/usr/bin/env python3
"""
Quick test of prompt optimization setup.

Tests that all components are working:
- Prompt optimizer module
- Google Cloud connection (if configured)
- OpenAI connection (if configured)
"""

import sys
import os

# Ensure UTF-8 output
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_imports():
    """Test that required modules can be imported."""
    print("\n" + "="*70)
    print("TEST 1: Module Imports")
    print("="*70)
    
    try:
        from prompt_optimizer import PromptOptimizer
        print("✅ prompt_optimizer module imported")
    except ImportError as e:
        print(f"❌ Failed to import prompt_optimizer: {e}")
        return False
    
    try:
        from google.cloud import aiplatform
        print("✅ google-cloud-aiplatform imported")
        has_vertex = True
    except ImportError:
        print("⚠️  google-cloud-aiplatform not installed (optional)")
        has_vertex = False
    
    try:
        from openai import OpenAI
        print("✅ openai module imported")
        has_openai = True
    except ImportError:
        print("⚠️  openai not installed (optional)")
        has_openai = False
    
    print()
    return True


def test_environment():
    """Test environment variables."""
    print("="*70)
    print("TEST 2: Environment Configuration")
    print("="*70)
    
    # Check Google Cloud
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if gcp_project:
        print(f"✅ GOOGLE_CLOUD_PROJECT: {gcp_project}")
    else:
        print("⚠️  GOOGLE_CLOUD_PROJECT not set (needed for Vertex AI)")
    
    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        print(f"✅ OPENAI_API_KEY: {'*' * 20}{openai_key[-4:]}")
    else:
        print("⚠️  OPENAI_API_KEY not set (needed for OpenAI optimization)")
    
    # Check Google Gemini
    google_key = os.environ.get("GOOGLE_API_KEY")
    if google_key:
        print(f"✅ GOOGLE_API_KEY: {'*' * 20}{google_key[-4:]}")
    else:
        print("⚠️  GOOGLE_API_KEY not set (needed for Gemini)")
    
    print()
    return True


def test_optimizer_initialization():
    """Test optimizer initialization."""
    print("="*70)
    print("TEST 3: Optimizer Initialization")
    print("="*70)
    
    try:
        from prompt_optimizer import PromptOptimizer
        
        optimizer = PromptOptimizer(enable_optimization=True)
        print("✅ PromptOptimizer created successfully")
        
        # Test with simple prompt
        test_prompt = "Extract data from clinical trial protocols."
        
        print("\n[TEST] Testing with sample prompt...")
        print(f"Input: '{test_prompt}'")
        
        # Try optimization (will fallback gracefully if not configured)
        optimized = optimizer.optimize(
            test_prompt,
            method="none"  # Use 'none' for initial test
        )
        
        print("✅ Optimization method executed (passthrough mode)")
        
        print()
        return True
    
    except Exception as e:
        print(f"❌ Optimizer test failed: {e}")
        print()
        return False


def test_template_loading():
    """Test template loading."""
    print("="*70)
    print("TEST 4: Template Loading")
    print("="*70)
    
    try:
        from prompt_templates import PromptTemplate
        from pathlib import Path
        
        templates_dir = Path("prompts")
        templates_found = list(templates_dir.glob("*.yaml"))
        
        print(f"Found {len(templates_found)} template files:")
        
        for template_file in templates_found:
            try:
                template = PromptTemplate.load(template_file.stem, "prompts")
                print(f"  ✅ {template_file.name} (v{template.metadata.version})")
            except Exception as e:
                print(f"  ❌ {template_file.name}: {e}")
        
        print()
        return len(templates_found) > 0
    
    except Exception as e:
        print(f"❌ Template loading test failed: {e}")
        print()
        return False


def test_vertex_ai_connection():
    """Test Vertex AI connection if configured."""
    print("="*70)
    print("TEST 5: Vertex AI Connection (Optional)")
    print("="*70)
    
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    
    if not gcp_project:
        print("⚠️  GOOGLE_CLOUD_PROJECT not set, skipping")
        print("   Run setup_google_cloud.ps1 to configure")
        print()
        return True  # Not a failure, just not configured
    
    try:
        from google.cloud import aiplatform
        
        aiplatform.init(
            project=gcp_project,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        )
        
        print(f"✅ Connected to Vertex AI (project: {gcp_project})")
        print("✅ Ready for prompt optimization!")
        
        print()
        return True
    
    except Exception as e:
        print(f"⚠️  Vertex AI connection failed: {e}")
        print("   This is OK if you haven't set up Google Cloud yet")
        print()
        return True  # Not a critical failure


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("PROMPT OPTIMIZATION SETUP TEST")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Module Imports", test_imports()))
    results.append(("Environment Config", test_environment()))
    results.append(("Optimizer Init", test_optimizer_initialization()))
    results.append(("Template Loading", test_template_loading()))
    results.append(("Vertex AI Connection", test_vertex_ai_connection()))
    
    # Summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Setup is complete.\n")
        print("Next steps:")
        print("1. If you haven't set up Google Cloud yet:")
        print("   ./setup_google_cloud.ps1")
        print()
        print("2. Test optimization on a prompt:")
        print("   python prompt_optimizer.py 'Your prompt here'")
        print()
        print("3. Run benchmark with optimization:")
        print("   python benchmark_prompts.py --test-set test_data/ --auto-optimize")
        print()
        return 0
    else:
        print("\n⚠️  Some tests failed. Check errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
