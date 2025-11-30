"""Quick test for Claude provider."""
import sys
sys.path.insert(0, '.')

# Load .env file
from dotenv import load_dotenv
load_dotenv()

from llm_providers import LLMProviderFactory

print('Testing Claude provider auto-detection...')
try:
    provider = LLMProviderFactory.auto_detect('claude-sonnet-4')
    print(f'  Provider: {provider}')
    print(f'  Model: {provider.model}')
    
    # Test a simple generation
    response = provider.generate([{
        'role': 'user', 
        'content': 'Return a JSON object with a greeting: {"greeting": "Hello!"}'
    }])
    print(f'  Response: {response.content[:200]}')
    print('✅ Claude provider working!')
except Exception as e:
    print(f'❌ Error: {e}')
