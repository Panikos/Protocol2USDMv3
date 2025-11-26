#!/usr/bin/env python3
"""Quick script to optimize the soa_extraction template"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from prompt_optimizer import PromptOptimizer
from prompt_templates import PromptTemplate
import yaml

print('Optimizing soa_extraction.yaml...')

# Load and optimize
optimizer = PromptOptimizer()
template = PromptTemplate.load('soa_extraction', 'prompts')
optimized = optimizer.optimize(template.system_prompt, method='google-zeroshot')

print(f'Optimized: {len(template.system_prompt)} -> {len(optimized)} chars')

# Load YAML
template_file = Path('prompts/soa_extraction.yaml')
with open(template_file, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Update
data['system_prompt'] = optimized
data['metadata']['version'] = '2.1'
data['metadata']['description'] += '\nAuto-optimized using google-zeroshot.'

if 'changelog' not in data['metadata']:
    data['metadata']['changelog'] = []

data['metadata']['changelog'].insert(0, {
    'version': '2.1',
    'date': '2025-10-06',
    'changes': 'Auto-optimized using google-zeroshot'
})

# Save
output_path = Path('prompts/soa_extraction_optimized.yaml')
with open(output_path, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=120)

print(f'✅ Saved to: {output_path}')
