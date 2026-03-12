import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import gradio as gr
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))

from rebuttal_service import init_llm_client, rebuttal_service
from tools import convert_pdf_to_core_markdown_mistral, fetch_openreview_reviews_markdown


def _noop(self, app: FastAPI):
    pass


gr.blocks.Blocks._add_health_routes = _noop


_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(_CURRENT_DIR, "gradio_uploads")
os.makedirs(SAVE_DIR, exist_ok=True)


PROVIDER_CONFIGS = {
    "OpenRouter": {
        "provider_key": "openrouter",
        "env_var": "OPENROUTER_API_KEY",
        "label": "OpenRouter API Key",
        "placeholder": "sk-or-v1-...",
    },
    "Qwen (DashScope)": {
        "provider_key": "qwen",
        "env_var": "QWEN_API_KEY",
        "label": "Qwen API Key",
        "placeholder": "sk-...",
    },
    "DeepSeek": {
        "provider_key": "deepseek",
        "env_var": "DEEPSEEK_API_KEY",
        "label": "DeepSeek API Key",
        "placeholder": "sk-...",
    },
    "OpenAI": {
        "provider_key": "openai",
        "env_var": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "placeholder": "sk-...",
    },
    "Gemini": {
        "provider_key": "gemini",
        "env_var": "GEMINI_API_KEY",
        "label": "Gemini API Key",
        "placeholder": "AIza...",
    },
    "ZhiPu (GLM)": {
        "provider_key": "zhipu",
        "env_var": "ZHIPUAI_API_KEY",
        "label": "ZhiPu API Key",
        "placeholder": "...",
    },
}

MODEL_CHOICES_BY_PROVIDER = {
    "OpenRouter": {
        "Gemini 3 Flash": "google/gemini-3-flash-preview",
        "Grok 4.1 Fast": "x-ai/grok-4.1-fast",
        "GPT-5 Mini": "openai/gpt-5-mini",
        "DeepSeek V3.2": "deepseek/deepseek-chat-v3.2",
        "Other models": "custom",
    },
    "Qwen (DashScope)": {
        "Qwen-Turbo": "qwen-turbo",
        "Qwen-Plus": "qwen-plus",
        "Qwen-Max": "qwen-max",
        "Other models": "custom",
    },
    "DeepSeek": {
        "DeepSeek Chat": "deepseek-chat",
        "DeepSeek Reasoner": "deepseek-reasoner",
        "Other models": "custom",
    },
    "OpenAI": {
        "GPT-5.2": "gpt-5.2",
        "GPT-5 Mini": "gpt-5-mini",
        "Other models": "custom",
    },
    "Gemini": {
        "Gemini-3.1-Pro": "gemini-3.1-pro-preview",
        "Gemini-3-Flash": "models/gemini-3-flash-preview",
        "Other models": "custom",
    },
    "ZhiPu (GLM)": {
        "GLM-4.7": "glm-4.7",
        "Other models": "custom",
    },
}


def get_api_key_for_provider(provider: str) -> str:
    config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["OpenRouter"])
    return os.environ.get(config["env_var"], "")


def get_default_model_for_provider(provider: str) -> str:
    models = MODEL_CHOICES_BY_PROVIDER.get(provider, MODEL_CHOICES_BY_PROVIDER["OpenRouter"])
    for k in models.keys():
        if k != "Other models":
            return k
    return list(models.keys())[0]


def _extract_paths(file_obj: Any) -> List[str]:
    if file_obj is None:
        return []

    items = file_obj if isinstance(file_obj, list) else [file_obj]
    out: List[str] = []

    for item in items:
        if item is None:
            continue
        path = ""
        if isinstance(item, (str, Path)):
            path = str(item)
        elif isinstance(item, dict):
            path = str(item.get("name", "") or item.get("path", ""))
        elif hasattr(item, "name"):
            path = str(item.name)

        if path and os.path.exists(path):
            out.append(path)

    return out


def _copy_files(src_paths: List[str], dst_dir: str, prefix: str) -> List[str]:
    os.makedirs(dst_dir, exist_ok=True)
    copied: List[str] = []
    for i, src in enumerate(src_paths, start=1):
        base = os.path.basename(src)
        if not base.lower().endswith(".md"):
            base = f"{base}.md"
        dst = os.path.join(dst_dir, f"{prefix}_{i}_{base}")
        shutil.copy(src, dst)
        copied.append(dst)
    return copied


def _copy_one_file(src_path: str, dst_path: str) -> str:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy(src_path, dst_path)
    return dst_path


def _format_stage1_reviewer_summaries(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "(empty)"
    lines: List[str] = []
    for row in rows:
        rid = row.get("reviewer_id", "R?")
        lines.append(f"### {rid}")
        lines.append(row.get("summary", ""))
        points = row.get("main_points", []) or []
        if points:
            lines.append("- Main points:")
            for p in points:
                lines.append(f"  - {p}")
        reqs = row.get("requested_experiments", []) or []
        if reqs:
            lines.append("- Requested experiments:")
            for r in reqs:
                lines.append(f"  - {r}")
        lines.append("")
    return "\n".join(lines)


def _format_stage1_tasks(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "(No supplemental experiments were generated.)"
    lines: List[str] = []
    for row in rows:
        lines.append(f"## {row.get('exp_id', 'EXP?')}")
        lines.append(f"- Related reviewers: {', '.join(row.get('related_reviewers', []) or [])}")
        lines.append(f"- Goal: {row.get('goal', '')}")
        lines.append(f"- How to run: {row.get('how_to_run', '')}")
        lines.append("- Coding prompt (copy to Codex/Claude Code):")
        lines.append("```md")
        lines.append(row.get("coding_prompt_md", ""))
        lines.append("```")
        hint = row.get("expected_result_hint", "")
        if hint:
            lines.append(f"- Expected trend hint: {hint}")
        lines.append("")
    return "\n".join(lines)


def _format_comparison_needs(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "(No explicit comparison-paper requirements were detected.)"
    lines: List[str] = []
    for row in rows:
        status = row.get("status", "missing")
        title = row.get("paper_title", "")
        reviewers = ", ".join(row.get("mentioned_by_reviewer", []) or [])
        reason = row.get("reason", "")
        lines.append(f"- [{status.upper()}] {title}")
        lines.append(f"  - Mentioned by: {reviewers}")
        if reason:
            lines.append(f"  - Reason: {reason}")
        provided = row.get("provided_md_path", "")
        if provided:
            lines.append(f"  - Provided md: {os.path.basename(provided)}")
    return "\n".join(lines)


def _draft_counter_text(char_count: int, note: str = "") -> str:
    status = "OK" if char_count <= 5000 else "OVER"
    base = f"Characters: {char_count}/5000 ({status})"
    if note:
        return f"{base}\n\nCompression note: {note}"
    return base


def _session_dir(session_id: str) -> str:
    return os.path.join(SAVE_DIR, session_id)


def _resolve_session_id(session_state, session_id_text: str) -> str:
    if session_state and session_state.get("session_id"):
        return session_state["session_id"]
    return (session_id_text or "").strip()


def on_provider_change(provider: str):
    config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["OpenRouter"])
    env_key = get_api_key_for_provider(provider)
    model_choices = MODEL_CHOICES_BY_PROVIDER.get(provider, MODEL_CHOICES_BY_PROVIDER["OpenRouter"])
    default_model = get_default_model_for_provider(provider)
    return (
        gr.update(
            label=config["label"],
            placeholder=f"Please enter your API Key ({config['placeholder']})",
            value=env_key,
            info="API key is only used in this session." + (" (Loaded from environment/.env)" if env_key else ""),
        ),
        gr.update(choices=list(model_choices.keys()), value=default_model),
    )


def toggle_custom_model(choice: str):
    return gr.update(visible=(choice == "Other models"))


def _init_client(provider_choice: str, api_key: str, model_choice: str, custom_model: str) -> str:
    if not api_key or not api_key.strip():
        raise ValueError("Please provide API key.")

    provider_config = PROVIDER_CONFIGS.get(provider_choice, PROVIDER_CONFIGS["OpenRouter"])
    provider_key = provider_config["provider_key"]
    model_choices = MODEL_CHOICES_BY_PROVIDER.get(provider_choice, MODEL_CHOICES_BY_PROVIDER["OpenRouter"])

    if model_choice == "Other models":
        if not custom_model or not custom_model.strip():
            raise ValueError("Please provide custom model name.")
        selected_model = custom_model.strip()
    else:
        selected_model = model_choices.get(model_choice, list(model_choices.values())[0])

    init_llm_client(api_key=api_key.strip(), provider=provider_key, model=selected_model)
    return selected_model


def run_stage1(
    paper_file,
    review_file,
    openreview_url,
    comparison_files,
    provider_choice,
    api_key,
    model_choice,
    custom_model,
):
    try:
        paper_paths = _extract_paths(paper_file)
        review_paths = _extract_paths(review_file)
        comparison_paths = _extract_paths(comparison_files)

        if len(paper_paths) != 1:
            raise ValueError("Please upload exactly one paper file (.md or .pdf).")

        paper_src = paper_paths[0]
        paper_ext = os.path.splitext(paper_src)[1].lower()
        if paper_ext not in [".md", ".pdf"]:
            raise ValueError("Paper file must be .md or .pdf.")

        openreview_url = (openreview_url or "").strip()
        has_review_file = len(review_paths) == 1
        has_openreview = bool(openreview_url)
        if has_review_file == has_openreview:
            raise ValueError("Please provide exactly one: a reviews markdown file OR an OpenReview forum link.")

        selected_model = _init_client(provider_choice, api_key, model_choice, custom_model)

        session_id = str(uuid.uuid4())[:8]
        session_dir = _session_dir(session_id)
        stage1_input_dir = os.path.join(session_dir, "inputs", "stage1")
        paper_dir = os.path.join(stage1_input_dir, "paper")
        reviews_dir = os.path.join(stage1_input_dir, "reviews")
        comparison_dir = os.path.join(stage1_input_dir, "comparisons")

        saved_paper_md = os.path.join(paper_dir, "paper.md")
        if paper_ext == ".md":
            _copy_one_file(paper_src, saved_paper_md)
        else:
            saved_pdf = _copy_one_file(paper_src, os.path.join(paper_dir, "paper_source.pdf"))
            paper_md = convert_pdf_to_core_markdown_mistral(saved_pdf)
            os.makedirs(paper_dir, exist_ok=True)
            with open(saved_paper_md, "w", encoding="utf-8") as f:
                f.write(paper_md)

        saved_review_md = os.path.join(reviews_dir, "reviews.md")
        if has_openreview:
            reviews_md = fetch_openreview_reviews_markdown(openreview_url)
            os.makedirs(reviews_dir, exist_ok=True)
            with open(saved_review_md, "w", encoding="utf-8") as f:
                f.write(reviews_md)
        else:
            _copy_one_file(review_paths[0], saved_review_md)

        saved_comparisons = _copy_files(comparison_paths, comparison_dir, "comparison")

        rebuttal_service.create_session(
            session_id=session_id,
            paper_path=saved_paper_md,
            review_path=saved_review_md,
            comparison_paths=saved_comparisons,
        )
        stage1 = rebuttal_service.run_stage1_analysis(session_id)

        reviewer_ids = [x.get("reviewer_id", "") for x in stage1.get("reviewer_summaries", []) if x.get("reviewer_id")]

        status = (
            f"Stage1 complete. Session: `{session_id}`\n\n"
            f"Model: `{selected_model}`\n"
            f"Reviewers detected: {', '.join(reviewer_ids) if reviewer_ids else 'R1'}\n"
            f"Logs: `{os.path.join(session_dir, 'logs')}`"
        )

        return (
            {"session_id": session_id},
            status,
            stage1.get("overall_summary", ""),
            _format_stage1_reviewer_summaries(stage1.get("reviewer_summaries", [])),
            _format_stage1_tasks(stage1.get("experiment_tasks", [])),
            _format_comparison_needs(stage1.get("comparison_needs", [])),
            gr.update(choices=reviewer_ids, value=(reviewer_ids[0] if reviewer_ids else None)),
            "",
            _draft_counter_text(0),
            "",
            "",
            session_id,
        )
    except Exception as e:
        return (
            None,
            f"Stage1 failed: {e}",
            "",
            "",
            "",
            "",
            gr.update(choices=[], value=None),
            "",
            _draft_counter_text(0),
            "",
            "",
            "",
        )


def load_session(session_id: str):
    try:
        session_id = (session_id or "").strip()
        if not session_id:
            raise ValueError("Please provide Session ID.")

        session = rebuttal_service.restore_session_from_disk(session_id)
        if not session:
            raise ValueError(f"Session `{session_id}` not found on disk.")

        has_stage1 = bool(session.stage1_data)
        has_stage2 = bool(session.stage2_drafts)

        reviewer_ids = rebuttal_service.get_reviewer_ids(session_id)
        first_id = reviewer_ids[0] if reviewer_ids else None
        first = rebuttal_service.get_reviewer_draft(session_id, first_id) if first_id else None

        text = first.text if first else ""
        counter = _draft_counter_text(first.char_count, first.compression_note) if first else _draft_counter_text(0)
        auto = ""
        if first:
            auto = "[AUTO] used in this reviewer block." if first.used_auto_results else "No [AUTO] result used in this reviewer block."

        status = (
            f"Session loaded: `{session_id}`\n\n"
            f"- has_stage1: `{has_stage1}`\n"
            f"- has_stage2: `{has_stage2}`\n"
            f"- reviewers: `{', '.join(reviewer_ids) if reviewer_ids else 'N/A'}`\n"
            f"- logs: `{os.path.join(session.session_dir, 'logs')}`"
        )

        return (
            {"session_id": session_id},
            status,
            gr.update(choices=reviewer_ids, value=first_id),
            text,
            counter,
            auto,
            rebuttal_service.build_all_drafts_markdown(session_id) if has_stage2 else "",
        )
    except Exception as e:
        return (
            None,
            f"Load session failed: {e}",
            gr.update(choices=[], value=None),
            "",
            _draft_counter_text(0),
            "",
            "",
        )


def run_stage2(experiment_result_files, additional_comparison_files, session_state, session_id_text):
    try:
        session_id = _resolve_session_id(session_state, session_id_text)
        if not session_id:
            raise ValueError("Please provide Session ID (run Stage1 or load session).")

        rebuttal_service.restore_session_from_disk(session_id)
        session_dir = _session_dir(session_id)

        exp_paths = _extract_paths(experiment_result_files)
        add_comp_paths = _extract_paths(additional_comparison_files)

        run_tag = time.strftime("%Y%m%d_%H%M%S")
        stage2_input_dir = os.path.join(session_dir, "inputs", f"stage2_{run_tag}")
        saved_exp = _copy_files(exp_paths, stage2_input_dir, "experiment")
        saved_add_comp = _copy_files(add_comp_paths, stage2_input_dir, "comparison")

        drafts = rebuttal_service.run_stage2_rebuttal(
            session_id=session_id,
            experiment_result_paths=saved_exp,
            additional_comparison_paths=saved_add_comp,
        )

        reviewer_ids = sorted(drafts.keys(), key=lambda x: int(x[1:]) if x.startswith("R") and x[1:].isdigit() else 10**9)
        if not reviewer_ids:
            raise RuntimeError("No reviewer drafts were generated.")

        first = drafts[reviewer_ids[0]]
        status = (
            f"Stage2 complete. Session: `{session_id}`\n"
            f"Generated {len(reviewer_ids)} reviewer rebuttal blocks.\n"
            "Each block is enforced to <= 5000 characters.\n"
            f"Logs: `{os.path.join(session_dir, 'logs')}`"
        )

        return (
            status,
            gr.update(choices=reviewer_ids, value=reviewer_ids[0]),
            first.text,
            _draft_counter_text(first.char_count, first.compression_note),
            "[AUTO] used in this reviewer block." if first.used_auto_results else "No [AUTO] result used in this reviewer block.",
            rebuttal_service.build_all_drafts_markdown(session_id),
        )
    except Exception as e:
        return (
            f"Stage2 failed: {e}",
            gr.update(choices=[], value=None),
            "",
            _draft_counter_text(0),
            "",
            "",
        )


def on_reviewer_change(reviewer_id: str, session_state, session_id_text):
    if not reviewer_id:
        return "", _draft_counter_text(0), ""

    session_id = _resolve_session_id(session_state, session_id_text)
    if not session_id:
        return "", _draft_counter_text(0), ""

    draft = rebuttal_service.get_reviewer_draft(session_id, reviewer_id)
    if not draft:
        return "", _draft_counter_text(0), ""

    auto_info = "[AUTO] used in this reviewer block." if draft.used_auto_results else "No [AUTO] result used in this reviewer block."
    return draft.text, _draft_counter_text(draft.char_count, draft.compression_note), auto_info


def apply_edit(reviewer_id: str, rebuttal_text: str, session_state, session_id_text):
    try:
        if not reviewer_id:
            raise ValueError("Please choose a reviewer.")
        session_id = _resolve_session_id(session_state, session_id_text)
        if not session_id:
            raise ValueError("Session is missing. Run Stage1 or load session first.")

        updated = rebuttal_service.finalize_reviewer_rebuttal(session_id, reviewer_id, rebuttal_text)

        auto_info = "[AUTO] used in this reviewer block." if updated.used_auto_results else "No [AUTO] result used in this reviewer block."
        return (
            updated.text,
            _draft_counter_text(updated.char_count, updated.compression_note),
            auto_info,
            rebuttal_service.build_all_drafts_markdown(session_id),
        )
    except Exception as e:
        return rebuttal_text, _draft_counter_text(len(rebuttal_text or "")), f"Edit apply failed: {e}", ""


def download_all_drafts(all_drafts_text: str):
    if not all_drafts_text:
        return gr.update()
    with tempfile.NamedTemporaryFile(mode="w", suffix="_all_rebuttals.md", delete=False, encoding="utf-8") as f:
        f.write("# Rebuttal Drafts By Reviewer\n\n")
        f.write(all_drafts_text)
        return gr.update(value=f.name, visible=True)


APP_CSS = """
#char-counter {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
}
#stage-status {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
}
"""


with gr.Blocks(title="Paper2Rebuttal Personal") as demo:
    session_state = gr.State(None)

    gr.Markdown(
        """
# Paper2Rebuttal (Personal Two-Stage Mode)

- Stage1: Upload `paper.md` + `reviews.md` (+ optional comparison-paper `.md` files), then get:
  - overall reviewer opinion summary
  - per-reviewer summary
  - supplemental experiment plan (copyable coding prompts)
  - missing comparison-paper list
- Stage2: Upload experiment-result `.md` (optional) and additional comparison `.md` (optional), then generate final rebuttal blocks per reviewer (English, each <= 5000 chars).
- If results are missing, the system generates reasonable placeholders with `[AUTO]` markers.

Stage1 inputs:
- Paper: `.md` or `.pdf` (PDF will be converted to Markdown via Mistral OCR, images dropped, only Abstract/Methods/Experiments kept)
- Reviews: upload `.md` OR provide an OpenReview forum link (Official Review + Meta Review are fetched)
"""
    )

    initial_provider = "Gemini"

    with gr.Group():
        gr.Markdown("## API & Model")
        with gr.Row():
            provider_choice = gr.Dropdown(
                label="LLM Provider",
                choices=list(PROVIDER_CONFIGS.keys()),
                value=initial_provider,
            )
            api_key_input = gr.Textbox(
                label=PROVIDER_CONFIGS[initial_provider]["label"],
                placeholder=f"Please enter your API Key ({PROVIDER_CONFIGS[initial_provider]['placeholder']})",
                value=get_api_key_for_provider(initial_provider),
                type="password",
            )

        with gr.Row():
            model_choice = gr.Dropdown(
                label="Model",
                choices=list(MODEL_CHOICES_BY_PROVIDER[initial_provider].keys()),
                value=get_default_model_for_provider(initial_provider),
                scale=2,
            )
            custom_model_input = gr.Textbox(
                label="Custom model name",
                placeholder="Enter custom model id",
                visible=False,
                scale=3,
            )

        provider_choice.change(
            fn=on_provider_change,
            inputs=[provider_choice],
            outputs=[api_key_input, model_choice],
        )
        model_choice.change(
            fn=toggle_custom_model,
            inputs=[model_choice],
            outputs=[custom_model_input],
        )

    with gr.Tab("Stage1: Analyze Reviews"):
        with gr.Row():
            paper_input = gr.File(label="Paper (.md / .pdf)", file_types=[".md", ".pdf"], file_count="single")
            review_input = gr.File(label="Reviews Markdown (.md, optional if OpenReview link is provided)", file_types=[".md"], file_count="single")
        openreview_url = gr.Textbox(
            label="OpenReview forum link (optional, instead of uploading reviews.md)",
            placeholder="https://openreview.net/forum?id=...",
        )
        comparison_input = gr.File(
            label="Comparison Papers Markdown (.md, optional, multiple)",
            file_types=[".md"],
            file_count="multiple",
        )

        stage1_btn = gr.Button("Run Stage1", variant="primary")
        stage1_status = gr.Markdown(elem_id="stage-status")

        overall_summary = gr.Textbox(label="Overall Reviewer Opinion Summary", lines=6)
        reviewer_summary = gr.Markdown(label="Per-Reviewer Summary")
        experiment_tasks = gr.Textbox(label="Supplemental Experiment Plan (copy-ready)", lines=16)
        comparison_needs = gr.Markdown(label="Comparison Paper Needs")

    with gr.Tab("Stage2: Generate Final Rebuttal"):
        with gr.Row():
            session_id_input = gr.Textbox(
                label="Session ID (for resume)",
                placeholder="Paste the session id here (e.g., 1a2b3c4d)",
            )
            load_session_btn = gr.Button("Load Session", variant="secondary")

        with gr.Row():
            exp_result_input = gr.File(
                label="Experiment Results Markdown (.md, optional, multiple)",
                file_types=[".md"],
                file_count="multiple",
            )
            stage2_comparison_input = gr.File(
                label="Additional Comparison Papers (.md, optional, multiple)",
                file_types=[".md"],
                file_count="multiple",
            )

        stage2_btn = gr.Button("Run Stage2", variant="primary")
        stage2_status = gr.Markdown(elem_id="stage-status")

        reviewer_selector = gr.Dropdown(label="Reviewer", choices=[], value=None)
        rebuttal_editor = gr.Textbox(label="Rebuttal (editable)", lines=18)
        char_counter = gr.Markdown(value=_draft_counter_text(0), elem_id="char-counter")
        auto_info = gr.Markdown("")

        with gr.Row():
            apply_btn = gr.Button("Apply Edit + Enforce <=5000", variant="secondary")

        all_drafts_output = gr.Textbox(label="All Reviewer Drafts", lines=18)
        download_btn = gr.Button("Download All Drafts", variant="secondary")
        download_file = gr.File(label="Download", visible=False)

    stage1_btn.click(
        fn=run_stage1,
        inputs=[
            paper_input,
            review_input,
            openreview_url,
            comparison_input,
            provider_choice,
            api_key_input,
            model_choice,
            custom_model_input,
        ],
        outputs=[
            session_state,
            stage1_status,
            overall_summary,
            reviewer_summary,
            experiment_tasks,
            comparison_needs,
            reviewer_selector,
            rebuttal_editor,
            char_counter,
            auto_info,
            all_drafts_output,
            session_id_input,
        ],
    )

    stage2_btn.click(
        fn=run_stage2,
        inputs=[exp_result_input, stage2_comparison_input, session_state, session_id_input],
        outputs=[stage2_status, reviewer_selector, rebuttal_editor, char_counter, auto_info, all_drafts_output],
    )

    load_session_btn.click(
        fn=load_session,
        inputs=[session_id_input],
        outputs=[session_state, stage2_status, reviewer_selector, rebuttal_editor, char_counter, auto_info, all_drafts_output],
    )

    reviewer_selector.change(
        fn=on_reviewer_change,
        inputs=[reviewer_selector, session_state, session_id_input],
        outputs=[rebuttal_editor, char_counter, auto_info],
    )

    apply_btn.click(
        fn=apply_edit,
        inputs=[reviewer_selector, rebuttal_editor, session_state, session_id_input],
        outputs=[rebuttal_editor, char_counter, auto_info, all_drafts_output],
    )

    download_btn.click(
        fn=download_all_drafts,
        inputs=[all_drafts_output],
        outputs=[download_file],
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Paper2Rebuttal Personal Two-Stage App")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=7860, help="Server port")
    parser.add_argument("--share", action="store_true", help="Create public link")
    args = parser.parse_args()

    print(f"Starting app on http://{args.host}:{args.port}")
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        theme=gr.themes.Soft(),
        css=APP_CSS,
    )
