# Configuration Guide

> **Version:** 3.2.0 | **Updated:** December 18, 2025

## Overview

The system uses **enterprise-level configuration** with:

1. **YAML files** - For paths, logging, providers (static config)
2. **Environment files** - For dev/prod/test overrides
3. **`.env` file** - For secrets and API keys
4. **Pydantic settings** - For validation and defaults

---

## Configuration Structure

```
config/
├── settings.py           # Pydantic settings (loads .env)
├── loader.py             # YAML config loader
├── paths.yaml            # Directory paths
├── logging.yaml          # Enterprise logging config
├── providers.yaml        # LLM/Embedding/VectorDB providers
├── prompts.yaml          # Prompt templates
└── environments/         # Per-environment overrides
    ├── dev.yaml          # Development settings
    ├── prod.yaml         # Production settings
    └── test.yaml         # Test settings
```

---

## Quick Start

### Switch Environments

```bash
# Development (default)
APP_ENV=dev python main.py query "Revenue?"

# Production
APP_ENV=prod python main.py query "Revenue?"

# Testing
APP_ENV=test python -m pytest
```

### Access Configuration

```python
from config import settings           # .env secrets
from config import get_config         # Full YAML config
from config import get_llm_config     # Just LLM settings

# Get current environment
config = get_config()
print(config['_meta']['environment'])  # 'dev'
```

---

## Configuration Files

### 1. `paths.yaml` - Directory Structure

```yaml
data:
  root: data
  raw: data/raw
  processed: data/processed
  cache: data/cache

cache:
  extraction: data/cache/extraction
  embeddings: data/cache/embeddings
  queries: data/cache/queries

outputs:
  root: outputs
  extraction_reports: outputs/extraction_reports

logs:
  root: logs
```

### 2. `providers.yaml` - LLM/Embedding/VectorDB

```yaml
llm:
  default_provider: local
  providers:
    local:
      model: google/flan-t5-base
    ollama:
      model: llama3.2
      base_url: http://localhost:11434
    openai:
      model: gpt-4o-mini
      # api_key: from .env

embeddings:
  default_provider: local
  providers:
    local:
      model: sentence-transformers/all-MiniLM-L6-v2
    openai:
      model: text-embedding-3-small

vectordb:
  default_provider: faiss
  providers:
    faiss:
      index_type: flat
    chromadb:
      collection_name: financial_tables
```

### 3. `logging.yaml` - Enterprise Logging

```yaml
version: 1
handlers:
  console:
    class: logging.StreamHandler
    level: INFO
  file:
    class: logging.handlers.RotatingFileHandler
    filename: logs/app.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  src:
    level: DEBUG
    handlers: [console, file]
```

---

## Environment-Specific Overrides

### Development (`dev.yaml`)

```yaml
app:
  debug: true
  log_level: DEBUG

llm:
  default_provider: local  # Fast local models

cache:
  enabled: true
  ttl_multiplier: 0.5  # Shorter TTL for dev
```

### Production (`prod.yaml`)

```yaml
app:
  debug: false
  log_level: INFO

llm:
  default_provider: custom  # Production API

evaluation:
  auto_run: true
  block_hallucinations: true

logging:
  json_format: true  # For log aggregation
```

---

## Secrets in `.env`

API keys and secrets stay in `.env`:

```env
# API Keys (never commit!)
OPENAI_API_KEY=sk-...
BEARER_TOKEN=your-custom-api-token
LANGSMITH_API_KEY=ls-...

# Provider choices
LLM_PROVIDER=local
EMBEDDING_PROVIDER=local
VECTORDB_PROVIDER=faiss

# Redis (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# Docling Extraction Configuration
DOCLING_ARTIFACTS_PATH=        # Path to local model weights (auto-detected)
DOCLING_ALLOW_DOWNLOAD=False   # Allow HuggingFace model downloads
DOCLING_TABLE_MODE=accurate    # TableFormer mode: "accurate" or "fast"
DOCLING_IMAGE_SCALE=1.0        # Image resolution scale (1.0-4.0)
DOCLING_OCR_ENGINE=auto        # OCR engine: "ocrmac", "rapidocr", "auto"
```

> [!IMPORTANT]
> **SecretStr Protection**: Sensitive fields use Pydantic's `SecretStr` type which prevents accidental logging. To access the actual value in code, use `.get_secret_value()`:
>
> ```python
> # ✅ Correct - extract secret value when needed
> api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
> 
> # ❌ Wrong - SecretStr object, not the actual string
> api_key = settings.OPENAI_API_KEY  # Returns SecretStr('**********')
> ```
>
> Protected fields: `OPENAI_API_KEY`, `BEARER_TOKEN`, `LANGSMITH_API_KEY`, `REDIS_PASSWORD`

---

## Environment Variable Interpolation

YAML files support `${VAR_NAME}` syntax:

```yaml
# In providers.yaml
custom:
  base_url: ${CUSTOM_LLM_BASE_URL}
  api_key: ${CUSTOM_LLM_API_KEY}
```

With default values:

```yaml
database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
```

---

## Configuration Priority

From highest to lowest:

1. **Environment variables** (runtime)
2. **`.env` file** (secrets)
3. **Environment YAML** (`dev.yaml`, `prod.yaml`)
4. **Base YAML** (`providers.yaml`, `paths.yaml`)
5. **Pydantic defaults** (`settings.py`)

---

## Usage Examples

### 1. Switch LLM Provider

**Option A - Via `.env`:**
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

**Option B - Via `providers.yaml`:**
```yaml
llm:
  default_provider: ollama
```

### 2. Switch Vector Database

```env
VECTORDB_PROVIDER=chromadb
```

### 3. Add New Provider

1. Add to `providers.yaml`:
```yaml
llm:
  providers:
    my_provider:
      model: my-model
      base_url: http://my-api
```

2. Implement provider class in `src/infrastructure/llm/providers/`

3. Register in `get_llm_manager()`

---

## Validation

Configuration is validated at startup:

```python
from config import settings

# Pydantic validates all settings
# Invalid config raises early

# Check current config
python -c "from config.settings import settings; print(settings.model_dump())"
```

---

## Best Practices

### DO:
- ✅ Keep secrets in `.env` (gitignored)
- ✅ Use environment YAML for env-specific settings
- ✅ Use `${VAR}` interpolation for dynamic values
- ✅ Validate config at startup

### DON'T:
- ❌ Hardcode secrets in YAML or Python
- ❌ Commit `.env` files to git
- ❌ Mix secrets and config in same file
- ❌ Use different config patterns per module
