# Protocol2USDMv3 Quick Reference

**Version 4.0** | One-page reference for common tasks

---

## 🚀 Quick Start (30 seconds)

```bash
pip install -r requirements.txt
echo "GOOGLE_API_KEY=your_key" > .env
python main.py input/protocol.pdf
streamlit run soa_streamlit_viewer.py
```

---

## 📝 Common Commands

### Running the Pipeline
```bash
# Default (Gemini 2.5 Pro)
python main.py protocol.pdf

# Specific models
python main.py protocol.pdf --model gpt-4o
python main.py protocol.pdf --model gpt-5
python main.py protocol.pdf --model gemini-2.0-flash

# View results
streamlit run soa_streamlit_viewer.py
```

### Testing
```bash
# All tests (93 total)
pytest

# Specific test suites
pytest tests/test_llm_providers.py -v      # 22 tests
pytest tests/test_prompt_templates.py -v   # 19 tests
pytest tests/test_normalization.py -v      # 18 tests
pytest tests/test_json_extraction.py -v    # 12 tests
```

---

## 🔑 API Keys Setup

**.env file:**
```bash
# Google (recommended)
GOOGLE_API_KEY=AIzaSy...

# OpenAI (optional)
OPENAI_API_KEY=sk-proj-...
```

**Get keys:**
- Google: https://makersuite.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys

---

## 📊 Model Comparison

| Model | Speed | Cost | Quality |
|-------|-------|------|---------|
| **gemini-2.5-pro** ⭐ | Fast | $$ | Excellent |
| gemini-2.0-flash | Very Fast | $ | Good |
| gpt-4o | Medium | $$$ | Excellent |
| gpt-5 | Medium | $$$$ | TBD |

**Recommendation:** Use `gemini-2.5-pro` (default)

---

## 📁 Output Files

```
output/PROTOCOL_NAME/
├── 10_reconciled_soa.json  ⭐ Main output
├── 5_raw_text_soa.json     📄 Text extraction
├── 6_raw_vision_soa.json   👁️ Vision extraction
├── pipeline.log            📋 Detailed logs
└── 3_soa_images/          🖼️ Page images
```

---

## 🔍 Checking Quality

### Log Statistics
```bash
grep "\[STATISTICS\]" output/PROTOCOL/pipeline.log
grep "\[POST-PROCESS\]" output/PROTOCOL/pipeline.log
```

### Expected Output
```
[STATISTICS] Chunk Processing Results:
  Successful: 3 (100.0%)
  Failed: 0

[POST-PROCESS] Normalized 5 entity names
[POST-PROCESS] Normalization complete
```

### Validation
```bash
# Final step validates automatically
# Check for errors:
grep "ERROR" output/PROTOCOL/pipeline.log
```

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| **API key error** | Check `.env` file, restart terminal |
| **Parse failures** | Check `[RETRY]` in logs, should auto-fix |
| **Missing visits** | Verify `2_soa_pages.json` has correct pages |
| **Schema errors** | Post-processing auto-fixes most issues |

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Overview & quick start |
| `USER_GUIDE.md` | Comprehensive guide |
| `QUICK_REFERENCE.md` | This file |
| `CHANGELOG.md` | Version history |
| `IMPLEMENTATION_COMPLETE.md` | Technical details |
| `MULTI_MODEL_IMPLEMENTATION.md` | Provider layer guide |

---

## 🎯 Pipeline Steps (11 total)

1. **Generate prompt** (~5s)
2. **Find SoA pages** (~10s)  
3. **Extract images** (~5s)
4. **Analyze structure** (~15s)
5. **Text extraction** (~60s) ⏱️
6. **Vision extraction** (~45s) ⏱️
7. **Post-process text** (~5s)
8. **Post-process vision** (~5s)
9. **Validate header** (~2s)
10. **Reconcile outputs** (~30s)
11. **Schema validation** (~5s)

**Total:** ~3-5 minutes

---

## 💡 Tips

### Best Practices
- ✅ Use Gemini 2.5 Pro for production
- ✅ Check logs for warnings
- ✅ Review in Streamlit viewer
- ✅ Verify all visits present
- ✅ Run tests after updates

### Cost Optimization
- Use `gemini-2.0-flash` for testing
- Cache results to avoid re-processing
- Process protocols in batches

### Quality Checks
- Compare visit count to protocol
- Check timing information accuracy
- Verify activity completeness
- Review orphaned timepoints

---

## 🧪 Development

### Running Tests
```bash
# All tests
pytest -v

# With coverage
pytest --cov=. tests/

# Specific module
pytest tests/test_llm_providers.py::TestOpenAIProvider -v
```

### Editing Prompts
```bash
# Edit template
vim prompts/soa_extraction.yaml

# Test changes
python main.py protocol.pdf
```

### Adding New Models
```python
# No code changes needed!
# Provider auto-detects from name:
# - "gpt" → OpenAI
# - "gemini" → Google
```

---

## 📞 Support

- **Logs:** `output/PROTOCOL/pipeline.log`
- **Tests:** `pytest tests/ -v`
- **Docs:** See table above

---

## 📌 Key Metrics

- **Tests:** 93/93 passing (100%)
- **Schema validation:** >95% pass rate
- **Parse success:** >95%
- **Clean names:** 100%
- **Models supported:** 4+ (extensible)

---

**Quick Links:**
- [Full User Guide](USER_GUIDE.md)
- [Implementation Details](MULTI_MODEL_IMPLEMENTATION.md)
- [Changelog](CHANGELOG.md)

---

**Last Updated:** 2025-10-04
