#!/usr/bin/env python3
"""
Batch Optimize All Prompts

Automatically optimizes all prompt templates using Google Vertex AI.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure UTF-8
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def optimize_all_templates(method="google-zeroshot", dry_run=False):
    """
    Optimize all YAML templates in the prompts directory.
    
    Args:
        method: Optimization method to use
        dry_run: If True, show what would be done without actually doing it
    """
    try:
        from prompt_optimizer import PromptOptimizer
        from prompt_templates import PromptTemplate
        import yaml
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return 1
    
    print("\n" + "="*70)
    print("BATCH PROMPT OPTIMIZATION")
    print("="*70)
    print(f"Method: {method}")
    print(f"Dry run: {dry_run}")
    print("="*70 + "\n")
    
    # Initialize optimizer
    optimizer = PromptOptimizer(enable_optimization=not dry_run)
    
    # Find all template files
    templates_dir = Path("prompts")
    template_files = sorted(templates_dir.glob("*.yaml"))
    
    # Filter out already optimized files
    template_files = [f for f in template_files if not f.stem.endswith("_optimized")]
    
    if not template_files:
        print("❌ No template files found in prompts/")
        return 1
    
    print(f"Found {len(template_files)} templates to optimize:\n")
    for f in template_files:
        print(f"  • {f.name}")
    print()
    
    results = []
    
    for i, template_file in enumerate(template_files, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(template_files)}] Optimizing: {template_file.name}")
        print('='*70)
        
        try:
            # Load template
            template = PromptTemplate.load(template_file.stem, str(templates_dir))
            
            print(f"Current version: v{template.metadata.version}")
            print(f"System prompt length: {len(template.system_prompt)} chars")
            
            if dry_run:
                print("🔍 DRY RUN - Would optimize this prompt")
                results.append({
                    "name": template_file.name,
                    "status": "dry-run",
                    "original_length": len(template.system_prompt)
                })
                continue
            
            # Optimize system prompt
            print(f"\n[OPTIMIZE] Using {method}...")
            optimized_system = optimizer.optimize(
                template.system_prompt,
                method=method,
                target_model="gemini-2.5-pro"
            )
            
            # Check if optimization changed anything
            if optimized_system == template.system_prompt:
                print("ℹ️  No changes from optimization (already optimal)")
                results.append({
                    "name": template_file.name,
                    "status": "no-change",
                    "original_length": len(template.system_prompt)
                })
                continue
            
            # Create optimized version
            output_path = templates_dir / f"{template_file.stem}_optimized.yaml"
            
            # Load original YAML to preserve structure
            with open(template_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Update system prompt
            data['system_prompt'] = optimized_system
            
            # Update metadata
            old_version = str(data['metadata']['version'])  # Convert to string in case it's a float
            version_parts = old_version.split('.')
            version_parts[-1] = str(int(float(version_parts[-1])) + 1)
            new_version = '.'.join(version_parts)
            
            data['metadata']['version'] = new_version
            data['metadata']['description'] += f"\nAuto-optimized using {method}."
            
            # Add changelog entry
            if 'changelog' not in data['metadata']:
                data['metadata']['changelog'] = []
            
            data['metadata']['changelog'].insert(0, {
                'version': new_version,
                'date': '2025-10-06',
                'changes': f'Auto-optimized using {method}'
            })
            
            # Save optimized version
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=120)
            
            print(f"\n✅ Optimized successfully!")
            print(f"   Original: {len(template.system_prompt)} chars")
            print(f"   Optimized: {len(optimized_system)} chars")
            print(f"   Change: {len(optimized_system) - len(template.system_prompt):+d} chars")
            print(f"   Version: {old_version} → {new_version}")
            print(f"   Saved to: {output_path.name}")
            
            results.append({
                "name": template_file.name,
                "status": "success",
                "original_length": len(template.system_prompt),
                "optimized_length": len(optimized_system),
                "change": len(optimized_system) - len(template.system_prompt),
                "old_version": old_version,
                "new_version": new_version,
                "output_file": output_path.name
            })
            
        except Exception as e:
            print(f"\n❌ Error optimizing {template_file.name}: {e}")
            results.append({
                "name": template_file.name,
                "status": "error",
                "error": str(e)
            })
    
    # Summary
    print("\n" + "="*70)
    print("OPTIMIZATION SUMMARY")
    print("="*70 + "\n")
    
    success_count = sum(1 for r in results if r["status"] == "success")
    no_change_count = sum(1 for r in results if r["status"] == "no-change")
    error_count = sum(1 for r in results if r["status"] == "error")
    dry_run_count = sum(1 for r in results if r["status"] == "dry-run")
    
    print(f"Total templates: {len(results)}")
    print(f"✅ Successfully optimized: {success_count}")
    print(f"ℹ️  No changes needed: {no_change_count}")
    print(f"❌ Errors: {error_count}")
    if dry_run:
        print(f"🔍 Dry run: {dry_run_count}")
    
    if success_count > 0:
        print(f"\n📁 Optimized files saved in: prompts/")
        print("\nOptimized templates:")
        for r in results:
            if r["status"] == "success":
                print(f"  • {r['output_file']} (v{r['new_version']})")
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70 + "\n")
    
    if success_count > 0:
        print("1. Review the optimized prompts:")
        print("   Compare *_optimized.yaml files with originals")
        print()
        print("2. Test the optimized prompts:")
        print("   python benchmark_prompts.py --test-set test_data/")
        print()
        print("3. If satisfied, replace original templates:")
        print("   # Backup originals first!")
        print("   # Then rename optimized versions")
        print()
    else:
        print("No prompts were optimized. Possible reasons:")
        print("• Prompts are already optimal")
        print("• Optimization service unavailable")
        print("• Check Google Cloud configuration")
        print()
    
    return 0 if error_count == 0 else 1


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch optimize all prompt templates")
    parser.add_argument("--method", default="google-zeroshot",
                       choices=["google-zeroshot", "google-datadriven", "openai-multiagent", "none"],
                       help="Optimization method to use")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without actually doing it")
    
    args = parser.parse_args()
    
    return optimize_all_templates(method=args.method, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
