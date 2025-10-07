"""
Unit tests for LLM provider abstraction layer.
Tests provider creation, configuration, and response handling.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, patch, MagicMock
from llm_providers import (
    LLMConfig,
    LLMResponse,
    OpenAIProvider,
    GeminiProvider,
    LLMProviderFactory
)


class TestLLMConfig:
    """Test suite for LLMConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.temperature == 0.0
        assert config.json_mode is True
        assert config.max_tokens is None
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LLMConfig(
            temperature=0.7,
            max_tokens=1000,
            json_mode=False
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.json_mode is False
    
    def test_to_dict_excludes_none(self):
        """Test that to_dict excludes None values."""
        config = LLMConfig(temperature=0.5, max_tokens=None)
        config_dict = config.to_dict()
        assert 'temperature' in config_dict
        assert 'max_tokens' not in config_dict


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""
    
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.model == "gpt-4o"
        assert provider.api_key == "test-key"
    
    def test_supports_json_mode(self):
        """Test that OpenAI provider supports JSON mode."""
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.supports_json_mode() is True
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=True)
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIProvider(model="gpt-4o")
    
    @patch('llm_providers.OpenAI')
    def test_generate_with_json_mode(self, mock_openai):
        """Test generation with JSON mode enabled."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"result": "test"}'), finish_reason='stop')]
        mock_response.model = 'gpt-4o'
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        messages = [{"role": "user", "content": "Test message"}]
        config = LLMConfig(json_mode=True)
        
        response = provider.generate(messages, config)
        
        assert response.content == '{"result": "test"}'
        assert response.model == 'gpt-4o'
        assert response.usage['total_tokens'] == 30
        
        # Verify JSON mode was requested
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs['response_format'] == {"type": "json_object"}
    
    @patch('llm_providers.OpenAI')
    def test_generate_without_temperature_for_o3(self, mock_openai):
        """Test that o3 models don't get temperature parameter."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='test'), finish_reason='stop')]
        mock_response.model = 'o3-mini'
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        provider = OpenAIProvider(model="o3-mini", api_key="test-key")
        messages = [{"role": "user", "content": "Test"}]
        
        provider.generate(messages)
        
        # Verify temperature was NOT included
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert 'temperature' not in call_kwargs
    
    @patch('llm_providers.OpenAI')
    def test_gpt5_uses_max_completion_tokens(self, mock_openai):
        """Test that GPT-5 uses max_completion_tokens instead of max_tokens."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='test'), finish_reason='stop')]
        mock_response.model = 'gpt-5'
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-5", api_key="test-key")
        messages = [{"role": "user", "content": "Test"}]
        config = LLMConfig(max_tokens=4096)
        
        provider.generate(messages, config)
        
        # Verify max_completion_tokens was used instead of max_tokens
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert 'max_completion_tokens' in call_kwargs
        assert call_kwargs['max_completion_tokens'] == 4096
        assert 'max_tokens' not in call_kwargs
        # Also verify temperature is not included for GPT-5
        assert 'temperature' not in call_kwargs


class TestGeminiProvider:
    """Test suite for GeminiProvider."""
    
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch('llm_providers.genai.configure'):
            provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
            assert provider.model == "gemini-2.5-pro"
            assert provider.api_key == "test-key"
    
    def test_supports_json_mode(self):
        """Test that Gemini provider supports JSON mode."""
        with patch('llm_providers.genai.configure'):
            provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
            assert provider.supports_json_mode() is True
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': ''}, clear=True)
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            GeminiProvider(model="gemini-2.5-pro")
    
    def test_format_messages_for_gemini(self):
        """Test message formatting for Gemini API."""
        with patch('llm_providers.genai.configure'):
            provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ]
            
            formatted = provider._format_messages_for_gemini(messages)
            
            assert "You are a helpful assistant." in formatted
            assert "Hello!" in formatted
    
    @patch('llm_providers.genai.GenerativeModel')
    @patch('llm_providers.genai.configure')
    def test_generate_with_json_mode(self, mock_configure, mock_model_class):
        """Test generation with JSON mode enabled."""
        # Setup mock
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '{"result": "test"}'
        mock_response.candidates = [Mock(finish_reason='STOP')]
        mock_response.usage_metadata = Mock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30
        )
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
        messages = [{"role": "user", "content": "Test message"}]
        config = LLMConfig(json_mode=True)
        
        response = provider.generate(messages, config)
        
        assert response.content == '{"result": "test"}'
        assert response.usage['total_tokens'] == 30
        
        # Verify JSON mode was requested
        call_kwargs = mock_model_class.call_args.kwargs
        assert call_kwargs['generation_config'].response_mime_type == "application/json"


class TestLLMProviderFactory:
    """Test suite for LLMProviderFactory."""
    
    def test_create_openai_provider(self):
        """Test creating OpenAI provider via factory."""
        provider = LLMProviderFactory.create('openai', 'gpt-4o', api_key='test-key')
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == 'gpt-4o'
    
    def test_create_gemini_provider(self):
        """Test creating Gemini provider via factory."""
        with patch('llm_providers.genai.configure'):
            provider = LLMProviderFactory.create('gemini', 'gemini-2.5-pro', api_key='test-key')
            assert isinstance(provider, GeminiProvider)
            assert provider.model == 'gemini-2.5-pro'
    
    def test_create_invalid_provider_raises_error(self):
        """Test that invalid provider name raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            LLMProviderFactory.create('invalid', 'some-model', api_key='test-key')
    
    def test_auto_detect_gpt_model(self):
        """Test auto-detection of GPT models."""
        provider = LLMProviderFactory.auto_detect('gpt-4o', api_key='test-key')
        assert isinstance(provider, OpenAIProvider)
        
        provider = LLMProviderFactory.auto_detect('gpt-5', api_key='test-key')
        assert isinstance(provider, OpenAIProvider)
        
        provider = LLMProviderFactory.auto_detect('o3-mini', api_key='test-key')
        assert isinstance(provider, OpenAIProvider)
    
    def test_auto_detect_gemini_model(self):
        """Test auto-detection of Gemini models."""
        with patch('llm_providers.genai.configure'):
            provider = LLMProviderFactory.auto_detect('gemini-2.5-pro', api_key='test-key')
            assert isinstance(provider, GeminiProvider)
            
            provider = LLMProviderFactory.auto_detect('gemini-2.0-flash', api_key='test-key')
            assert isinstance(provider, GeminiProvider)
    
    def test_auto_detect_unknown_model_raises_error(self):
        """Test that unknown model pattern raises ValueError."""
        with pytest.raises(ValueError, match="Could not auto-detect"):
            LLMProviderFactory.auto_detect('unknown-model-123', api_key='test-key')
    
    def test_list_providers(self):
        """Test listing supported providers."""
        providers = LLMProviderFactory.list_providers()
        assert 'openai' in providers
        assert 'gemini' in providers


class TestLLMResponse:
    """Test suite for LLMResponse dataclass."""
    
    def test_response_creation(self):
        """Test creating LLMResponse."""
        response = LLMResponse(
            content="Test response",
            model="gpt-4o",
            usage={"total_tokens": 100},
            finish_reason="stop"
        )
        
        assert response.content == "Test response"
        assert response.model == "gpt-4o"
        assert response.usage['total_tokens'] == 100
        assert response.finish_reason == "stop"
    
    def test_response_with_minimal_fields(self):
        """Test LLMResponse with only required fields."""
        response = LLMResponse(
            content="Test",
            model="gpt-4o"
        )
        
        assert response.content == "Test"
        assert response.usage is None
        assert response.finish_reason is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
