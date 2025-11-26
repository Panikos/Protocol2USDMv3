# Quick Start: Integrating Prompt Optimization APIs

**Get started with Google's Zero-Shot Optimizer in 30 minutes**

---

## Step 1: Google Cloud Setup (10 min)

### Create Google Cloud Account
```bash
# 1. Go to https://cloud.google.com/
# 2. Sign up / Sign in
# 3. Create new project: "prompt-optimization"
```

### Enable Required APIs
```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Or via Console:
# https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
```

### Install SDK
```bash
pip install google-cloud-aiplatform
```

### Authenticate
```bash
# Set up authentication
gcloud auth application-default login

# Or set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

---

## Step 2: Quick Test (5 min)

### Test Zero-Shot Optimizer

Create `test_optimizer.py`:

```python
from google.cloud import aiplatform

# Initialize
aiplatform.init(
    project="your-project-id",
    location="us-central1"
)

# Your current prompt
original_prompt = """
Extract the Schedule of Activities from the protocol text.
Return JSON with activities and timepoints.
"""

# Optimize it!
from vertexai.preview.prompts import Prompt

prompt_obj = Prompt(
    prompt_data=original_prompt,
    model_name="gemini-2.5-pro"
)

# Get optimization suggestions
optimized = prompt_obj.optimize()

print("ORIGINAL:")
print(original_prompt)
print("\n" + "="*70 + "\n")
print("OPTIMIZED:")
print(optimized.prompt_data)
```

Run it:
```bash
python test_optimizer.py
```

**Expected:** Improved version with better structure and clarity

---

## Step 3: Integrate into Strategy (15 min)

### Add to `benchmark_prompts.py`

```python
# At top of file
from google.cloud import aiplatform
from vertexai.preview.prompts import Prompt

ENABLE_AUTO_OPTIMIZATION = True  # Feature flag

class PromptBenchmark:
    # ... existing code ...
    
    def optimize_prompt(self, prompt_text: str, target_model: str = "gemini-2.5-pro") -> str:
        """
        Use Google's zero-shot optimizer to improve prompt.
        
        Args:
            prompt_text: Original prompt text
            target_model: Target Gemini model
            
        Returns:
            Optimized prompt text
        """
        if not ENABLE_AUTO_OPTIMIZATION:
            return prompt_text
        
        try:
            print(f"[INFO] Optimizing prompt for {target_model}...")
            
            # Initialize
            aiplatform.init(
                project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                location="us-central1"
            )
            
            # Create prompt object
            prompt_obj = Prompt(
                prompt_data=prompt_text,
                model_name=target_model
            )
            
            # Optimize
            optimized = prompt_obj.optimize()
            
            print(f"[SUCCESS] Prompt optimized (length: {len(prompt_text)} → {len(optimized.prompt_data)})")
            
            return optimized.prompt_data
        
        except Exception as e:
            print(f"[WARNING] Optimization failed: {e}. Using original.")
            return prompt_text
    
    def run_benchmark_with_optimization(self, model: str = "gemini-2.5-pro") -> Dict:
        """Run benchmark, optionally optimizing prompts first."""
        
        # Load current prompts
        from prompt_templates import PromptTemplate
        
        templates = {
            "vision": PromptTemplate.load("vision_soa_extraction", "prompts"),
            "text": PromptTemplate.load("soa_extraction", "prompts"),
            "reconciliation": PromptTemplate.load("soa_reconciliation", "prompts"),
        }
        
        # Optionally optimize each
        if ENABLE_AUTO_OPTIMIZATION:
            for name, template in templates.items():
                print(f"\n[OPTIMIZE] {name}...")
                optimized_system = self.optimize_prompt(
                    template.system_prompt, 
                    model
                )
                template.system_prompt = optimized_system
        
        # Run normal benchmark
        return self.run_benchmark(model)
```

### Add Command-Line Flag

```python
# In main()
parser.add_argument(
    "--auto-optimize", 
    action="store_true",
    help="Auto-optimize prompts before benchmarking"
)

if args.auto_optimize:
    ENABLE_AUTO_OPTIMIZATION = True
```

### Usage

```bash
# Regular benchmark
python benchmark_prompts.py --test-set test_data/

# With auto-optimization
python benchmark_prompts.py --test-set test_data/ --auto-optimize
```

---

## Step 4: Compare Results

### Run A/B Test

```bash
# 1. Baseline (no optimization)
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro
# Save results: baseline.json

# 2. With optimization
python benchmark_prompts.py --test-set test_data/ --model gemini-2.5-pro --auto-optimize
# Save results: optimized.json

# 3. Compare
python compare_results.py baseline.json optimized.json
```

**Expected improvement:** 2-5% on primary metrics

---

## OpenAI Multi-Agent Integration (Advanced)

### Step 1: Access Optimizer

1. Go to [OpenAI Platform](https://platform.openai.com/chat/edit?optimize=true)
2. Paste your prompt in Developer Message
3. Click "Optimize" button
4. Review suggested improvements
5. Save as Prompt Object

### Step 2: Use in Code

```python
from openai import OpenAI

client = OpenAI()

# Load saved prompt object
response = client.chat.completions.create(
    model="gpt-5",
    prompt_id="your-saved-prompt-id",  # From step 1
    messages=[
        {"role": "user", "content": protocol_text}
    ]
)
```

---

## Environment Variables

Add to `.env`:

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# OpenAI (already have)
OPENAI_API_KEY=sk-...

# Google API (already have)
GOOGLE_API_KEY=...
```

---

## Cost Tracking

### Monitor Usage

```python
import time

def optimize_with_cost_tracking(prompt_text):
    start_time = time.time()
    
    optimized = optimize_prompt(prompt_text)
    
    duration = time.time() - start_time
    
    # Log for cost analysis
    print(f"[COST] Optimization took {duration:.2f}s")
    # Approximate: $0.01-0.05 per optimization
    
    return optimized
```

### Estimate Monthly Cost

```python
# Per prompt optimization: ~$0.02
# Per sprint (4 prompts, 2x/month): $0.16
# Monthly: ~$5-10

# Well within budget!
```

---

## Troubleshooting

### "Authentication failed"
```bash
# Re-authenticate
gcloud auth application-default login

# Verify
gcloud auth list
```

### "API not enabled"
```bash
# Enable all required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable compute.googleapis.com
```

### "Quota exceeded"
```bash
# Check quotas
gcloud compute project-info describe --project=your-project-id

# Request increase if needed
# https://console.cloud.google.com/iam-admin/quotas
```

### "Optimization doesn't improve results"
- Not all prompts need optimization
- Try with different test cases
- Compare on full benchmark, not single run
- Some prompts are already well-optimized

---

## Best Practices

### When to Auto-Optimize

✅ **DO optimize when:**
- Starting new prompt from scratch
- Prompt has known issues
- Metrics are below target
- Migrating prompts between models

❌ **DON'T optimize when:**
- Prompt already performing well (>95%)
- Just made manual improvements (test first)
- In production without testing
- Cost is a concern for high-frequency calls

### Optimization Workflow

```
Manual Draft (v2.1)
    ↓
Auto-Optimize → Candidate A
    ↓
Benchmark Both
    ↓
Choose Better Performer
    ↓
Deploy Winner
```

---

## Quick Reference

### Google Zero-Shot
```python
from vertexai.preview.prompts import Prompt

prompt = Prompt(prompt_data=text, model_name="gemini-2.5-pro")
optimized = prompt.optimize()
```

### OpenAI Multi-Agent
```
1. Paste in Playground
2. Click "Optimize"
3. Review changes
4. Save & use
```

### Cost Estimates
- Google Zero-Shot: ~$0.01-0.02 per prompt
- OpenAI Multi-Agent: ~$0.05-0.10 per prompt
- Monthly budget: ~$20-30

---

## Success Metrics

Track these to measure optimization API value:

1. **Time Savings**
   - Before: 2 hours manual iteration
   - After: 30 min (auto-optimize + test)
   - **Savings: 75%**

2. **Quality Improvement**
   - Additional 2-5% over manual
   - More consistent application of best practices
   - **Value: High**

3. **Consistency**
   - All prompts follow same standards
   - Automatic contradiction detection
   - **Value: High**

---

## Next Steps

1. ✅ Complete setup (30 min)
2. ✅ Run test optimization
3. ✅ Integrate into benchmark tool
4. ✅ Run A/B comparison
5. ✅ Update strategy with learnings
6. 🔄 Make it part of regular workflow

---

**Status:** Ready to integrate  
**Time to value:** 30 minutes  
**Expected ROI:** Very high (40-60% faster + 2-5% better quality)

Start with Google's zero-shot optimizer today!
