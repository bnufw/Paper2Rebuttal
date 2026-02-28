# Repository Guidelines

## Project Structure & Module Organization
This repository is a lightweight Python application centered on a Gradio UI and a multi-agent rebuttal pipeline.

- `app.py`: entry point for the web app and workflow orchestration.
- `rebuttal_service.py`: core session/process logic for issue extraction, strategy generation, and rebuttal flow.
- `llm.py`: provider routing and LLM client abstraction.
- `arxiv.py`: arXiv search/download and reference acquisition logic.
- `tools.py`: shared helpers (prompt loading, PDF-to-markdown conversion, utility functions).
- `prompts/`: YAML prompts for each agent stage.
- `assets/`: static resources.

Generated runtime data (for example `gradio_uploads/`, `arxiv_papers/`, `sessions/`) should stay out of commits.

## Build, Test, and Development Commands
- `conda create -n rebuttal python=3.10 && conda activate rebuttal`: create the recommended environment.
- `pip install -r requirements.txt`: install dependencies.
- `cp .env.example .env`: initialize environment configuration.
- `python app.py --port 8080`: run locally on CPU.
- `python app.py --device cuda --port 8080`: run with CUDA for faster Docling parsing.

No Makefile or npm-based workflow is used in this project.

## Coding Style & Naming Conventions
- Follow Python conventions: 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused; add logic to existing files unless a new module is clearly justified.
- Prefer concise docstrings/comments only where behavior is non-obvious.
- Keep prompt files in `prompts/` as stage-scoped YAML (for example `strategy_reviewer.yaml`).

## Testing Guidelines
There is currently no dedicated automated test suite (`tests/` is not present). For contributions:
- Add focused tests when introducing non-trivial logic changes.
- At minimum, run a local smoke check by starting `app.py` and validating one end-to-end session.
- If adding tests, use `test_*.py` naming to align with Python tooling conventions.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects (for example `add retry with exponential backoff for API calls`) and occasional `[update] ...` maintenance commits.

- Use clear, scoped commit messages: `feat:`, `fix:`, or concise imperative text.
- PRs should include: purpose, key changes, verification steps, and any UI-impact screenshots.
- Link related issues/PRs when available (for example `(#5)` style references).
- Avoid mixing refactors with behavior changes in one PR.

## Security & Configuration Tips
- Never commit `.env` or API keys.
- Prefer provider-specific environment variables from `.env.example`.
- Keep large downloaded artifacts and temporary session files untracked per `.gitignore`.
