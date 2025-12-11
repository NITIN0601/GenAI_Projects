# Docling Local Model Configuration

This guide explains how to configure Docling to use locally downloaded models instead of downloading from HuggingFace Hub.

## Quick Setup

Add to your `.env` file:

```bash
# Path to local docling models
DOCLING_ARTIFACTS_PATH=/Users/nitin/Desktop/Chatbot/Morgan/GENAI/src/model/docling

# Force offline mode (prevents downloads from HuggingFace)
DOCLING_OFFLINE=True
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DOCLING_ARTIFACTS_PATH` | Path to locally downloaded docling models | `/path/to/src/model/docling` |
| `DOCLING_OFFLINE` | Set to `True` to block internet downloads | `True` or `False` |

---

## Downloading Models

### Step 1: Download from HuggingFace

Download the docling-layout-heron model from:
- **URL**: https://huggingface.co/docling-project/docling-layout-heron

### Step 2: Directory Structure

Place the model files in your local directory:

```
src/model/docling/
├── config.json
├── model.safetensors (or model.bin)
├── preprocessor_config.json
├── tokenizer_config.json
└── ... (other model files)
```

### Alternative: Using docling-tools

```bash
# Prefetch all docling models to a specific directory
docling-tools models download --artifacts-path /path/to/your/models
```

---

## How It Works

The `DoclingHelper.convert_pdf()` function in `src/utils/extraction_utils.py` checks for environment variables:

1. If `DOCLING_ARTIFACTS_PATH` is set → Uses local models
2. If `DOCLING_OFFLINE=True` → Sets HuggingFace offline mode
3. Otherwise → Downloads from HuggingFace Hub (default)

---

## Verification

Test the configuration:

```python
import os
os.environ['DOCLING_ARTIFACTS_PATH'] = '/path/to/your/models'
os.environ['DOCLING_OFFLINE'] = 'True'

from src.utils.extraction_utils import DoclingHelper

# This should use local models without internet access
result = DoclingHelper.convert_pdf('your_pdf.pdf')
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Model still downloading | Verify `DOCLING_ARTIFACTS_PATH` is set correctly |
| Missing model files | Ensure all files from HuggingFace repo are present |
| Module not found errors | Check docling version compatibility |

---

## Related Files

- **Configuration**: `.env` / `.env.example`
- **Implementation**: `src/utils/extraction_utils.py` → `DoclingHelper.convert_pdf()`
- **Backend**: `src/infrastructure/extraction/backends/docling_backend.py`
