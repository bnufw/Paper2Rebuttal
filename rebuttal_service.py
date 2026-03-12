import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from llm import LLMClient, TokenUsageTracker
from tools import _fix_json_escapes, load_prompt


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
class ComparisonNeed:
    paper_title: str
    mentioned_by_reviewer: List[str]
    reason: str
    provided_md_path: str = ""
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
        return len(text or "")

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

    def _attachment_log_lines(self, attachments: Optional[List[Dict[str, Any]]]) -> List[str]:
        lines: List[str] = []
        for idx, attachment in enumerate(attachments or [], start=1):
            data = attachment.get("data")
            size = len(data) if isinstance(data, (bytes, bytearray)) else 0
            lines.append(
                "ATTACHMENT_{}: type={} mime_type={} name={} bytes={}".format(
                    idx,
                    attachment.get("type", ""),
                    attachment.get("mime_type", ""),
                    attachment.get("name", ""),
                    size,
                )
            )
        return lines

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

        paper_context, paper_attachments = self._build_paper_prompt_context(session, char_limit=120000)
        planner_context = (
            f"{paper_context}\n\n"
            f"[reviewer summaries]\n```json\n{json.dumps(reviewer_summaries, ensure_ascii=False, indent=2)}\n```"
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

        provided_title_to_path: Dict[str, str] = {}
        provided_titles: List[str] = []
        for path in session.comparison_paths:
            if not os.path.exists(path):
                continue
            title = self._extract_title_from_markdown(self._read_text_safe(path), fallback=os.path.basename(path))
            norm_title = self._normalize_title(title)
            if norm_title:
                provided_title_to_path[norm_title] = path
                provided_titles.append(title)

        gap_context = (
            f"[review original text]\n```md\n{session.review_md}\n```\n\n"
            f"[provided comparison titles]\n```json\n{json.dumps(provided_titles, ensure_ascii=False, indent=2)}\n```"
        )
        gap_text = self._run_prompt(
            "stage1_comparison_gap_detector.yaml",
            gap_context,
            agent_name="stage1_comparison_gap_detector",
            temperature=0.2,
            session=session,
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
                if not mentioned:
                    mentioned = [r.reviewer_id for r in session.reviewers]

                matched_title = str(item.get("match_provided_title", "")).strip()
                match_path = ""
                if matched_title:
                    match_path = provided_title_to_path.get(self._normalize_title(matched_title), "")
                if not match_path:
                    fuzzy = self._fuzzy_match_title(paper_title, list(provided_title_to_path.keys()))
                    if fuzzy:
                        match_path = provided_title_to_path.get(fuzzy, "")

                comparison_needs.append(
                    ComparisonNeed(
                        paper_title=paper_title,
                        mentioned_by_reviewer=mentioned,
                        reason=str(item.get("reason", "")).strip(),
                        provided_md_path=match_path,
                        status="provided" if match_path else "missing",
                    )
                )

        stage1_data = {
            "overall_summary": overall_summary,
            "reviewer_summaries": reviewer_summaries,
            "experiment_tasks": [asdict(x) for x in experiment_tasks],
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
        comparison_needs = [
            ComparisonNeed(**x)
            for x in (session.stage1_data.get("comparison_needs", []) or [])
            if isinstance(x, dict)
        ]

        user_results = self._parse_experiment_results(experiment_result_paths)
        evidence_by_exp: Dict[str, Dict[str, str]] = {}

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
                auto_context = (
                    f"{paper_context}\n\n"
                    f"[experiment task]\n```json\n{json.dumps(asdict(task), ensure_ascii=False, indent=2)}\n```"
                )
                result_text = self._run_prompt(
                    "stage2_auto_result_generator.yaml",
                    auto_context,
                    agent_name=f"stage2_auto_result_generator_{exp_id}",
                    temperature=0.4,
                    session=session,
                    attachments=paper_attachments,
                ).strip()
                if "[AUTO]" not in result_text:
                    result_text = f"[AUTO] {result_text}"

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

            comparison_context = self._build_comparison_context_for_reviewer(
                rid,
                comparison_needs,
                session.comparison_paths,
            )
            paper_context, paper_attachments = self._build_paper_prompt_context(session, char_limit=100000)

            writer_context = (
                f"[reviewer id]\n{rid}\n\n"
                f"{paper_context}\n\n"
                f"[reviewer raw review]\n```md\n{reviewer_raw_map.get(rid, '')}\n```\n\n"
                f"[reviewer summary]\n```json\n{json.dumps(reviewer_summary_map.get(rid, {}), ensure_ascii=False, indent=2)}\n```\n\n"
                f"[experiment evidence]\n```md\n{chr(10).join(evidence_md_lines)}\n```\n\n"
                f"[comparison context]\n```md\n{comparison_context}\n```"
            )
            draft_text = self._run_prompt(
                "stage2_reviewer_rebuttal_writer.yaml",
                writer_context,
                agent_name=f"stage2_reviewer_rebuttal_writer_{rid}",
                temperature=0.35,
                session=session,
                attachments=paper_attachments,
            ).strip()

            if not draft_text:
                draft_text = f"Response to Reviewer {rid}\n\nQ1: We thank the reviewer for the comments.\nA1: We will provide the missing details in the camera-ready version."

            limited_text, note = self._enforce_5000_limit(draft_text, rid, session=session)
            char_count = self.count_chars(limited_text)
            used_auto = "[AUTO]" in limited_text or any(
                x.get("source") == "auto" for x in evidence_items
            )

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

        existing = session.stage2_drafts[rid]
        updated = RebuttalDraft(
            reviewer_id=rid,
            text=limited_text,
            char_count=char_count,
            used_auto_results=("[AUTO]" in limited_text) or existing.used_auto_results,
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
    ) -> str:
        rid = self._normalize_reviewer_id(reviewer_id)
        if not rid:
            return ""

        available_title_to_path: Dict[str, str] = {}
        for path in comparison_paths:
            if not os.path.exists(path):
                continue
            title = self._extract_title_from_markdown(self._read_text_safe(path), os.path.basename(path))
            available_title_to_path[self._normalize_title(title)] = path

        lines: List[str] = []
        for need in comparison_needs:
            if rid not in [self._normalize_reviewer_id(x) for x in need.mentioned_by_reviewer]:
                continue

            lines.append(f"- Mentioned paper: {need.paper_title}")
            if need.reason:
                lines.append(f"  reason: {need.reason}")

            source_path = need.provided_md_path
            if not source_path:
                fuzzy = self._fuzzy_match_title(need.paper_title, list(available_title_to_path.keys()))
                if fuzzy:
                    source_path = available_title_to_path.get(fuzzy, "")

            if source_path and os.path.exists(source_path):
                paper_md = self._read_text_safe(source_path)
                excerpt = paper_md[:1800].strip()
                lines.append(f"  provided_md: yes ({os.path.basename(source_path)})")
                lines.append(f"  excerpt: {excerpt}")
            else:
                lines.append("  provided_md: no")
                lines.append("  note: Comparison paper markdown is missing; keep response high-level and request concrete paper evidence from author if needed.")

        if not lines:
            return "No reviewer-specific comparison-paper request was detected."
        return "\n".join(lines)

    def _enforce_5000_limit(self, text: str, reviewer_id: str, session: Optional[SessionState] = None) -> Tuple[str, str]:
        content = (text or "").strip()
        if len(content) <= 5000:
            return content, ""

        note = ""
        for i in range(2):
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

    def _reviewer_sort_key(self, reviewer_id: str) -> Tuple[int, str]:
        rid = self._normalize_reviewer_id(reviewer_id)
        m = re.search(r"R(\d+)", rid)
        if m:
            return int(m.group(1)), rid
        return 10**9, rid


rebuttal_service = RebuttalService()
