"""
Quick verification script for prompt migration.
Checks that all migrated templates load correctly.
"""

import sys
from pathlib import Path

# Ensure UTF-8 output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def check_template(name, path):
    """Check if a YAML template exists and can be loaded."""
    try:
        from prompt_templates import PromptTemplate
        
        template_path = Path(path)
        if not template_path.exists():
            print(f"❌ {name}: Template file not found at {path}")
            return False
        
        template = PromptTemplate.load(template_path.stem, template_path.parent)
        version = template.metadata.version
        print(f"✅ {name}: v{version} loaded successfully")
        return True
    except Exception as e:
        print(f"❌ {name}: Failed to load - {e}")
        return False

def main():
    print("\n" + "=" * 70)
    print("PROMPT MIGRATION VERIFICATION")
    print("=" * 70 + "\n")
    
    templates = [
        ("Reconciliation Prompt", "prompts/soa_reconciliation.yaml"),
        ("Vision Extraction Prompt", "prompts/vision_soa_extraction.yaml"),
        ("Find SoA Pages Prompt", "prompts/find_soa_pages.yaml"),
        ("Text Extraction Prompt", "prompts/soa_extraction.yaml"),
    ]
    
    results = []
    for name, path in templates:
        results.append(check_template(name, path))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"✅ Passed: {passed}/{total} ({percentage:.0f}%)")
    
    if passed == total:
        print("\n🎉 All migrated prompts verified successfully!")
        print("=" * 70)
        return 0
    else:
        print(f"\n⚠️  {total - passed} template(s) failed verification")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
