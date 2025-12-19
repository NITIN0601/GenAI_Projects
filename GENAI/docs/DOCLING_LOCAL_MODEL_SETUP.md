# Docling Local Model Configuration

This guide explains how to configure Docling to use locally downloaded models instead of downloading from HuggingFace Hub.

## Quick Setup

The system **automatically detects** local model weights in:
- `src/model/doclingPackages/` — Layout model (docling-layout-heron)
- `src/model/docling-models/` — Tableformer models

No `.env` changes needed if models are in these directories!

### Optional: Manual Override

```bash
# Override auto-detection with a custom path
DOCLING_ARTIFACTS_PATH=/path/to/custom/models

# Allow downloading from HuggingFace if local models not found
DOCLING_ALLOW_DOWNLOAD=False
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOCLING_ARTIFACTS_PATH` | Override auto-detected model path | Auto-detect |
| `DOCLING_ALLOW_DOWNLOAD` | Allow HuggingFace downloads | `False` (local only) |
| `DOCLING_OCR_ENGINE` | Force OCR engine (`ocrmac`, `rapidocr`, `auto`) | `auto` |
| `DOCLING_TABLE_MODE` | TableFormer mode (`accurate`, `fast`) | `accurate` |
| `DOCLING_IMAGE_SCALE` | Image resolution scale (1.0-4.0) | `1.0` |

---

## Directory Structure

```
src/model/
├── doclingPackages/              # Layout model (docling-layout-heron)
│   ├── config.json
│   ├── model.safetensors         # ~171MB
│   ├── preprocessor_config.json
│   └── RapidOcr/                 # OCR models (Windows/Linux)
│       └── onnx/PP-OCRv4/
│           ├── det/
│           ├── rec/
│           └── cls/
│
└── docling-models/               # Tableformer models
    ├── config.json
    ├── README.md
    └── model_artifacts/
        └── tableformer/
            ├── accurate/
            └── fast/
```

---

## Downloading Models

### Layout Model (doclingPackages)

Download from: https://huggingface.co/docling-project/docling-layout-heron

Place in `src/model/doclingPackages/`.

### Tableformer Model (docling-models)

Download from: https://huggingface.co/ds4sd/docling-models

Place in `src/model/docling-models/`.

### Alternative: Using docling-tools

```bash
docling-tools models download --artifacts-path /path/to/your/models
```

---

## How It Works

The `DoclingHelper.convert_pdf()` function in `src/utils/extraction_utils.py`:

1. Checks `DOCLING_ARTIFACTS_PATH` environment variable
2. Auto-detects local models in `src/model/doclingPackages/` and `src/model/docling-models/`
3. If found → Sets offline mode, uses local weights
4. If not found and `DOCLING_ALLOW_DOWNLOAD=True` → Downloads from HuggingFace
5. Otherwise → Raises error with setup instructions

---

## Verification

```python
from src.utils.extraction_utils import DoclingHelper

# Auto-detects local models
result = DoclingHelper.convert_pdf('your_pdf.pdf')
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No local docling model weights found" | Ensure `src/model/doclingPackages/model.safetensors` exists |
| Missing tableformer models | Add `src/model/docling-models/model_artifacts/` |
| Still trying to download | Check that `DOCLING_ALLOW_DOWNLOAD` is not set to `True` |

---

## Related Files

- **Configuration**: `.env.example` (lines 85-110)
- **Implementation**: `src/utils/extraction_utils.py` → `DoclingHelper`
- **Backend**: `src/infrastructure/extraction/backends/docling_backend.py`
