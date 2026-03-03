# Stack Research

**Domain:** Personal rebuttal co-pilot extension in an existing Python Gradio app  
**Researched:** 2026-03-03  
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10.x | Main runtime | Already the project baseline; lowest migration risk for a subsequent milestone. |
| Gradio | 6.2.x (keep current pin) | UI workflow + state/event orchestration | Existing app is already Blocks-based; Gradio supports `File`, `Textbox`, `Markdown`, `State`, and queue/event chaining needed for MD-first + reviewer-by-reviewer flows. |
| Pydantic | `>=2.8,<3` | Structured output validation | Best fit for converting LLM outputs into strict typed objects (experiment plans, comparison claims, per-reviewer rebuttal units) with explicit validation errors. |
| Docling | 2.30.x (keep current pin) | PDF->Markdown fallback path | Keeps compatibility with current pipeline while enabling MD-first as primary path and PDF parsing as optional fallback. |
| OpenAI-compatible SDK layer (`openai` + current `llm.py`) | `openai==2.14.0` + existing wrapper | Model routing across providers | Keeps current provider-agnostic architecture; add structured-output mode only where provider/model supports it, with Pydantic fallback parse loop. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| markdown-it-py | `>=3.0,<4` | Markdown tokenization/parsing | Use for MD-first ingestion when you need stable heading/list/code-block-aware parsing (paper markdown, reviewer markdown, comparison-paper markdown). |
| PyYAML | `>=6.0` (already present) | Prompt and config loading | Keep for prompt templates and stage-scoped prompt composition. |
| Python stdlib `len()` + deterministic budget utility | Built-in | Character-budget enforcement | Use as the source of truth for `<=5000 chars per reviewer` checks; keep it character-based, not token-based. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Regression tests for parser/budget logic | Add focused tests for reviewer split, markdown ingest, and budget enforcer loops. |
| ruff | Fast linting/format checks | Keep style concise and prevent low-signal drift during iterative prompt/logic edits. |

## Installation

```bash
# Core additions for this milestone
pip install "pydantic>=2.8,<3" "markdown-it-py>=3.0,<4"

# Dev dependencies
pip install "pytest>=8,<9" "ruff>=0.6,<1"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Pydantic v2 schema validation | Ad-hoc `json.loads()` + regex fixes | Only for throwaway prototypes; not suitable for reliable per-reviewer structured pipelines. |
| markdown-it-py token parsing | Plain regex markdown splitting | Only for very short controlled text; breaks quickly on nested markdown and code blocks. |
| Existing custom multi-agent orchestration (`rebuttal_service.py`) | Full framework migration (LangChain/LlamaIndex workflow rewrite) | Only if future scope becomes multi-tenant/tool-calling platform; overkill for this milestone. |
| Character-based enforcement with `len()` | Token-based budget via tokenizer | Only when requirement is token cap. Here requirement is explicit character cap, so token budgeting is misaligned. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Full orchestration rewrite to heavy agent frameworks | High migration risk and regression risk; no direct value for single-user incremental extension. | Keep current pipeline, add focused stages/utilities. |
| Token count as final budget metric | Requirement is reviewer-level character cap (`<=5000`), not token cap. | Deterministic `len()` checks and retry-compress loop. |
| Auto web retrieval for comparison papers | Conflicts with project constraint: comparison must use user-provided markdown papers. | Local ingestion of user-supplied comparison markdown files only. |
| Regex-only markdown parser for core logic | Fragile for headings/lists/code fences and mixed formatting. | markdown-it-py token stream + explicit section mapping. |

## Stack Patterns by Variant

**If MD-first input is available (recommended default):**
- Use `gr.Textbox(lines=...)` + optional `gr.File(file_types=[".md", ".txt"])` for direct markdown ingestion.
- Parse markdown with `markdown-it-py`, then map to structured Pydantic models for downstream agents.
- Because this avoids avoidable PDF parse latency and preserves user-edited structure.

**If user only has PDF (fallback path):**
- Use existing Docling conversion (`DocumentConverter` -> `export_to_markdown()`), then feed into the same MD-first parser path.
- Because this keeps one downstream normalization path and reduces branching bugs.

**If provider/model supports structured outputs:**
- Use provider-native JSON schema mode where available, then still validate with Pydantic.
- Because native constrained decoding lowers malformed outputs, while local validation keeps provider-independent safety.

**If provider/model does not support structured outputs:**
- Use current prompting approach + Pydantic parse/repair/retry loop.
- Because it preserves compatibility with existing multi-provider routing.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `gradio==6.2.0` | Python 3.10 runtime in this repo | Current project pin; supports `File`, `Textbox`, `Markdown`, `State`, and queue/event chaining used by this app pattern. |
| `fastapi==0.128.0` | `pydantic>=2,<3` | Keep Pydantic in v2 line to align with current modern FastAPI ecosystem usage. |
| `openai==2.14.0` | Pydantic v2 schemas (optional) | Useful for structured output pathways when supported by selected provider/model. |
| `docling==2.30.0` | Existing `DOCLING_DEVICE`-controlled runtime | Keep current pin for non-regressive behavior; use as fallback when markdown is not supplied directly. |

## Key Choice Confidence

| Choice | Confidence | Why |
|--------|------------|-----|
| Keep Gradio Blocks architecture and extend incrementally | HIGH | Directly matches existing codebase and milestone constraint of non-regressive extension. |
| Add Pydantic for structured intermediate artifacts | HIGH | Official docs and ecosystem usage strongly support robust validation/error reporting for untrusted/LLM-generated data. |
| Adopt markdown-it-py for MD-first parsing | MEDIUM | Strong technical fit and CommonMark-oriented parser design; still a net-new dependency in this repo. |
| Keep Docling as fallback, not primary path | HIGH | Matches MD-first requirement while preserving current working PDF workflow. |
| Use character-count (`len`) enforcement for per-reviewer cap | HIGH | Requirement is explicitly character-based; Python built-in behavior is deterministic and simple. |
| Use provider-native structured outputs only as optional acceleration | MEDIUM | Capability depends on selected provider/model; repository is multi-provider and must retain fallback path. |

## Sources

- Context7 `/gradio-app/gradio` — components (`File`, `Textbox`, `Markdown`), Blocks chaining/state patterns.  
- Context7 `/pydantic/pydantic` — `BaseModel` validation, strict mode, field constraints, validation errors.  
- Context7 `/docling-project/docling` — `DocumentConverter`, PDF pipeline options, markdown export.
- https://www.gradio.app/docs/gradio/file — file input types and usage patterns (official docs).  
- https://www.gradio.app/docs/gradio/textbox — multiline input and `max_length` support (official docs).  
- https://www.gradio.app/docs/gradio/markdown — markdown rendering behavior (official docs).  
- https://www.gradio.app/guides/state-in-blocks — session-scoped state patterns (official docs).  
- https://www.gradio.app/guides/queuing — queue/concurrency model for long-running events (official docs).  
- https://docs.pydantic.dev/latest/concepts/models/ — model validation APIs (`model_validate`, `model_validate_json`).  
- https://docs.pydantic.dev/latest/concepts/strict_mode/ — strict mode behavior and tradeoffs.  
- https://docs.pydantic.dev/latest/concepts/fields/ — constraints like `max_length`, aliases, typed fields.  
- https://docling-project.github.io/docling/getting_started/quickstart/ — conversion to markdown example.  
- https://docling-project.github.io/docling/reference/document_converter/ — core converter API.  
- https://docling-project.github.io/docling/reference/pipeline_options/ — PDF pipeline options and runtime controls.  
- https://developers.openai.com/api/docs/guides/structured-outputs/ — schema-constrained output option and SDK-level structured patterns.  
- https://docs.python.org/3/library/functions.html#len — canonical behavior of `len()` used for character-budget enforcement.

---
*Stack research for: Personal rebuttal co-pilot extension in existing Gradio app*  
*Researched: 2026-03-03*
