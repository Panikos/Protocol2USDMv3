"""
Unified LLM Client - Consolidates all LLM initialization and access.

This module eliminates the duplicated LLM setup code that was scattered across:
- reconcile_soa_llm.py
- send_pdf_to_llm.py
- vision_extract_soa.py
- soa_postprocess_consolidated.py
- find_soa_pages.py

Usage:
    from core.llm_client import get_llm_client, LLMConfig
    
    client = get_llm_client("gemini-2.5-pro")
    response = client.generate(messages, LLMConfig(json_mode=True))
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables once at module level
_env_loaded = False

def _ensure_env_loaded():
    """Ensure .env is loaded exactly once."""
    global _env_loaded
    if not _env_loaded:
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        _env_loaded = True


# Re-export from llm_providers for backward compatibility
try:
    from llm_providers import (
        LLMProviderFactory, 
        LLMConfig, 
        LLMResponse,
        OpenAIProvider,
        GeminiProvider,
    )
    PROVIDER_LAYER_AVAILABLE = True
except ImportError:
    PROVIDER_LAYER_AVAILABLE = False
    
    # Minimal fallback definitions
    @dataclass
    class LLMConfig:
        """Configuration for LLM generation."""
        temperature: float = 0.0
        max_tokens: Optional[int] = None
        json_mode: bool = True
        
    @dataclass
    class LLMResponse:
        """Standardized response from LLM."""
        content: str
        model: str
        usage: Optional[Dict[str, int]] = None


def get_llm_client(model_name: str, api_key: Optional[str] = None):
    """
    Get a configured LLM client for the specified model.
    
    This is the single entry point for obtaining LLM clients across the pipeline.
    
    Args:
        model_name: Model identifier (e.g., 'gpt-4o', 'gemini-2.5-pro', 'gpt-5.1')
        api_key: Optional API key override. If None, reads from environment.
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        ValueError: If provider layer unavailable and no fallback possible
        RuntimeError: If API key not configured
        
    Example:
        >>> client = get_llm_client("gemini-2.5-pro")
        >>> response = client.generate(messages, LLMConfig(json_mode=True))
        >>> print(response.content)
    """
    _ensure_env_loaded()
    
    if not PROVIDER_LAYER_AVAILABLE:
        raise ValueError(
            "LLM provider layer not available. "
            "Ensure llm_providers.py is in the project root."
        )
    
    return LLMProviderFactory.auto_detect(model_name, api_key=api_key)


def get_default_model() -> str:
    """
    Get the default model from environment or use fallback.
    
    Checks in order:
    1. OPENAI_MODEL environment variable
    2. Default to 'gemini-2.5-pro' (user preference)
    """
    _ensure_env_loaded()
    return os.environ.get("OPENAI_MODEL", "gemini-2.5-pro")


def is_reasoning_model(model_name: str) -> bool:
    """
    Check if model is a reasoning model (o1, o3, gpt-5 series).
    
    Reasoning models have different parameter requirements:
    - No temperature parameter
    - Use max_completion_tokens instead of max_tokens
    """
    reasoning_models = [
        'o1', 'o1-mini', 
        'o3', 'o3-mini', 'o3-mini-high',
        'gpt-5', 'gpt-5-mini', 
        'gpt-5.1', 'gpt-5.1-mini'
    ]
    return any(rm in model_name.lower() for rm in reasoning_models)


def detect_provider(model_name: str) -> str:
    """
    Detect the provider for a given model name.
    
    Returns:
        'openai', 'google', or 'unknown'
    """
    model_lower = model_name.lower()
    
    if any(x in model_lower for x in ['gpt', 'o1', 'o3']):
        return 'openai'
    elif 'gemini' in model_lower:
        return 'google'
    else:
        return 'unknown'


# Convenience function for simple text generation
def generate_text(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.0,
) -> str:
    """
    Simple text generation helper.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        temperature: Generation temperature
        
    Returns:
        Generated text content
    """
    if model_name is None:
        model_name = get_default_model()
        
    client = get_llm_client(model_name)
    config = LLMConfig(
        temperature=temperature,
        json_mode=json_mode,
    )
    
    response = client.generate(messages, config)
    return response.content


# Legacy compatibility - direct client access
def get_openai_client():
    """Get OpenAI client for legacy code. Prefer get_llm_client() instead."""
    _ensure_env_loaded()
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return OpenAI(api_key=api_key)
    except ImportError:
        pass
    return None


def get_gemini_client(model_name: str = "gemini-2.5-pro"):
    """Get Gemini client for legacy code. Prefer get_llm_client() instead."""
    _ensure_env_loaded()
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(model_name)
    except ImportError:
        pass
    return None


# Convenience functions for simple LLM calls
def call_llm(
    prompt: str,
    model_name: Optional[str] = None,
    json_mode: bool = True,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    Simple LLM call with a single prompt.
    
    Args:
        prompt: The prompt text
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        temperature: Generation temperature
        
    Returns:
        Dict with 'response' key containing the generated text
    """
    if model_name is None:
        model_name = get_default_model()
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        content = generate_text(
            messages=messages,
            model_name=model_name,
            json_mode=json_mode,
            temperature=temperature,
        )
        return {"response": content}
    except Exception as e:
        return {"error": str(e)}


def call_llm_with_image(
    prompt: str,
    image_path: str,
    model_name: Optional[str] = None,
    json_mode: bool = True,
) -> Dict[str, Any]:
    """
    LLM call with an image attachment.
    
    Args:
        prompt: The prompt text
        image_path: Path to the image file
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        
    Returns:
        Dict with 'response' key containing the generated text
    """
    import base64
    from pathlib import Path
    
    if model_name is None:
        model_name = get_default_model()
    
    _ensure_env_loaded()
    
    try:
        # Read and encode image
        image_data = Path(image_path).read_bytes()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Detect image type
        suffix = Path(image_path).suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(suffix, 'image/png')
        
        provider = detect_provider(model_name)
        
        if provider == 'google':
            # Use Gemini API
            import google.generativeai as genai
            
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                return {"error": "GOOGLE_API_KEY not set"}
                
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # Create image part
            image_part = {
                "mime_type": mime_type,
                "data": base64_image,
            }
            
            response = model.generate_content([prompt, image_part])
            return {"response": response.text}
            
        elif provider == 'openai':
            # Use OpenAI API
            from openai import OpenAI
            
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return {"error": "OPENAI_API_KEY not set"}
                
            client = OpenAI(api_key=api_key)
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
            )
            
            return {"response": response.choices[0].message.content}
        else:
            return {"error": f"Unknown provider for model: {model_name}"}
            
    except Exception as e:
        return {"error": str(e)}
