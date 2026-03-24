import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from llm import LLMClient, TokenUsageTracker
from tools import (
    _fix_json_escapes,
    download_pdf_to_local,
    load_prompt,
    resolve_comparison_paper_candidate,
)


_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_BASE_DIR = os.path.join(_CURRENT_DIR, "gradio_uploads")
os.makedirs(SESSIONS_BASE_DIR, exist_ok=True)


token_tracker = TokenUsageTracker()
llm_client: Optional[LLMClient] = None


def init_llm_client(api_key: str, provider: str = "openrouter", model: str = "google/gemini-3-flash-preview") -> LLMClient:
    global llm_client
    llm_client = LLMClient(
        provider=provider,
        api_key=api_key,
        default_model=model,
        site_url="https://rebuttal-assistant.local",
        site_name="Rebuttal Assistant",
        token_tracker=token_tracker,
    )
    return llm_client


def get_llm_client() -> LLMClient:
    if llm_client is None:
        raise RuntimeError("LLM client not initialized. Please configure API Key first.")
    return llm_client


@dataclass
class ReviewerBlock:
    reviewer_id: str
    raw_review_md: str
    issue_summary_md: str = ""


@dataclass
class ExperimentTask:
    exp_id: str
    related_reviewers: List[str]
    goal: str
    how_to_run: str
    coding_prompt_md: str
    expected_result_hint: str


@dataclass
class ReviewerResponsePlan:
    reviewer_id: str
    main_position_en: str
    must_answer_points_cn: List[str]
    planned_evidence: List[str]
    open_tbd_items: List[str]


@dataclass
class ComparisonNeed:
    paper_title: str
    mentioned_by_reviewer: List[str]
    reason: str
    reviewer_scope: str = "explicit"
    direct_url: str = ""
    search_query: str = ""
    source_hint: str = "unknown"
    provided_file_id: str = ""
    provided_source_path: str = ""
    provided_source_type: str = ""
    retrieval_provider: str = ""
    resolved_url: str = ""
    retrieval_note: str = ""
    status: str = "missing"


@dataclass
class RebuttalDraft:
    reviewer_id: str
    text: str
    char_count: int
    used_auto_results: bool
    is_within_limit: bool
    compression_note: str = ""


@dataclass
class SessionState:
    session_id: str
    session_dir: str
    paper_path: str
    review_path: str
    comparison_paths: List[str] = field(default_factory=list)

    paper_md: str = ""
    review_md: str = ""
    reviewers: List[ReviewerBlock] = field(default_factory=list)

    stage1_data: Dict[str, Any] = field(default_factory=dict)
    stage2_drafts: Dict[str, RebuttalDraft] = field(default_factory=dict)


class RebuttalService:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}

    def restore_session_from_disk(self, session_id: str) -> Optional[SessionState]:
        existing = self.sessions.get(session_id)
        if existing:
            return existing

        session_dir = os.path.join(SESSIONS_BASE_DIR, session_id)
        if not os.path.isdir(session_dir):
            return None

        outputs_dir = os.path.join(session_dir, "outputs")
        os.makedirs(outputs_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "logs"), exist_ok=True)

        meta = self._load_json_safe(os.path.join(outputs_dir, "session_meta.json")) or {}
        paper_path = str(meta.get("paper_path", "") or "")
        review_path = str(meta.get("review_path", "") or "")
        raw_comparisons = meta.get("comparison_paths", []) or []
        comparison_paths = [str(x) for x in raw_comparisons if isinstance(x, str)]

        session = SessionState(
            session_id=session_id,
            session_dir=session_dir,
            paper_path=paper_path,
            review_path=review_path,
            comparison_paths=comparison_paths,
        )

        if paper_path and os.path.exists(paper_path) and not str(paper_path).lower().endswith(".pdf"):
            session.paper_md = self._read_text_safe(paper_path)
        if review_path and os.path.exists(review_path):
            session.review_md = self._read_text_safe(review_path)
            if session.review_md.strip():
                session.reviewers = self._split_reviews_by_reviewer(session.review_md)

        stage1_data = self._load_json_safe(os.path.join(outputs_dir, "stage1_output.json"))
        if isinstance(stage1_data, dict):
            session.stage1_data = stage1_data

        stage2_raw = self._load_json_safe(os.path.join(outputs_dir, "stage2_drafts.json"))
        if isinstance(stage2_raw, dict):
            drafts: Dict[str, RebuttalDraft] = {}
            for rid, item in stage2_raw.items():
                if not isinstance(item, dict):
                    continue
                try:
                    draft = RebuttalDraft(**item)
                except Exception:
                    continue
                key = self._normalize_reviewer_id(draft.reviewer_id) or self._normalize_reviewer_id(str(rid)) or str(rid)
                drafts[key] = draft
            session.stage2_drafts = drafts

        self.sessions[session_id] = session
        self._append_progress(session, "Session restored from disk.")
        return session

    def create_session(
        self,
        session_id: str,
        paper_path: str,
        review_path: str,
        comparison_paths: Optional[List[str]] = None,
    ) -> SessionState:
        session_dir = os.path.join(SESSIONS_BASE_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "outputs"), exist_ok=True)
        os.makedirs(os.path.join(session_dir, "logs"), exist_ok=True)

        session = SessionState(
            session_id=session_id,
            session_dir=session_dir,
            paper_path=paper_path,
            review_path=review_path,
            comparison_paths=comparison_paths or [],
        )
        self.sessions[session_id] = session
        self._save_session_meta(session)
        self._append_progress(session, "Session created.")
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self.sessions.get(session_id)

    def count_chars(self, text: str) -> int:
        normalized = re.sub(r"\[(?i:auto)\]", "", text or "")
        return len(normalized)

    def _paper_is_pdf(self, session: SessionState) -> bool:
        return str(session.paper_path or "").lower().endswith(".pdf")

    def _ensure_paper_loaded(self, session: SessionState) -> None:
        if self._paper_is_pdf(session):
            session.paper_md = ""
            return
        if session.paper_path:
            session.paper_md = self._read_text_safe(session.paper_path)

    def _build_paper_prompt_context(
        self,
        session: SessionState,
        char_limit: Optional[int] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if self._paper_is_pdf(session):
            client = get_llm_client()
            if client.provider != "gemini":
                raise ValueError("This session uses a PDF paper. Please use Gemini for this session.")
            if not client.supports_pdf_attachments():
                raise ValueError("Native Gemini PDF input requires the google.genai backend.")

            pdf_bytes = self._read_binary_safe(session.paper_path)
            if not pdf_bytes:
                raise ValueError("Paper PDF is empty.")

            context_text = (
                "[paper content]\n"
                "The paper is attached as PDF.\n"
                "Use the attached paper PDF. Focus on abstract, method, and experiments. "
                "Ignore related work and appendix unless necessary."
            )
            attachments = [
                {
                    "type": "bytes",
                    "mime_type": "application/pdf",
                    "data": pdf_bytes,
                    "name": os.path.basename(session.paper_path),
                }
            ]
            return context_text, attachments

        self._ensure_paper_loaded(session)
        if not session.paper_md.strip():
            raise ValueError("Paper markdown is empty.")

        paper_text = session.paper_md[:char_limit] if char_limit else session.paper_md
        return f"[paper content]\n```md\n{paper_text}\n```", []

    def _path_source_type(self, path: str) -> str:
        ext = str(path or "").lower()
        if ext.endswith(".pdf"):
            return "pdf"
        if ext.endswith(".md"):
            return "md"
        return "unknown"

    def _build_comparison_items(self, comparison_paths: List[str]) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        for idx, path in enumerate(comparison_paths or [], start=1):
            if not os.path.exists(path):
                continue
            source_type = self._path_source_type(path)
            display_name = os.path.splitext(os.path.basename(path))[0]
            if source_type == "md":
                title = self._extract_title_from_markdown(
                    self._read_text_safe(path),
                    fallback=os.path.basename(path),
                ).strip()
                if title:
                    display_name = title
            items.append(
                {
                    "file_id": f"CMP{idx}",
                    "display_name": display_name,
                    "source_type": source_type,
                    "path": path,
                }
            )
        return items

    def _build_comparison_pdf_attachments(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        attachments: List[Dict[str, Any]] = []
        has_pdf = any(item.get("source_type") == "pdf" for item in items)
        if has_pdf:
            client = get_llm_client()
            if client.provider != "gemini" or not client.supports_pdf_attachments():
                raise ValueError(
                    "Comparison PDF files require Gemini native PDF input (google.genai backend)."
                )
        for item in items:
            if item.get("source_type") != "pdf":
                continue
            path = item.get("path", "")
            if not path or not os.path.exists(path):
                continue
            pdf_bytes = self._read_binary_safe(path)
            if not pdf_bytes:
                continue
            attachments.append(
                {
                    "type": "bytes",
                    "mime_type": "application/pdf",
                    "data": pdf_bytes,
                    "name": os.path.basename(path),
                    "lead_text": (
                        "[comparison attachment]\n"
                        f"file_id: {item.get('file_id', '')}\n"
                        f"display_name: {item.get('display_name', '')}\n"
                        "The next attached PDF corresponds to this comparison item."
                    ),
                }
            )
        return attachments

    def _attachment_log_lines(self, attachments: Optional[List[Dict[str, Any]]]) -> List[str]:
        lines: List[str] = []
        for idx, attachment in enumerate(attachments or [], start=1):
            data = attachment.get("data")
            size = len(data) if isinstance(data, (bytes, bytearray)) else 0
            lines.append(
                "ATTACHMENT_{}: type={} mime_type={} name={} bytes={} lead_text={}".format(
                    idx,
                    attachment.get("type", ""),
                    attachment.get("mime_type", ""),
                    attachment.get("name", ""),
                    size,
                    "yes" if attachment.get("lead_text") else "no",
                )
            )
        return lines

    def _extract_urls_from_text(self, text: str) -> List[str]:
        return [x.rstrip(").,;]>}") for x in re.findall(r"https?://[^\s<>\"]+", text or "")]

    def _verified_direct_url(self, candidate_url: str, review_md: str) -> str:
        candidate_url = str(candidate_url or "").strip().rstrip(").,;]>}")
        if not candidate_url:
            return ""
        review_urls = self._extract_urls_from_text(review_md)
        for url in review_urls:
            if candidate_url == url:
                return url
        return ""

    def _normalize_source_hint(self, source_hint: str, direct_url: str = "") -> str:
        hint = str(source_hint or "").strip().lower()
        host = ""
        try:
            from urllib.parse import urlparse

            host = (urlparse(direct_url).hostname or "").lower()
        except Exception:
            host = ""

        if host.endswith("arxiv.org") or host == "export.arxiv.org":
            return "arxiv"
        if "openreview" in host:
            return "openreview"
        if "thecvf.com" in host:
            return "cvf"

        if hint in {"arxiv", "openreview", "cvf"}:
            return hint
        if any(token in hint for token in ["cvpr", "iccv", "eccv", "wacv", "thecvf", "openaccess"]):
            return "cvf"
        return "unknown"

    def _apply_comparison_item_to_need(
        self,
        need: ComparisonNeed,
        item: Dict[str, str],
        status: Optional[str] = None,
    ) -> None:
        need.provided_file_id = str(item.get("file_id", "")).strip()
        need.provided_source_path = str(item.get("path", "")).strip()
        need.provided_source_type = str(item.get("source_type", "")).strip()
        need.status = status or need.status or "provided"

    def _match_existing_comparison_item(
        self,
        need: ComparisonNeed,
        available_items: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        if not available_items:
            return None

        if need.provided_file_id:
            for item in available_items:
                if str(item.get("file_id", "")).strip() == need.provided_file_id:
                    return item

        if need.provided_source_path:
            for item in available_items:
                if str(item.get("path", "")).strip() == need.provided_source_path:
                    return item

        title_map: Dict[str, Dict[str, str]] = {}
        for item in available_items:
            norm_title = self._normalize_title(item.get("display_name", ""))
            if norm_title:
                title_map[norm_title] = item
        fuzzy = self._fuzzy_match_title(need.paper_title, list(title_map.keys()))
        if fuzzy:
            return title_map.get(fuzzy)
        return None

    def _comparison_inputs_dir(self, session: SessionState) -> str:
        path = os.path.join(session.session_dir, "inputs", "stage1", "comparisons")
        os.makedirs(path, exist_ok=True)
        return path

    def _auto_resolve_comparison_needs(
        self,
        session: SessionState,
        comparison_needs: List[ComparisonNeed],
    ) -> List[ComparisonNeed]:
        if not comparison_needs:
            return comparison_needs

        available_items = self._build_comparison_items(session.comparison_paths)
        resolved_cache: Dict[str, Dict[str, Any]] = {}
        changed = False

        for need in comparison_needs:
            matched_item = self._match_existing_comparison_item(need, available_items)
            if matched_item:
                existing_status = need.status if need.status in {"downloaded", "provided"} else "provided"
                self._apply_comparison_item_to_need(need, matched_item, status=existing_status)
                if not need.retrieval_note and existing_status == "provided":
                    need.retrieval_note = "Matched to an existing comparison file."
                continue

            cache_key = f"{self._normalize_title(need.paper_title)}|{need.direct_url}"
            cached = resolved_cache.get(cache_key)
            if cached:
                if cached.get("path"):
                    if cached["path"] not in session.comparison_paths:
                        session.comparison_paths.append(cached["path"])
                        changed = True
                        available_items = self._build_comparison_items(session.comparison_paths)
                    matched_item = self._match_existing_comparison_item(need, available_items)
                    if matched_item:
                        self._apply_comparison_item_to_need(need, matched_item, status="downloaded")
                    need.retrieval_provider = str(cached.get("provider", "")).strip()
                    need.resolved_url = str(cached.get("resolved_url", "")).strip()
                    need.retrieval_note = str(cached.get("retrieval_note", "")).strip()
                else:
                    need.status = str(cached.get("status", "search_failed")).strip() or "search_failed"
                    need.retrieval_provider = str(cached.get("provider", "")).strip()
                    need.resolved_url = str(cached.get("resolved_url", "")).strip()
                    need.retrieval_note = str(cached.get("retrieval_note", "")).strip()
                continue

            candidate = resolve_comparison_paper_candidate(
                paper_title=need.paper_title,
                direct_url=need.direct_url,
                search_query=need.search_query,
                source_hint=need.source_hint,
            )
            if not candidate:
                note = "No high-confidence match found across arXiv, OpenReview, and CVF."
                need.status = "search_failed"
                need.retrieval_note = note
                self._append_progress(session, f"Stage1: no auto comparison match found for `{need.paper_title}`.")
                resolved_cache[cache_key] = {
                    "path": "",
                    "provider": "",
                    "resolved_url": "",
                    "retrieval_note": note,
                    "status": "search_failed",
                }
                continue

            provider = str(candidate.get("provider", "")).strip()
            resolved_url = str(candidate.get("resolved_url", "") or candidate.get("pdf_url", "")).strip()
            note = str(candidate.get("match_note", "")).strip() or "Matched from automatic paper search."
            pdf_url = str(candidate.get("pdf_url", "")).strip()
            try:
                file_stem = "_".join(
                    [
                        provider or "paper",
                        str(candidate.get("paper_id", "")).strip(),
                        need.paper_title,
                    ]
                )
                pdf_path = download_pdf_to_local(
                    pdf_url=pdf_url,
                    output_dir=self._comparison_inputs_dir(session),
                    file_stem=file_stem,
                    source_label="auto",
                )
                self._append_progress(
                    session,
                    f"Stage1: downloaded comparison paper `{need.paper_title}` from {provider or 'unknown source'}.",
                )
            except Exception as e:
                fail_note = f"{note} Download failed: {e}"
                need.status = "search_failed"
                need.retrieval_provider = provider
                need.resolved_url = resolved_url
                need.retrieval_note = fail_note
                self._append_progress(
                    session,
                    f"Stage1: auto comparison download failed for `{need.paper_title}` ({provider or 'unknown source'}).",
                )
                resolved_cache[cache_key] = {
                    "path": "",
                    "provider": provider,
                    "resolved_url": resolved_url,
                    "retrieval_note": fail_note,
                    "status": "search_failed",
                }
                continue

            if pdf_path not in session.comparison_paths:
                session.comparison_paths.append(pdf_path)
                changed = True
            available_items = self._build_comparison_items(session.comparison_paths)
            matched_item = self._match_existing_comparison_item(
                ComparisonNeed(
                    paper_title=need.paper_title,
                    mentioned_by_reviewer=[],
                    reason="",
                    provided_source_path=pdf_path,
                ),
                available_items,
            )
            if matched_item:
                self._apply_comparison_item_to_need(need, matched_item, status="downloaded")
            else:
                need.provided_source_path = pdf_path
                need.provided_source_type = self._path_source_type(pdf_path)
                need.status = "downloaded"
            need.retrieval_provider = provider
            need.resolved_url = resolved_url
            need.retrieval_note = note
            resolved_cache[cache_key] = {
                "path": pdf_path,
                "provider": provider,
                "resolved_url": resolved_url,
                "retrieval_note": note,
                "status": "downloaded",
            }

        if changed:
            self._save_session_meta(session)
        return comparison_needs

    def run_stage1_analysis(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        self._append_progress(session, "Stage1 started.")
        self._ensure_paper_loaded(session)
        session.review_md = self._read_text_safe(session.review_path)

        if not session.review_md.strip():
            raise ValueError("Review markdown is empty.")

        session.reviewers = self._split_reviews_by_reviewer(session.review_md)
        self._append_progress(session, f"Stage1: detected {len(session.reviewers)} reviewer block(s).")

        reviewer_blocks_payload = [
            {"reviewer_id": r.reviewer_id, "raw_review_md": r.raw_review_md}
            for r in session.reviewers
        ]
        summary_context = (
            f"[review original text]\n```md\n{session.review_md}\n```\n\n"
            f"[reviewer blocks]\n```json\n{json.dumps(reviewer_blocks_payload, ensure_ascii=False, indent=2)}\n```"
        )
        summary_text = self._run_prompt(
            "stage1_review_summarizer.yaml",
            summary_context,
            agent_name="stage1_review_summarizer",
            temperature=0.2,
            session=session,
        )
        summary_json = self._extract_json(summary_text)
        self._append_progress(session, "Stage1: review summarizer completed.")

        reviewer_summary_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(summary_json, dict):
            for item in summary_json.get("reviewers", []) or []:
                rid = self._normalize_reviewer_id(item.get("reviewer_id", ""))
                if rid:
                    reviewer_summary_map[rid] = {
                        "reviewer_id": rid,
                        "summary": str(item.get("summary", "")).strip(),
                        "main_points": item.get("main_points", []) or [],
                        "requested_experiments": item.get("requested_experiments", []) or [],
                    }

        reviewer_summaries: List[Dict[str, Any]] = []
        for reviewer in session.reviewers:
            rid = reviewer.reviewer_id
            info = reviewer_summary_map.get(rid, {})
            summary_md = info.get("summary") or reviewer.raw_review_md[:500]
            reviewer.issue_summary_md = summary_md
            reviewer_summaries.append(
                {
                    "reviewer_id": rid,
                    "summary": summary_md,
                    "main_points": info.get("main_points", []),
                    "requested_experiments": info.get("requested_experiments", []),
                }
            )

        overall_summary = ""
        if isinstance(summary_json, dict):
            overall_summary = str(summary_json.get("overall_summary", "")).strip()
        if not overall_summary:
            overall_summary = "; ".join(
                [f"{x['reviewer_id']}: {x['summary'][:120]}" for x in reviewer_summaries]
            )

        issue_refiner_context = (
            f"[review original text]\n```md\n{session.review_md}\n```\n\n"
            f"[reviewer blocks]\n```json\n{json.dumps(reviewer_blocks_payload, ensure_ascii=False, indent=2)}\n```\n\n"
            f"[reviewer summaries]\n```json\n{json.dumps(reviewer_summaries, ensure_ascii=False, indent=2)}\n```"
        )
        issue_refiner_text = self._run_prompt(
            "stage1_issue_refiner.yaml",
            issue_refiner_context,
            agent_name="stage1_issue_refiner",
            temperature=0.2,
            session=session,
        )
        issue_refiner_json = self._extract_json(issue_refiner_text)
        self._append_progress(session, "Stage1: issue refiner completed.")

        canonical_issues: List[Dict[str, Any]] = []
        if isinstance(issue_refiner_json, dict):
            for idx, item in enumerate(issue_refiner_json.get("canonical_issues", []) or [], start=1):
                if not isinstance(item, dict):
                    continue
                related_reviewers = [
                    self._normalize_reviewer_id(x)
                    for x in (item.get("related_reviewers", []) or [])
                    if self._normalize_reviewer_id(x)
                ]
                category = str(item.get("category", "")).strip().lower()
                if category not in {"experiment", "comparison", "clarification", "writing"}:
                    category = "clarification"
                canonical_issues.append(
                    {
                        "issue_id": str(item.get("issue_id", "")).strip() or f"ISSUE{idx}",
                        "related_reviewers": related_reviewers,
                        "category": category,
                        "summary_cn": str(item.get("summary_cn", "")).strip(),
                        "evidence_quotes": [
                            str(x).strip()
                            for x in (item.get("evidence_quotes", []) or [])
                            if str(x).strip()
                        ],
                        "needs_new_evidence": bool(item.get("needs_new_evidence", False)),
                    }
                )
        if not canonical_issues:
            canonical_issues = self._build_default_canonical_issues(reviewer_summaries)

        paper_context, paper_attachments = self._build_paper_prompt_context(session, char_limit=120000)
        planner_context = (
            f"{paper_context}\n\n"
            f"[review original text]\n```md\n{session.review_md}\n```\n\n"
            f"[reviewer blocks]\n```json\n{json.dumps(reviewer_blocks_payload, ensure_ascii=False, indent=2)}\n```\n\n"
            f"[reviewer summaries]\n```json\n{json.dumps(reviewer_summaries, ensure_ascii=False, indent=2)}\n```\n\n"
            f"[canonical issues]\n```json\n{json.dumps(canonical_issues, ensure_ascii=False, indent=2)}\n```"
        )
        planner_text = self._run_prompt(
            "stage1_experiment_planner.yaml",
            planner_context,
            agent_name="stage1_experiment_planner",
            temperature=0.3,
            session=session,
            attachments=paper_attachments,
        )
        planner_json = self._extract_json(planner_text)
        self._append_progress(session, "Stage1: experiment planner completed.")

        experiment_tasks: List[ExperimentTask] = []
        if isinstance(planner_json, dict):
            for i, task in enumerate(planner_json.get("experiment_tasks", []) or [], start=1):
                rid_list = [
                    self._normalize_reviewer_id(x)
                    for x in (task.get("related_reviewers", []) or [])
                    if self._normalize_reviewer_id(x)
                ]
                if not rid_list:
                    rid_list = [r.reviewer_id for r in session.reviewers]
                exp_id = self._normalize_exp_id(str(task.get("exp_id", ""))) or f"EXP{i}"
                experiment_tasks.append(
                    ExperimentTask(
                        exp_id=exp_id,
                        related_reviewers=rid_list,
                        goal=str(task.get("goal", "")).strip(),
                        how_to_run=str(task.get("how_to_run", "")).strip(),
                        coding_prompt_md=str(task.get("coding_prompt_md", "")).strip(),
                        expected_result_hint=str(task.get("expected_result_hint", "")).strip(),
                    )
                )

        reviewer_response_plans: List[ReviewerResponsePlan] = []
        if isinstance(planner_json, dict):
            for row in planner_json.get("reviewer_response_plans", []) or []:
                if not isinstance(row, dict):
                    continue
                rid = self._normalize_reviewer_id(row.get("reviewer_id", ""))
                if not rid:
                    continue
                reviewer_response_plans.append(
                    ReviewerResponsePlan(
                        reviewer_id=rid,
                        main_position_en=str(row.get("main_position_en", "")).strip(),
                        must_answer_points_cn=[
                            str(x).strip()
                            for x in (row.get("must_answer_points_cn", []) or [])
                            if str(x).strip()
                        ],
                        planned_evidence=[
                            str(x).strip()
                            for x in (row.get("planned_evidence", []) or [])
                            if str(x).strip()
                        ],
                        open_tbd_items=[
                            str(x).strip()
                            for x in (row.get("open_tbd_items", []) or [])
                            if str(x).strip()
                        ],
                    )
                )
        if not reviewer_response_plans:
            reviewer_response_plans = self._build_default_reviewer_response_plans(
                reviewer_summaries,
                canonical_issues,
            )
        else:
            existing_ids = {
                self._normalize_reviewer_id(plan.reviewer_id) for plan in reviewer_response_plans
            }
            default_plans = self._build_default_reviewer_response_plans(
                reviewer_summaries,
                canonical_issues,
            )
            for default_plan in default_plans:
                if self._normalize_reviewer_id(default_plan.reviewer_id) not in existing_ids:
                    reviewer_response_plans.append(default_plan)

        available_comparison_items = self._build_comparison_items(session.comparison_paths)
        comparison_item_map = {
            str(item.get("file_id", "")).strip(): item
            for item in available_comparison_items
            if str(item.get("file_id", "")).strip()
        }
        gap_attachments = self._build_comparison_pdf_attachments(available_comparison_items)

        gap_context = (
            f"[review original text]\n```md\n{session.review_md}\n```\n\n"
            f"[provided comparison items]\n```json\n{json.dumps([{k: v for k, v in item.items() if k != 'path'} for item in available_comparison_items], ensure_ascii=False, indent=2)}\n```"
        )
        gap_text = self._run_prompt(
            "stage1_comparison_gap_detector.yaml",
            gap_context,
            agent_name="stage1_comparison_gap_detector",
            temperature=0.2,
            session=session,
            attachments=gap_attachments,
        )
        gap_json = self._extract_json(gap_text)
        self._append_progress(session, "Stage1: comparison gap detector completed.")

        comparison_needs: List[ComparisonNeed] = []
        if isinstance(gap_json, dict):
            for item in gap_json.get("mentioned_papers", []) or []:
                paper_title = str(item.get("paper_title", "")).strip()
                if not paper_title:
                    continue
                mentioned = [
                    self._normalize_reviewer_id(x)
                    for x in (item.get("mentioned_by_reviewer", []) or [])
                    if self._normalize_reviewer_id(x)
                ]
                reviewer_scope = "explicit" if mentioned else "all_due_to_unclear_attribution"

                match_file_id = str(item.get("match_file_id", "")).strip()
                matched_item = comparison_item_map.get(match_file_id, {})
                match_path = str(matched_item.get("path", "")).strip()
                match_source_type = str(matched_item.get("source_type", "")).strip()
                direct_url = self._verified_direct_url(str(item.get("direct_url", "")).strip(), session.review_md)
                search_query = " ".join(str(item.get("search_query", "")).split()).strip() or paper_title
                source_hint = self._normalize_source_hint(str(item.get("source_hint", "")).strip(), direct_url)

                comparison_needs.append(
                    ComparisonNeed(
                        paper_title=paper_title,
                        mentioned_by_reviewer=mentioned,
                        reason=str(item.get("reason", "")).strip(),
                        reviewer_scope=reviewer_scope,
                        direct_url=direct_url,
                        search_query=search_query,
                        source_hint=source_hint,
                        provided_file_id=match_file_id,
                        provided_source_path=match_path,
                        provided_source_type=match_source_type,
                        status="provided" if match_path else "missing",
                    )
                )

        comparison_needs = self._auto_resolve_comparison_needs(session, comparison_needs)
        reviewer_response_plans = self._augment_response_plans_with_comparisons(
            reviewer_response_plans,
            comparison_needs,
        )

        stage1_data = {
            "overall_summary": overall_summary,
            "reviewer_summaries": reviewer_summaries,
            "canonical_issues": canonical_issues,
            "experiment_tasks": [asdict(x) for x in experiment_tasks],
            "reviewer_response_plans": [asdict(x) for x in reviewer_response_plans],
            "comparison_needs": [asdict(x) for x in comparison_needs],
        }

        session.stage1_data = stage1_data
        self._save_json(
            os.path.join(session.session_dir, "outputs", "stage1_output.json"),
            stage1_data,
        )
        self._save_session_meta(session)
        self._append_progress(session, "Stage1 completed.")

        return stage1_data

    def run_stage2_rebuttal(
        self,
        session_id: str,
        experiment_result_paths: Optional[List[str]] = None,
        additional_comparison_paths: Optional[List[str]] = None,
    ) -> Dict[str, RebuttalDraft]:
        session = self._require_session(session_id)
        self._append_progress(session, "Stage2 started.")

        self._ensure_paper_loaded(session)
        if not session.review_md.strip() and session.review_path:
            session.review_md = self._read_text_safe(session.review_path)
        if not session.reviewers and session.review_md.strip():
            session.reviewers = self._split_reviews_by_reviewer(session.review_md)

        if not session.stage1_data:
            restored_stage1 = self._load_json_safe(os.path.join(session.session_dir, "outputs", "stage1_output.json"))
            if isinstance(restored_stage1, dict):
                session.stage1_data = restored_stage1

        if not session.stage1_data:
            raise RuntimeError("Stage1 has not been completed.")

        experiment_result_paths = experiment_result_paths or []
        additional_comparison_paths = additional_comparison_paths or []

        for path in additional_comparison_paths:
            if path not in session.comparison_paths:
                session.comparison_paths.append(path)

        tasks = [
            ExperimentTask(**x)
            for x in (session.stage1_data.get("experiment_tasks", []) or [])
            if isinstance(x, dict)
        ]
        reviewer_summaries = session.stage1_data.get("reviewer_summaries", []) or []
        reviewer_response_plans = [
            ReviewerResponsePlan(
                reviewer_id=self._normalize_reviewer_id(x.get("reviewer_id", "")),
                main_position_en=str(x.get("main_position_en", "")).strip(),
                must_answer_points_cn=[
                    str(v).strip()
                    for v in (x.get("must_answer_points_cn", []) or [])
                    if str(v).strip()
                ],
                planned_evidence=[
                    str(v).strip()
                    for v in (x.get("planned_evidence", []) or [])
                    if str(v).strip()
                ],
                open_tbd_items=[
                    str(v).strip()
                    for v in (x.get("open_tbd_items", []) or [])
                    if str(v).strip()
                ],
            )
            for x in (session.stage1_data.get("reviewer_response_plans", []) or [])
            if isinstance(x, dict) and self._normalize_reviewer_id(x.get("reviewer_id", ""))
        ]
        comparison_needs = [
            need
            for x in (session.stage1_data.get("comparison_needs", []) or [])
            for need in [self._comparison_need_from_dict(x)]
            if need
        ]
        if not reviewer_response_plans:
            reviewer_response_plans = self._build_default_reviewer_response_plans(
                reviewer_summaries,
                session.stage1_data.get("canonical_issues", []) or [],
            )
        else:
            existing_ids = {
                self._normalize_reviewer_id(plan.reviewer_id) for plan in reviewer_response_plans
            }
            default_plans = self._build_default_reviewer_response_plans(
                reviewer_summaries,
                session.stage1_data.get("canonical_issues", []) or [],
            )
            for default_plan in default_plans:
                if self._normalize_reviewer_id(default_plan.reviewer_id) not in existing_ids:
                    reviewer_response_plans.append(default_plan)
        reviewer_response_plans = self._augment_response_plans_with_comparisons(
            reviewer_response_plans,
            comparison_needs,
        )

        user_results = self._parse_experiment_results(experiment_result_paths)
        evidence_by_exp: Dict[str, Dict[str, str]] = {}
        all_reviewer_ids = [
            self._normalize_reviewer_id(x.get("reviewer_id", ""))
            for x in reviewer_summaries
        ]
        all_reviewer_ids = [x for x in all_reviewer_ids if x]

        for task in tasks:
            exp_id = self._normalize_exp_id(task.exp_id)
            result_text = user_results.get(exp_id, "")
            source = "user"

            if not result_text and len(user_results) == 1:
                result_text = list(user_results.values())[0]

            if not result_text:
                source = "auto"
                self._append_progress(session, f"Stage2: generating [AUTO] result for {exp_id}.")
                paper_context, paper_attachments = self._build_paper_prompt_context(session, char_limit=60000)
                task_reviewer_ids = task.related_reviewers or all_reviewer_ids
                comparison_context, comparison_attachments = self._build_comparison_context_for_task(
                    task_reviewer_ids,
                    comparison_needs,
                    session.comparison_paths,
                )
                auto_context = (
                    f"{paper_context}\n\n"
                    f"[comparison context]\n```md\n{comparison_context}\n```\n\n"
                    f"[experiment task]\n```json\n{json.dumps(asdict(task), ensure_ascii=False, indent=2)}\n```"
                )
                result_text = self._run_prompt(
                    "stage2_auto_result_generator.yaml",
                    auto_context,
                    agent_name=f"stage2_auto_result_generator_{exp_id}",
                    temperature=0.4,
                    session=session,
                    attachments=paper_attachments + comparison_attachments,
                ).strip()
                result_text = self._normalize_auto_result_text(result_text)

            evidence_by_exp[exp_id] = {
                "source": source,
                "result_snippet": result_text.strip(),
            }

        reviewer_ids = [self._normalize_reviewer_id(x.get("reviewer_id", "")) for x in reviewer_summaries]
        reviewer_ids = [x for x in reviewer_ids if x]

        merger_context = (
            f"[experiment tasks]\n```json\n{json.dumps([asdict(x) for x in tasks], ensure_ascii=False, indent=2)}\n```\n\n"
            f"[evidence by experiment]\n```json\n{json.dumps(evidence_by_exp, ensure_ascii=False, indent=2)}\n```\n\n"
            f"[reviewer ids]\n```json\n{json.dumps(reviewer_ids, ensure_ascii=False)}\n```"
        )
        merger_text = self._run_prompt(
            "stage2_experiment_result_merger.yaml",
            merger_context,
            agent_name="stage2_experiment_result_merger",
            temperature=0.2,
            session=session,
        )
        merger_json = self._extract_json(merger_text)
        self._append_progress(session, "Stage2: experiment result merger completed.")

        reviewer_evidence_map: Dict[str, List[Dict[str, str]]] = {}
        if isinstance(merger_json, dict):
            raw_map = merger_json.get("reviewer_evidence", {}) or {}
            if isinstance(raw_map, dict):
                for rid, rows in raw_map.items():
                    norm_rid = self._normalize_reviewer_id(rid)
                    if not norm_rid or not isinstance(rows, list):
                        continue
                    reviewer_evidence_map[norm_rid] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        reviewer_evidence_map[norm_rid].append(
                            {
                                "exp_id": self._normalize_exp_id(str(row.get("exp_id", ""))),
                                "source": str(row.get("source", "")).strip() or "user",
                                "result_snippet": str(row.get("result_snippet", "")).strip(),
                            }
                        )

        if not reviewer_evidence_map:
            for rid in reviewer_ids:
                reviewer_evidence_map[rid] = []
            for task in tasks:
                exp_id = self._normalize_exp_id(task.exp_id)
                payload = evidence_by_exp.get(exp_id, {})
                row = {
                    "exp_id": exp_id,
                    "source": payload.get("source", "user"),
                    "result_snippet": payload.get("result_snippet", ""),
                }
                for rid in task.related_reviewers:
                    norm_rid = self._normalize_reviewer_id(rid)
                    if norm_rid:
                        reviewer_evidence_map.setdefault(norm_rid, []).append(row)

        reviewer_raw_map = {r.reviewer_id: r.raw_review_md for r in session.reviewers}
        reviewer_summary_map = {
            self._normalize_reviewer_id(x.get("reviewer_id", "")): x for x in reviewer_summaries
        }
        reviewer_response_plan_map = {
            self._normalize_reviewer_id(x.reviewer_id): x for x in reviewer_response_plans
        }

        drafts: Dict[str, RebuttalDraft] = {}
        for rid in reviewer_ids:
            self._append_progress(session, f"Stage2: drafting rebuttal for {rid}.")
            evidence_items = reviewer_evidence_map.get(rid, [])
            evidence_md_lines = []
            for item in evidence_items:
                exp_id = self._normalize_exp_id(item.get("exp_id", ""))
                evidence_md_lines.append(
                    f"- {exp_id} ({item.get('source', 'user')}): {item.get('result_snippet', '').strip()}"
                )
            if not evidence_md_lines:
                evidence_md_lines.append("- No direct experiment evidence mapped for this reviewer.")

            comparison_context, comparison_attachments = self._build_comparison_context_for_reviewer(
                rid,
                comparison_needs,
                session.comparison_paths,
            )
            paper_context, paper_attachments = self._build_paper_prompt_context(session, char_limit=100000)
            combined_attachments = paper_attachments + comparison_attachments
            response_plan = reviewer_response_plan_map.get(
                rid,
                ReviewerResponsePlan(
                    reviewer_id=rid,
                    main_position_en="We will answer the reviewer with direct evidence and a clarified explanation.",
                    must_answer_points_cn=[],
                    planned_evidence=[],
                    open_tbd_items=[],
                ),
            )

            writer_context = (
                f"[reviewer id]\n{rid}\n\n"
                f"{paper_context}\n\n"
                f"[reviewer raw review]\n```md\n{reviewer_raw_map.get(rid, '')}\n```\n\n"
                f"[reviewer summary]\n```json\n{json.dumps(reviewer_summary_map.get(rid, {}), ensure_ascii=False, indent=2)}\n```\n\n"
                f"[reviewer response plan]\n```json\n{json.dumps(asdict(response_plan), ensure_ascii=False, indent=2)}\n```\n\n"
                f"[experiment evidence]\n```md\n{chr(10).join(evidence_md_lines)}\n```\n\n"
                f"[comparison context]\n```md\n{comparison_context}\n```"
            )
            draft_text = self._run_prompt(
                "stage2_reviewer_rebuttal_writer.yaml",
                writer_context,
                agent_name=f"stage2_reviewer_rebuttal_writer_{rid}",
                temperature=0.35,
                session=session,
                attachments=combined_attachments,
            ).strip()

            if not draft_text:
                draft_text = f"Response to Reviewer {rid}\n\nQ1: We thank the reviewer for the comments.\nA1: We will provide the missing details in the camera-ready version."

            revised_text = self._run_rebuttal_reviewer(
                reviewer_id=rid,
                raw_review_md=reviewer_raw_map.get(rid, ""),
                response_plan=response_plan,
                draft_text=draft_text,
                evidence_md="\n".join(evidence_md_lines),
                comparison_context=comparison_context,
                attachments=combined_attachments,
                session=session,
            )
            limited_text, note = self._finalize_generated_rebuttal(
                text=revised_text or draft_text,
                reviewer_id=rid,
                raw_review_md=reviewer_raw_map.get(rid, ""),
                response_plan=response_plan,
                evidence_md="\n".join(evidence_md_lines),
                comparison_context=comparison_context,
                attachments=combined_attachments,
                session=session,
            )
            char_count = self.count_chars(limited_text)
            used_auto = "[AUTO]" in limited_text

            drafts[rid] = RebuttalDraft(
                reviewer_id=rid,
                text=limited_text,
                char_count=char_count,
                used_auto_results=used_auto,
                is_within_limit=char_count <= 5000,
                compression_note=note,
            )

        session.stage2_drafts = drafts
        self._save_json(
            os.path.join(session.session_dir, "outputs", "stage2_drafts.json"),
            {k: asdict(v) for k, v in drafts.items()},
        )
        self._save_session_meta(session)
        self._append_progress(session, "Stage2 completed.")
        return drafts

    def finalize_reviewer_rebuttal(self, session_id: str, reviewer_id: str, edited_text: str) -> RebuttalDraft:
        session = self._require_session(session_id)
        rid = self._normalize_reviewer_id(reviewer_id)
        if rid not in session.stage2_drafts:
            raise ValueError(f"Reviewer {rid} draft not found.")

        text = (edited_text or "").strip()
        if not text:
            raise ValueError("Edited rebuttal text is empty.")

        limited_text, note = self._enforce_5000_limit(text, rid, session=session)
        char_count = self.count_chars(limited_text)

        updated = RebuttalDraft(
            reviewer_id=rid,
            text=limited_text,
            char_count=char_count,
            used_auto_results=("[AUTO]" in limited_text),
            is_within_limit=char_count <= 5000,
            compression_note=note,
        )
        session.stage2_drafts[rid] = updated

        self._save_json(
            os.path.join(session.session_dir, "outputs", "stage2_drafts.json"),
            {k: asdict(v) for k, v in session.stage2_drafts.items()},
        )
        self._append_progress(session, f"Applied edit for {rid}.")
        return updated

    def get_reviewer_ids(self, session_id: str) -> List[str]:
        session = self._require_session(session_id)
        if session.stage2_drafts:
            return sorted(session.stage2_drafts.keys(), key=self._reviewer_sort_key)
        if session.stage1_data:
            ids = [self._normalize_reviewer_id(x.get("reviewer_id", "")) for x in session.stage1_data.get("reviewer_summaries", []) or []]
            ids = [x for x in ids if x]
            return sorted(ids, key=self._reviewer_sort_key)
        return [x.reviewer_id for x in session.reviewers]

    def get_reviewer_draft(self, session_id: str, reviewer_id: str) -> Optional[RebuttalDraft]:
        session = self._require_session(session_id)
        rid = self._normalize_reviewer_id(reviewer_id)
        return session.stage2_drafts.get(rid)

    def build_all_drafts_markdown(self, session_id: str) -> str:
        session = self._require_session(session_id)
        blocks = []
        for rid in sorted(session.stage2_drafts.keys(), key=self._reviewer_sort_key):
            draft = session.stage2_drafts[rid]
            blocks.append(f"## {rid} ({draft.char_count}/5000)\n\n{draft.text}")
        return "\n\n---\n\n".join(blocks)

    def _require_session(self, session_id: str) -> SessionState:
        session = self.get_session(session_id)
        if not session:
            session = self.restore_session_from_disk(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        return session

    def _load_json_safe(self, path: str) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _safe_log_name(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (text or "").strip())
        cleaned = cleaned.strip("._-")
        return cleaned or "unknown"

    def _get_logs_dir(self, session: SessionState) -> str:
        path = os.path.join(session.session_dir, "logs")
        os.makedirs(path, exist_ok=True)
        return path

    def _append_progress(self, session: SessionState, message: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}\n"
        try:
            with open(os.path.join(self._get_logs_dir(session), "progress.log"), "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _run_prompt(
        self,
        prompt_file: str,
        context_text: str,
        agent_name: str,
        temperature: float = 0.3,
        session: Optional[SessionState] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        prompt_text = load_prompt(prompt_file)
        run_id = ""
        if session:
            now_ms = int(time.time() * 1000)
            run_id = f"{now_ms}_{self._safe_log_name(agent_name)}"
            client = get_llm_client()
            attachment_lines = self._attachment_log_lines(attachments)
            attachment_log = "\n".join(attachment_lines) + "\n" if attachment_lines else "ATTACHMENTS: none\n"
            input_log = (
                f"PROVIDER: {getattr(client, 'provider', 'unknown')}\n"
                f"MODEL: {getattr(client, 'default_model', 'unknown')}\n"
                f"AGENT: {agent_name}\n"
                f"PROMPT_FILE: {prompt_file}\n"
                f"TEMPERATURE: {temperature}\n"
                f"SAVED_AT: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{attachment_log}"
                "-----PROMPT-----\n"
                f"{prompt_text}\n"
                "-----CONTEXT-----\n"
                f"{context_text}\n"
            )
            try:
                with open(os.path.join(self._get_logs_dir(session), f"{run_id}_input.txt"), "w", encoding="utf-8") as f:
                    f.write(input_log)
            except Exception:
                pass
            self._append_progress(session, f"LLM call started: {agent_name} ({prompt_file}).")

        final_text, _ = get_llm_client().generate(
            instructions=prompt_text,
            input_text=context_text,
            attachments=attachments,
            enable_reasoning=True,
            temperature=temperature,
            agent_name=agent_name,
        )
        if session and run_id:
            output_log = (
                f"AGENT: {agent_name}\n"
                f"PROMPT_FILE: {prompt_file}\n"
                f"SAVED_AT: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                "-----FINAL-----\n"
                f"{(final_text or '').strip()}\n"
            )
            try:
                with open(os.path.join(self._get_logs_dir(session), f"{run_id}_output.txt"), "w", encoding="utf-8") as f:
                    f.write(output_log)
            except Exception:
                pass
            self._append_progress(session, f"LLM call completed: {agent_name} ({prompt_file}).")
        return (final_text or "").strip()

    def _read_text_safe(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    def _read_binary_safe(self, file_path: str) -> bytes:
        with open(file_path, "rb") as f:
            return f.read()

    def _save_json(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _save_session_meta(self, session: SessionState) -> None:
        data = {
            "session_id": session.session_id,
            "paper_path": session.paper_path,
            "review_path": session.review_path,
            "comparison_paths": session.comparison_paths,
            "reviewer_ids": [x.reviewer_id for x in session.reviewers],
            "has_stage1": bool(session.stage1_data),
            "has_stage2": bool(session.stage2_drafts),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_json(os.path.join(session.session_dir, "outputs", "session_meta.json"), data)

    def _extract_json(self, text: str) -> Any:
        if not text:
            return None

        fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL | re.IGNORECASE)
        candidates = []
        if fence_match:
            candidates.append(fence_match.group(1))

        text_stripped = text.strip()
        candidates.append(text_stripped)

        left_brace = text.find("{")
        right_brace = text.rfind("}")
        if left_brace != -1 and right_brace > left_brace:
            candidates.append(text[left_brace:right_brace + 1])

        left_bracket = text.find("[")
        right_bracket = text.rfind("]")
        if left_bracket != -1 and right_bracket > left_bracket:
            candidates.append(text[left_bracket:right_bracket + 1])

        for raw in candidates:
            candidate = raw.strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except Exception:
                pass
            try:
                return json.loads(_fix_json_escapes(candidate))
            except Exception:
                continue
        return None

    def _comparison_need_from_dict(self, item: Dict[str, Any]) -> Optional[ComparisonNeed]:
        if not isinstance(item, dict):
            return None
        paper_title = str(item.get("paper_title", "")).strip()
        if not paper_title:
            return None
        mentioned = [
            self._normalize_reviewer_id(x)
            for x in (item.get("mentioned_by_reviewer", []) or [])
            if self._normalize_reviewer_id(x)
        ]
        provided_source_path = str(
            item.get("provided_source_path", "") or item.get("provided_md_path", "") or ""
        ).strip()
        provided_source_type = str(item.get("provided_source_type", "")).strip()
        if not provided_source_type and provided_source_path:
            provided_source_type = self._path_source_type(provided_source_path)
        provided_file_id = str(item.get("provided_file_id", "")).strip()
        status = str(item.get("status", "")).strip() or ("provided" if provided_source_path else "missing")
        reviewer_scope = str(item.get("reviewer_scope", "")).strip()
        if reviewer_scope not in {"explicit", "all_due_to_unclear_attribution"}:
            reviewer_scope = "explicit" if mentioned else "all_due_to_unclear_attribution"
        return ComparisonNeed(
            paper_title=paper_title,
            mentioned_by_reviewer=mentioned,
            reason=str(item.get("reason", "")).strip(),
            reviewer_scope=reviewer_scope,
            direct_url=str(item.get("direct_url", "")).strip(),
            search_query=" ".join(str(item.get("search_query", "")).split()).strip(),
            source_hint=self._normalize_source_hint(str(item.get("source_hint", "")).strip(), str(item.get("direct_url", "")).strip()),
            provided_file_id=provided_file_id,
            provided_source_path=provided_source_path,
            provided_source_type=provided_source_type,
            retrieval_provider=str(item.get("retrieval_provider", "")).strip(),
            resolved_url=str(item.get("resolved_url", "")).strip(),
            retrieval_note=str(item.get("retrieval_note", "")).strip(),
            status=status,
        )

    def _comparison_need_target_reviewers(
        self,
        need: ComparisonNeed,
        all_reviewer_ids: List[str],
    ) -> List[str]:
        if need.reviewer_scope == "all_due_to_unclear_attribution":
            return [self._normalize_reviewer_id(rid) for rid in all_reviewer_ids if self._normalize_reviewer_id(rid)]

        targets: List[str] = []
        seen: set[str] = set()
        for rid in need.mentioned_by_reviewer:
            norm_rid = self._normalize_reviewer_id(rid)
            if not norm_rid or norm_rid in seen:
                continue
            seen.add(norm_rid)
            targets.append(norm_rid)
        return targets

    def _comparison_scope_note(self, need: ComparisonNeed) -> str:
        if need.reviewer_scope == "all_due_to_unclear_attribution":
            return "Reviewer attribution is unclear in the review text, so this paper is shared with all reviewers."
        return ""

    def _build_comparison_context(
        self,
        target_reviewer_ids: List[str],
        comparison_needs: List[ComparisonNeed],
        comparison_paths: List[str],
        empty_message: str,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        normalized_targets: List[str] = []
        seen_targets: set[str] = set()
        for reviewer_id in target_reviewer_ids:
            norm_rid = self._normalize_reviewer_id(reviewer_id)
            if not norm_rid or norm_rid in seen_targets:
                continue
            seen_targets.add(norm_rid)
            normalized_targets.append(norm_rid)
        if not normalized_targets:
            return empty_message, []

        available_items = self._build_comparison_items(comparison_paths)
        item_by_file_id = {
            str(item.get("file_id", "")).strip(): item
            for item in available_items
            if str(item.get("file_id", "")).strip()
        }
        item_by_norm_title: Dict[str, Dict[str, str]] = {}
        for item in available_items:
            norm_title = self._normalize_title(item.get("display_name", ""))
            if norm_title:
                item_by_norm_title[norm_title] = item

        lines: List[str] = []
        attachments: List[Dict[str, Any]] = []
        attached_paths: set[str] = set()
        for need in comparison_needs:
            need_targets = self._comparison_need_target_reviewers(need, normalized_targets)
            matched_targets = [rid for rid in normalized_targets if rid in need_targets]
            if not matched_targets:
                continue

            lines.append(f"- Mentioned paper: {need.paper_title}")
            if need.reason:
                lines.append(f"  reason: {need.reason}")
            if len(normalized_targets) > 1:
                lines.append(f"  relevant_reviewers: {', '.join(matched_targets)}")
            scope_note = self._comparison_scope_note(need)
            if scope_note:
                lines.append(f"  attribution_note: {scope_note}")

            matched_item: Dict[str, str] = {}
            if need.provided_file_id:
                matched_item = item_by_file_id.get(need.provided_file_id, {})
            if not matched_item and need.provided_source_path:
                for item in available_items:
                    if item.get("path") == need.provided_source_path:
                        matched_item = item
                        break
            if not matched_item:
                fuzzy = self._fuzzy_match_title(need.paper_title, list(item_by_norm_title.keys()))
                if fuzzy:
                    matched_item = item_by_norm_title.get(fuzzy, {})

            source_path = str(matched_item.get("path", "")).strip()
            source_type = str(matched_item.get("source_type", "")).strip()
            display_name = str(matched_item.get("display_name", "")).strip() or os.path.basename(source_path)
            file_id = str(matched_item.get("file_id", "")).strip()

            if source_path and os.path.exists(source_path) and source_type == "md":
                paper_md = self._read_text_safe(source_path)
                excerpt = paper_md[:1800].strip()
                lines.append(f"  provided_md: yes ({os.path.basename(source_path)})")
                lines.append(f"  excerpt: {excerpt}")
            elif source_path and os.path.exists(source_path) and source_type == "pdf":
                if source_path not in attached_paths:
                    pdf_attachments = self._build_comparison_pdf_attachments([matched_item])
                    attachments.extend(pdf_attachments)
                    attached_paths.add(source_path)
                lines.append(f"  provided_pdf: yes ({display_name})")
                if file_id:
                    lines.append(f"  file_id: {file_id}")
                lines.append("  note: Use only the attached comparison PDF for claims about this paper.")
            else:
                lines.append("  provided_md: no")
                lines.append(
                    f"  note: [lack] Comparison material for {need.paper_title} is unavailable in the current session."
                )
                lines.append(
                    "  instruction: Keep the response high-level, state the material gap explicitly, and avoid unsupported paper-specific claims."
                )
                if need.retrieval_note:
                    lines.append(f"  retrieval_note: {need.retrieval_note}")
                if need.direct_url:
                    lines.append(f"  direct_url: {need.direct_url}")
                elif need.resolved_url:
                    lines.append(f"  resolved_url: {need.resolved_url}")
            lines.append("")

        if not lines:
            return empty_message, []
        return "\n".join(lines).strip(), attachments

    def _build_comparison_context_for_task(
        self,
        related_reviewers: List[str],
        comparison_needs: List[ComparisonNeed],
        comparison_paths: List[str],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        return self._build_comparison_context(
            target_reviewer_ids=related_reviewers,
            comparison_needs=comparison_needs,
            comparison_paths=comparison_paths,
            empty_message="No reviewer-relevant comparison-paper request was detected for this experiment.",
        )

    def _normalize_auto_result_text(self, text: str) -> str:
        content = (text or "").strip()
        if not content:
            return ""

        content = re.sub(r"\[\s*(?i:auto)\s*\]", "[AUTO]", content)
        number_pattern = re.compile(r"(?<![A-Za-z0-9_])([+-]?\d+(?:\.\d+)?(?:%|x)?)(?![A-Za-z0-9_]|\s*\[AUTO\])")
        normalized_lines: List[str] = []
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            line = re.sub(r"(?:\s*\[AUTO\]){2,}", "[AUTO]", line)
            if "[AUTO]" in line:
                line = number_pattern.sub(lambda m: f"{m.group(1)}[AUTO]", line)
            normalized_lines.append(line)
        return "\n".join(normalized_lines).strip()

    def _build_default_canonical_issues(
        self,
        reviewer_summaries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        issue_idx = 1
        for row in reviewer_summaries:
            rid = self._normalize_reviewer_id(row.get("reviewer_id", ""))
            if not rid:
                continue
            requests = [str(x).strip() for x in (row.get("requested_experiments", []) or []) if str(x).strip()]
            for request in requests:
                issues.append(
                    {
                        "issue_id": f"ISSUE{issue_idx}",
                        "related_reviewers": [rid],
                        "category": "experiment",
                        "summary_cn": request,
                        "evidence_quotes": [],
                        "needs_new_evidence": True,
                    }
                )
                issue_idx += 1
            for point in [str(x).strip() for x in (row.get("main_points", []) or []) if str(x).strip()]:
                lowered = point.lower()
                category = "clarification"
                if any(token in lowered for token in ["compare", "baseline", "ablation", "experiment"]):
                    category = "experiment"
                elif any(token in lowered for token in ["novel", "similar", "citation", "paper"]):
                    category = "comparison"
                elif any(token in lowered for token in ["clarity", "writing", "presentation", "wording"]):
                    category = "writing"
                issues.append(
                    {
                        "issue_id": f"ISSUE{issue_idx}",
                        "related_reviewers": [rid],
                        "category": category,
                        "summary_cn": point,
                        "evidence_quotes": [],
                        "needs_new_evidence": category in {"experiment", "comparison"},
                    }
                )
                issue_idx += 1
        return issues

    def _build_default_reviewer_response_plans(
        self,
        reviewer_summaries: List[Dict[str, Any]],
        canonical_issues: List[Dict[str, Any]],
    ) -> List[ReviewerResponsePlan]:
        issues_by_reviewer: Dict[str, List[Dict[str, Any]]] = {}
        for item in canonical_issues:
            if not isinstance(item, dict):
                continue
            for rid in item.get("related_reviewers", []) or []:
                norm_rid = self._normalize_reviewer_id(rid)
                if norm_rid:
                    issues_by_reviewer.setdefault(norm_rid, []).append(item)

        plans: List[ReviewerResponsePlan] = []
        for row in reviewer_summaries:
            rid = self._normalize_reviewer_id(row.get("reviewer_id", ""))
            if not rid:
                continue
            must_answer = [str(x).strip() for x in (row.get("main_points", []) or []) if str(x).strip()]
            if not must_answer:
                must_answer = [
                    str(item.get("summary_cn", "")).strip()
                    for item in issues_by_reviewer.get(rid, [])
                    if str(item.get("summary_cn", "")).strip()
                ]
            planned_evidence = [str(x).strip() for x in (row.get("requested_experiments", []) or []) if str(x).strip()]
            open_tbd: List[str] = []
            for item in issues_by_reviewer.get(rid, []):
                if item.get("needs_new_evidence"):
                    summary_cn = str(item.get("summary_cn", "")).strip()
                    if summary_cn:
                        open_tbd.append(summary_cn)
            plans.append(
                ReviewerResponsePlan(
                    reviewer_id=rid,
                    main_position_en="We will answer the reviewer with direct evidence and a clarified explanation.",
                    must_answer_points_cn=must_answer[:6],
                    planned_evidence=planned_evidence[:6],
                    open_tbd_items=open_tbd[:6],
                )
            )
        return plans

    def _augment_response_plans_with_comparisons(
        self,
        plans: List[ReviewerResponsePlan],
        comparison_needs: List[ComparisonNeed],
    ) -> List[ReviewerResponsePlan]:
        by_reviewer = {self._normalize_reviewer_id(plan.reviewer_id): plan for plan in plans}
        all_reviewer_ids = list(by_reviewer.keys())
        for need in comparison_needs:
            summary = f"对比论文：{need.paper_title}"
            scope_note = self._comparison_scope_note(need)
            for norm_rid in self._comparison_need_target_reviewers(need, all_reviewer_ids):
                if norm_rid not in by_reviewer:
                    continue
                plan = by_reviewer[norm_rid]
                if summary not in plan.must_answer_points_cn:
                    plan.must_answer_points_cn.append(summary)
                if need.reason:
                    evidence_hint = f"说明差异点：{need.reason}"
                    if evidence_hint not in plan.planned_evidence:
                        plan.planned_evidence.append(evidence_hint)
                if scope_note and scope_note not in plan.planned_evidence:
                    plan.planned_evidence.append(scope_note)
                if need.status not in {"provided", "downloaded"}:
                    missing_hint = f"待补对比材料：{need.paper_title}"
                    if missing_hint not in plan.open_tbd_items:
                        plan.open_tbd_items.append(missing_hint)
        return list(by_reviewer.values())

    def _normalize_reviewer_id(self, reviewer_id: str) -> str:
        text = (reviewer_id or "").strip().upper()
        if not text:
            return ""
        m = re.search(r"R\s*(\d+)", text)
        if m:
            return f"R{int(m.group(1))}"
        m = re.search(r"REVIEWER\s*(\d+)", text)
        if m:
            return f"R{int(m.group(1))}"
        m = re.search(r"(\d+)", text)
        if m:
            return f"R{int(m.group(1))}"
        return text.replace(" ", "")

    def _split_reviews_by_reviewer(self, review_md: str) -> List[ReviewerBlock]:
        lines = review_md.splitlines()
        header_re = re.compile(
            r"^\s{0,3}(?:#+\s*)?(?:reviewer|review|r)\s*([0-9]+)\b[:：]?\s*(.*)$",
            re.IGNORECASE,
        )

        current_id = ""
        current_lines: List[str] = []
        blocks: List[ReviewerBlock] = []

        def flush_current() -> None:
            nonlocal current_id, current_lines
            content = "\n".join(current_lines).strip()
            if current_id and content:
                blocks.append(ReviewerBlock(reviewer_id=current_id, raw_review_md=content))
            current_lines = []

        for line in lines:
            m = header_re.match(line)
            if m:
                flush_current()
                idx = int(m.group(1))
                current_id = f"R{idx}"
                trailing = (m.group(2) or "").strip()
                current_lines = [trailing] if trailing else []
            else:
                current_lines.append(line)

        flush_current()
        if not blocks:
            return [ReviewerBlock(reviewer_id="R1", raw_review_md=review_md.strip())]

        return sorted(blocks, key=lambda x: self._reviewer_sort_key(x.reviewer_id))

    def _extract_title_from_markdown(self, md_text: str, fallback: str = "") -> str:
        for line in md_text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                if title:
                    return title
            if line:
                break
        return fallback

    def _normalize_title(self, title: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", (title or "").lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _fuzzy_match_title(self, query_title: str, candidate_norm_titles: List[str]) -> str:
        q = self._normalize_title(query_title)
        if not q:
            return ""

        for c in candidate_norm_titles:
            if q == c or q in c or c in q:
                return c

        q_tokens = set(q.split())
        best = ""
        best_score = 0.0
        for c in candidate_norm_titles:
            c_tokens = set(c.split())
            if not c_tokens:
                continue
            score = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
            if score > best_score:
                best_score = score
                best = c
        return best if best_score >= 0.45 else ""

    def _normalize_exp_id(self, exp_id: str) -> str:
        text = (exp_id or "").upper().strip()
        m = re.search(r"EXP\s*[-_ ]?\s*(\d+)", text)
        if m:
            return f"EXP{int(m.group(1))}"
        m = re.search(r"(\d+)", text)
        if m:
            return f"EXP{int(m.group(1))}"
        return ""

    def _parse_experiment_results(self, result_paths: List[str]) -> Dict[str, str]:
        output: Dict[str, str] = {}
        header_re = re.compile(r"^\s{0,3}(?:#+\s*)?(EXP\s*[-_ ]?\d+)\b[:：]?\s*(.*)$", re.IGNORECASE)

        for path in result_paths:
            if not os.path.exists(path):
                continue
            text = self._read_text_safe(path)
            if not text.strip():
                continue

            lines = text.splitlines()
            matches: List[Tuple[int, str, str]] = []
            for idx, line in enumerate(lines):
                m = header_re.match(line)
                if m:
                    matches.append((idx, self._normalize_exp_id(m.group(1)), m.group(2).strip()))

            if matches:
                for i, (start_idx, exp_id, trailing) in enumerate(matches):
                    end_idx = matches[i + 1][0] if i + 1 < len(matches) else len(lines)
                    body = "\n".join(lines[start_idx:end_idx]).strip()
                    if trailing:
                        body = f"{trailing}\n{body}".strip()
                    if exp_id and body:
                        output[exp_id] = body
            else:
                fallback_key = self._normalize_exp_id(os.path.basename(path))
                if fallback_key:
                    output[fallback_key] = text.strip()

        return output

    def _build_comparison_context_for_reviewer(
        self,
        reviewer_id: str,
        comparison_needs: List[ComparisonNeed],
        comparison_paths: List[str],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        return self._build_comparison_context(
            target_reviewer_ids=[reviewer_id],
            comparison_needs=comparison_needs,
            comparison_paths=comparison_paths,
            empty_message="No reviewer-specific comparison-paper request was detected.",
        )

    def _compress_rebuttal_text(
        self,
        text: str,
        reviewer_id: str,
        session: Optional[SessionState] = None,
        rounds: int = 2,
    ) -> Tuple[str, str]:
        content = (text or "").strip()
        if len(content) <= 5000:
            return content, ""

        note = ""
        for i in range(rounds):
            compress_context = (
                f"[target character limit]\n5000\n\n"
                f"[reviewer id]\n{reviewer_id}\n\n"
                f"[text to compress]\n```md\n{content}\n```"
            )
            compressed = self._run_prompt(
                "stage2_rebuttal_compressor.yaml",
                compress_context,
                agent_name=f"stage2_rebuttal_compressor_{reviewer_id}_{i+1}",
                temperature=0.2,
                session=session,
            ).strip()
            if not compressed:
                break
            content = compressed
            if len(content) <= 5000:
                note = f"Compressed in round {i + 1}."
                return content, note

        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        if len(content) <= 5000:
            return content, "Compressed by heuristic cleanup."

        suffix = "\n[TRUNCATED_FOR_LIMIT]"
        keep = max(0, 5000 - len(suffix))
        content = content[:keep].rstrip() + suffix
        return content, "Compressed and hard-truncated to satisfy 5000-character limit."

    def _run_rebuttal_reviewer(
        self,
        reviewer_id: str,
        raw_review_md: str,
        response_plan: ReviewerResponsePlan,
        draft_text: str,
        evidence_md: str,
        comparison_context: str,
        attachments: List[Dict[str, Any]],
        session: Optional[SessionState] = None,
        target_limit: Optional[int] = None,
        pass_name: str = "main",
    ) -> str:
        context = (
            f"[reviewer id]\n{reviewer_id}\n\n"
            f"[reviewer raw review]\n```md\n{raw_review_md}\n```\n\n"
            f"[reviewer response plan]\n```json\n{json.dumps(asdict(response_plan), ensure_ascii=False, indent=2)}\n```\n\n"
            f"[writer draft]\n```md\n{draft_text}\n```\n\n"
            f"[experiment evidence]\n```md\n{evidence_md}\n```\n\n"
            f"[comparison context]\n```md\n{comparison_context}\n```"
        )
        if target_limit is not None:
            context += f"\n\n[target character limit]\n{int(target_limit)}"
        revised = self._run_prompt(
            "stage2_rebuttal_reviewer.yaml",
            context,
            agent_name=f"stage2_rebuttal_reviewer_{reviewer_id}_{pass_name}",
            temperature=0.2,
            session=session,
            attachments=attachments,
        ).strip()
        return revised or (draft_text or "").strip()

    def _ensure_required_comparison_markers(
        self,
        text: str,
        comparison_context: str,
    ) -> Tuple[str, str]:
        content = (text or "").strip()
        lack_lines = [line.strip() for line in (comparison_context or "").splitlines() if "[lack]" in line]
        if lack_lines and "[lack]" not in content:
            marker_line = re.sub(r"^note:\s*", "", lack_lines[0], flags=re.IGNORECASE).strip()
            if content:
                content = f"{content}\n\n{marker_line}"
            else:
                content = marker_line
            return content, "Inserted missing [lack] marker."
        return content, ""

    def _finalize_generated_rebuttal(
        self,
        text: str,
        reviewer_id: str,
        raw_review_md: str,
        response_plan: ReviewerResponsePlan,
        evidence_md: str,
        comparison_context: str,
        attachments: List[Dict[str, Any]],
        session: Optional[SessionState] = None,
    ) -> Tuple[str, str]:
        content = (text or "").strip()
        notes: List[str] = []
        content, marker_note = self._ensure_required_comparison_markers(content, comparison_context)
        if marker_note:
            notes.append(marker_note)
        if len(content) <= 5000:
            return content, " ".join(notes).strip()

        compressed, compress_note = self._compress_rebuttal_text(
            content,
            reviewer_id,
            session=session,
            rounds=2,
        )
        content = compressed
        if compress_note:
            notes.append(compress_note)

        if len(content) > 5000:
            return content, " ".join(notes).strip()

        repaired = self._run_rebuttal_reviewer(
            reviewer_id=reviewer_id,
            raw_review_md=raw_review_md,
            response_plan=response_plan,
            draft_text=content,
            evidence_md=evidence_md,
            comparison_context=comparison_context,
            attachments=attachments,
            session=session,
            target_limit=5000,
            pass_name="limit_repair",
        )
        if repaired and repaired != content:
            content = repaired
            notes.append("Post-compression review rewrite applied.")

        content, marker_note = self._ensure_required_comparison_markers(content, comparison_context)
        if marker_note:
            notes.append(marker_note)

        if len(content) > 5000:
            content, final_note = self._compress_rebuttal_text(
                content,
                reviewer_id,
                session=session,
                rounds=1,
            )
            if final_note:
                notes.append(final_note)

        return content, " ".join(notes).strip()

    def _enforce_5000_limit(self, text: str, reviewer_id: str, session: Optional[SessionState] = None) -> Tuple[str, str]:
        return self._compress_rebuttal_text(text, reviewer_id, session=session, rounds=2)

    def _reviewer_sort_key(self, reviewer_id: str) -> Tuple[int, str]:
        rid = self._normalize_reviewer_id(reviewer_id)
        m = re.search(r"R(\d+)", rid)
        if m:
            return int(m.group(1)), rid
        return 10**9, rid


rebuttal_service = RebuttalService()
