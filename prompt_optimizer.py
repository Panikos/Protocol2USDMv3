#!/usr/bin/env python3
"""
Prompt Optimization Wrapper

Provides unified interface to prompt optimization APIs from:
- Google Vertex AI (Zero-shot and Data-driven)
- OpenAI Multi-Agent System
- Manual optimization helpers

Usage:
    optimizer = PromptOptimizer()
    optimized = optimizer.optimize(prompt_text, method="google-zeroshot")
"""

import os
import sys
from typing import Dict, Optional, Literal
from pathlib import Path

# Ensure UTF-8 output
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class PromptOptimizer:
    """Unified interface for prompt optimization APIs."""
    
    def __init__(self, enable_optimization: bool = True):
        """
        Initialize optimizer.
        
        Args:
            enable_optimization: If False, acts as pass-through
        """
        self.enable_optimization = enable_optimization
        self._vertex_ai_initialized = False
        self._openai_initialized = False
    
    def _init_vertex_ai(self):
        """Initialize Google Vertex AI (lazy loading)."""
        if self._vertex_ai_initialized:
            return True
        
        try:
            from google.cloud import aiplatform
            
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                print("[WARNING] GOOGLE_CLOUD_PROJECT not set. Vertex AI unavailable.")
                return False
            
            # Initialize
            aiplatform.init(
                project=project_id,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            )
            
            self._vertex_ai_initialized = True
            print(f"[INFO] Vertex AI initialized (project: {project_id})")
            return True
        
        except ImportError:
            print("[WARNING] google-cloud-aiplatform not installed. Run: pip install google-cloud-aiplatform")
            return False
        except Exception as e:
            print(f"[WARNING] Vertex AI initialization failed: {e}")
            return False
    
    def _init_openai(self):
        """Initialize OpenAI (lazy loading)."""
        if self._openai_initialized:
            return True
        
        try:
            from openai import OpenAI
            
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("[WARNING] OPENAI_API_KEY not set. OpenAI unavailable.")
                return False
            
            self._openai_client = OpenAI(api_key=api_key)
            self._openai_initialized = True
            print("[INFO] OpenAI initialized")
            return True
        
        except ImportError:
            print("[WARNING] openai package not installed.")
            return False
        except Exception as e:
            print(f"[WARNING] OpenAI initialization failed: {e}")
            return False
    
    def optimize(
        self,
        prompt_text: str,
        method: Literal["google-zeroshot", "google-datadriven", "openai-multiagent", "none"] = "google-zeroshot",
        target_model: str = "gemini-2.5-pro",
        evaluation_data: Optional[Dict] = None
    ) -> str:
        """
        Optimize a prompt using specified method.
        
        Args:
            prompt_text: Original prompt text
            method: Optimization method to use
            target_model: Target model for optimization
            evaluation_data: Optional evaluation data for data-driven optimization
        
        Returns:
            Optimized prompt text
        """
        if not self.enable_optimization or method == "none":
            return prompt_text
        
        print(f"[OPTIMIZE] Using method: {method}")
        
        if method == "google-zeroshot":
            return self._optimize_google_zeroshot(prompt_text, target_model)
        elif method == "google-datadriven":
            return self._optimize_google_datadriven(prompt_text, target_model, evaluation_data)
        elif method == "openai-multiagent":
            return self._optimize_openai_multiagent(prompt_text)
        else:
            print(f"[WARNING] Unknown method: {method}")
            return prompt_text
    
    def _optimize_google_zeroshot(self, prompt_text: str, target_model: str) -> str:
        """
        Optimize using Gemini with prompt engineering best practices.
        Uses a meta-prompt to apply official Google best practices.
        """
        print(f"[INFO] Optimizing for {target_model}...")
        
        try:
            import google.generativeai as genai
            
            # Configure Gemini
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                print("[WARNING] GOOGLE_API_KEY not set, using original prompt")
                return prompt_text
            
            genai.configure(api_key=api_key)
            
            # Meta-prompt for optimization
            meta_prompt = f"""You are an expert prompt engineer specializing in optimizing prompts for Gemini models.

Analyze the following prompt and improve it by applying these best practices:

1. **Clear Instructions**: Make task description explicit and unambiguous
2. **Structured Format**: Use clear sections with headers
3. **Explicit Definitions**: Define all key terms and concepts
4. **Step-by-Step Process**: Break complex tasks into numbered steps
5. **Output Format Specification**: Clearly specify expected output structure
6. **Boundary Setting**: Explicitly state what to do and what NOT to do
7. **Examples Where Helpful**: Add illustrative examples for complex concepts
8. **Conciseness**: Remove redundancy while keeping clarity

ORIGINAL PROMPT:
{prompt_text}

Provide the OPTIMIZED version following these guidelines. Output ONLY the optimized prompt text, no explanations or meta-commentary."""

            # Use Gemini to optimize
            model = genai.GenerativeModel(target_model)
            response = model.generate_content(
                meta_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8192
                )
            )
            
            optimized_text = response.text.strip()
            
            # Log changes
            orig_len = len(prompt_text)
            opt_len = len(optimized_text)
            change_pct = ((opt_len - orig_len) / orig_len) * 100 if orig_len > 0 else 0
            
            print(f"[SUCCESS] Optimized (length: {orig_len} → {opt_len}, {change_pct:+.1f}%)")
            
            return optimized_text
        
        except Exception as e:
            print(f"[ERROR] Optimization failed: {e}")
            print("[INFO] Using original prompt")
            return prompt_text
    
    def _optimize_google_datadriven(
        self,
        prompt_text: str,
        target_model: str,
        evaluation_data: Optional[Dict]
    ) -> str:
        """
        Optimize using Google Vertex AI Data-Driven Optimizer.
        Uses labeled examples for thorough optimization.
        """
        if not self._init_vertex_ai():
            print("[WARNING] Vertex AI unavailable, using original prompt")
            return prompt_text
        
        if not evaluation_data:
            print("[WARNING] Data-driven optimization requires evaluation_data")
            print("[INFO] Falling back to zero-shot optimization")
            return self._optimize_google_zeroshot(prompt_text, target_model)
        
        try:
            print("[INFO] Running data-driven optimization (this may take a while)...")
            
            # This is a more complex API call that requires evaluation data
            # Placeholder for actual implementation
            print("[WARNING] Data-driven optimization not fully implemented yet")
            print("[INFO] Falling back to zero-shot")
            return self._optimize_google_zeroshot(prompt_text, target_model)
        
        except Exception as e:
            print(f"[ERROR] Data-driven optimization failed: {e}")
            return prompt_text
    
    def _optimize_openai_multiagent(self, prompt_text: str) -> str:
        """
        Optimize using OpenAI Multi-Agent System.
        
        Note: This currently requires manual use of the OpenAI Playground.
        This method provides guidance and can be enhanced when API becomes available.
        """
        if not self._init_openai():
            print("[WARNING] OpenAI unavailable")
            return prompt_text
        
        print("[INFO] OpenAI Multi-Agent optimization requires manual steps:")
        print("  1. Go to: https://platform.openai.com/chat/edit?optimize=true")
        print("  2. Paste your prompt")
        print("  3. Click 'Optimize'")
        print("  4. Review and save")
        print()
        print("[INFO] For now, returning original prompt")
        
        # Future: When API becomes available, implement automated multi-agent optimization
        return prompt_text
    
    def compare_optimizations(
        self,
        prompt_text: str,
        methods: list = None
    ) -> Dict[str, str]:
        """
        Compare multiple optimization methods.
        
        Args:
            prompt_text: Original prompt
            methods: List of methods to compare (default: all available)
        
        Returns:
            Dictionary mapping method names to optimized prompts
        """
        if methods is None:
            methods = ["none", "google-zeroshot"]
        
        results = {}
        
        for method in methods:
            print(f"\n{'='*70}")
            print(f"Testing method: {method}")
            print('='*70)
            
            optimized = self.optimize(prompt_text, method=method)
            results[method] = optimized
        
        return results


def optimize_template_file(
    template_path: str,
    output_path: Optional[str] = None,
    method: str = "google-zeroshot"
) -> bool:
    """
    Optimize a YAML template file.
    
    Args:
        template_path: Path to template YAML file
        output_path: Where to save optimized template (default: <name>_optimized.yaml)
        method: Optimization method
    
    Returns:
        True if successful
    """
    try:
        import yaml
        from prompt_templates import PromptTemplate
        from pathlib import Path
        
        # Load template
        template_file = Path(template_path)
        template = PromptTemplate.load(template_file.stem, str(template_file.parent))
        
        # Optimize system prompt
        optimizer = PromptOptimizer()
        optimized_system = optimizer.optimize(
            template.system_prompt,
            method=method,
            target_model="gemini-2.5-pro"
        )
        
        # Create output path
        if output_path is None:
            path = Path(template_path)
            output_path = path.parent / f"{path.stem}_optimized{path.suffix}"
        
        # Load original YAML
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Update system prompt
        data['system_prompt'] = optimized_system
        
        # Update version and changelog
        old_version = data['metadata']['version']
        new_version_parts = old_version.split('.')
        new_version_parts[-1] = str(int(new_version_parts[-1]) + 1)
        new_version = '.'.join(new_version_parts)
        
        data['metadata']['version'] = new_version
        data['metadata']['changelog'].insert(0, {
            'version': new_version,
            'date': '2025-10-05',
            'changes': f'Auto-optimized using {method}'
        })
        
        # Save
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        
        print(f"\n[SUCCESS] Optimized template saved to: {output_path}")
        print(f"[INFO] Version: {old_version} → {new_version}")
        
        return True
    
    except Exception as e:
        print(f"[ERROR] Template optimization failed: {e}")
        return False


def main():
    """CLI for prompt optimization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimize prompts using various APIs")
    parser.add_argument("prompt", nargs="?", help="Prompt text or path to prompt file")
    parser.add_argument("--method", default="google-zeroshot",
                       choices=["google-zeroshot", "google-datadriven", "openai-multiagent", "none"],
                       help="Optimization method")
    parser.add_argument("--model", default="gemini-2.5-pro", help="Target model")
    parser.add_argument("--compare", action="store_true", help="Compare multiple methods")
    parser.add_argument("--template", help="Path to YAML template file to optimize")
    
    args = parser.parse_args()
    
    optimizer = PromptOptimizer()
    
    # Template file optimization
    if args.template:
        optimize_template_file(args.template, method=args.method)
        return 0
    
    # Interactive mode if no prompt provided
    if not args.prompt:
        print("Enter prompt (multi-line, Ctrl+D or Ctrl+Z to finish):")
        prompt_lines = []
        try:
            while True:
                line = input()
                prompt_lines.append(line)
        except EOFError:
            pass
        prompt_text = '\n'.join(prompt_lines)
    else:
        # Check if it's a file
        if Path(args.prompt).exists():
            with open(args.prompt, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
        else:
            prompt_text = args.prompt
    
    # Compare mode
    if args.compare:
        results = optimizer.compare_optimizations(prompt_text)
        
        print("\n" + "="*70)
        print("COMPARISON RESULTS")
        print("="*70)
        
        for method, optimized in results.items():
            print(f"\n### {method.upper()} ###")
            print(optimized[:500] + "..." if len(optimized) > 500 else optimized)
        
        return 0
    
    # Single optimization
    optimized = optimizer.optimize(prompt_text, method=args.method, target_model=args.model)
    
    print("\n" + "="*70)
    print("OPTIMIZED PROMPT")
    print("="*70)
    print(optimized)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
