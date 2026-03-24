import sys
import os

os.environ["OMP_NUM_THREADS"] = "4"

DOCLING_DEVICE = os.environ.get("DOCLING_DEVICE", "cpu").lower()

import re
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
import urllib.request
import urllib.parse
import urllib.error
import threading
from typing import Any, Dict, List, Optional, Tuple

from arxiv import resolve_arxiv_paper

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ARXIV_DIRECT_OPENER = urllib.request.build_opener()
ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
OPENREVIEW_HOSTS = {"openreview.net", "www.openreview.net", "api2.openreview.net"}
CVF_HOSTS = {"openaccess.thecvf.com", "www.openaccess.thecvf.com"}
CVF_BASE_URL = "https://openaccess.thecvf.com"
DEFAULT_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
_OPENREVIEW_CLIENT_CACHE: Dict[Tuple[str, str, str], Any] = {}
_CVF_QUERY_CACHE: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
            
PDF_CONVERT_LOCK = threading.Lock()

from pathlib import Path
import shutil

_docling_converter = None
_docling_current_device = None 

def _read_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def _fix_json_escapes(json_str: str) -> str:
    """Fix unescaped backslashes in JSON strings (e.g., backslashes in LaTeX formulas)"""
    json_str = json_str.replace('\\\\', '\x00ESCAPED_BACKSLASH\x00')
    json_str = json_str.replace('\\n', '\x00ESCAPED_N\x00')
    json_str = json_str.replace('\\t', '\x00ESCAPED_T\x00')
    json_str = json_str.replace('\\"', '\x00ESCAPED_QUOTE\x00')
    json_str = json_str.replace('\\/', '\x00ESCAPED_SLASH\x00')
    json_str = json_str.replace('\\r', '\x00ESCAPED_R\x00')
    json_str = json_str.replace('\\b', '\x00ESCAPED_B\x00')
    json_str = json_str.replace('\\f', '\x00ESCAPED_F\x00')
    # Escape remaining single backslashes
    json_str = json_str.replace('\\', '\\\\')
    # Restore protected content
    json_str = json_str.replace('\x00ESCAPED_BACKSLASH\x00', '\\\\')
    json_str = json_str.replace('\x00ESCAPED_N\x00', '\\n')
    json_str = json_str.replace('\x00ESCAPED_T\x00', '\\t')
    json_str = json_str.replace('\x00ESCAPED_QUOTE\x00', '\\"')
    json_str = json_str.replace('\x00ESCAPED_SLASH\x00', '\\/')
    json_str = json_str.replace('\x00ESCAPED_R\x00', '\\r')
    json_str = json_str.replace('\x00ESCAPED_B\x00', '\\b')
    json_str = json_str.replace('\x00ESCAPED_F\x00', '\\f')
    return json_str

def pdf_to_md(pdf_path: str, output_path: str) -> str | None:
    """Convert PDF to Markdown.
    
    Uses a global lock to protect docling calls, ensuring only one PDF is converted at a time.
    Returns the generated file path, or None on failure.
    
    Note: docling is imported lazily to avoid triggering CUDA initialization errors
    in HF Spaces Stateless GPU environment.
    """
    global _docling_converter
    
    try:
        paths = Path(pdf_path)
        
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        print(f"[DEBUG] Preparing to convert PDF: {pdf_path}")
        print(f"[DEBUG] Waiting to acquire docling conversion lock...")
        with PDF_CONVERT_LOCK:
            print(f"[DEBUG] Lock acquired, starting docling conversion...")
            

            if _docling_converter is None:
                device_str = DOCLING_DEVICE
                print(f"[DEBUG] First use, importing and initializing docling DocumentConverter ({device_str.upper()} mode)...")
                from docling.document_converter import DocumentConverter, PdfFormatOption
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.datamodel.base_models import InputFormat
                try:
                    from docling.datamodel.pipeline_options import AcceleratorDevice
                    if device_str == "cuda":
                        accelerator_device = AcceleratorDevice.CUDA
                    else:
                        accelerator_device = AcceleratorDevice.CPU
                except ImportError:
                    accelerator_device = device_str
                
                pipeline_options = PdfPipelineOptions()
                pipeline_options.accelerator_options.device = accelerator_device
                
                _docling_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                    }
                )
                print(f"[DEBUG] docling DocumentConverter initialization complete ({device_str.upper()} mode)")
        
            converter = _docling_converter
        
            print(f"[DEBUG] Calling docling converter.convert()...")
            raw_result = converter.convert(pdf_path)
        
            if hasattr(raw_result, 'document'):
                md_content = raw_result.document.export_to_markdown()
            else:
                md_content = raw_result.export_to_markdown()
            
            print(f"[DEBUG] docling conversion complete, releasing lock")
        
        target_md = os.path.join(output_path, paths.stem + ".md")
        with open(target_md, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"[SUCCESS] Markdown file saved to: {target_md}")
        print(f"[DEBUG] Markdown file size: {len(md_content)} characters")
        
        return target_md
        
    except Exception as e:
        print(f"[ERROR] pdf_to_md failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def mistral_pdf_to_markdown(pdf_path: str, model: str = "mistral-ocr-latest") -> str:
    api_key = (os.environ.get("MISTRAL_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Missing MISTRAL_API_KEY. Please set it in your environment before uploading a PDF.")

    import base64
    import requests

    with open(pdf_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{b64}",
        },
        "include_image_base64": False,
    }
    resp = requests.post(
        "https://api.mistral.ai/v1/ocr",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=600,
    )
    if not resp.ok:
        raise ValueError(f"Mistral OCR failed: HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json() or {}
    pages = data.get("pages") or []
    if not isinstance(pages, list) or not pages:
        raise ValueError("Mistral OCR returned no pages.")

    def page_key(p: dict) -> int:
        try:
            return int(p.get("index", 0))
        except Exception:
            return 0

    chunks = []
    for p in sorted([x for x in pages if isinstance(x, dict)], key=page_key):
        md = str(p.get("markdown", "") or "").strip()
        if md:
            chunks.append(md)
    return "\n\n".join(chunks).strip()


def strip_markdown_images(md_text: str) -> str:
    text = md_text or ""
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
    text = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", text)
    text = re.sub(r"(?is)<img[^>]*>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def extract_paper_core_sections(md_text: str) -> str:
    text = (md_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    md_heading_re = re.compile(r"^(#{1,6})\s+(.*)\s*$")
    num_heading_re = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+([A-Za-z][A-Za-z0-9][A-Za-z0-9 \-:]{0,90})\s*$")

    def norm_title(title: str) -> str:
        t = (title or "").strip().lower()
        t = re.sub(r"^\s*(\d+(?:\.\d+)*|[ivx]+)\s*[\.\:\-]?\s*", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    headings = []
    for i, line in enumerate(lines):
        m = md_heading_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append({"i": i, "level": level, "title": title})
            continue

        if line.strip().lower() == "abstract":
            headings.append({"i": i, "level": 2, "title": "Abstract"})
            continue

        m = num_heading_re.match(line)
        if m and len(line) <= 120 and not line.strip().endswith("."):
            nums = m.group(1)
            title = m.group(2).strip()
            level = min(6, 2 + nums.count("."))
            headings.append({"i": i, "level": level, "title": title})

    if not headings:
        return strip_markdown_images(text)

    exclude_re = re.compile(r"\b(related\s*work|related\s*works|appendix|supplementary)\b", re.IGNORECASE)
    method_re = re.compile(r"\b(method|methods|approach|methodology|model|architecture|framework|algorithm)\b", re.IGNORECASE)
    exp_re = re.compile(r"\b(experiment|experiments|experimental|evaluation|results|ablation|benchmark|implementation|setup|dataset)\b", re.IGNORECASE)

    def want(title_norm: str) -> bool:
        if exclude_re.search(title_norm):
            return False
        if "abstract" in title_norm:
            return True
        if method_re.search(title_norm):
            return True
        if exp_re.search(title_norm):
            return True
        return False

    kept_blocks = []
    for idx, h in enumerate(headings):
        start = h["i"]
        level = h["level"]
        end = len(lines)
        for j in range(idx + 1, len(headings)):
            if headings[j]["level"] <= level:
                end = headings[j]["i"]
                break

        title_norm = norm_title(h["title"])
        if not want(title_norm):
            continue
        block = "\n".join(lines[start:end]).strip()
        if block:
            kept_blocks.append(block)

    if not kept_blocks:
        return strip_markdown_images(text)

    out = "# Paper (Abstract/Methods/Experiments)\n\n" + "\n\n".join(kept_blocks)
    return strip_markdown_images(out)


def convert_pdf_to_core_markdown_mistral(pdf_path: str) -> str:
    return extract_paper_core_sections(mistral_pdf_to_markdown(pdf_path))


def openreview_forum_url_to_id(openreview_url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    u = urlparse((openreview_url or "").strip())
    qs = parse_qs(u.query or "")
    forum_id = (qs.get("id", [""]) or [""])[0].strip() or (qs.get("forum", [""]) or [""])[0].strip()
    if not forum_id:
        raise ValueError("OpenReview link missing forum id (expected ?id=... or ?forum=...).")
    return forum_id


def fetch_openreview_reviews_markdown(openreview_url: str) -> str:
    try:
        import openreview
    except Exception as e:
        raise ValueError(f"openreview-py is not installed or failed to import: {type(e).__name__}: {e}")

    baseurl = (os.environ.get("OPENREVIEW_BASEURL") or "https://api2.openreview.net").strip()
    username = (os.environ.get("OPENREVIEW_USERNAME") or "").strip()
    password = (os.environ.get("OPENREVIEW_PASSWORD") or "").strip()

    forum_id = openreview_forum_url_to_id(openreview_url)

    kwargs = {"baseurl": baseurl}
    if username and password:
        kwargs.update({"username": username, "password": password})
    client = openreview.api.OpenReviewClient(**kwargs)
    notes = client.get_all_notes(forum=forum_id) or []

    def get_attr(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def note_time(n) -> int:
        for k in ("tcdate", "cdate", "tmdate", "mdate"):
            v = get_attr(n, k, None)
            if isinstance(v, (int, float)):
                return int(v)
        return 0

    def invitations(n) -> list[str]:
        vals = []

        single = get_attr(n, "invitation", None)
        if single:
            vals.append(str(single))

        multi = get_attr(n, "invitations", None) or []
        if isinstance(multi, str):
            multi = [multi]
        vals.extend(str(x) for x in multi if x)

        parent = get_attr(n, "parentInvitations", None)
        if isinstance(parent, str) and parent:
            vals.append(parent)
        elif isinstance(parent, list):
            vals.extend(str(x) for x in parent if x)

        seen = set()
        out = []
        for v in vals:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    def signature(n) -> str:
        sigs = get_attr(n, "signatures", None) or []
        if isinstance(sigs, list) and sigs:
            return str(sigs[0] or "")
        return str(get_attr(n, "id", "") or "")

    official_by_sig = {}
    meta_notes = []
    for n in notes:
        invs = [x.lower() for x in invitations(n)]
        if any("official_review" in inv for inv in invs):
            sig = signature(n) or str(get_attr(n, "id", "") or "")
            prev = official_by_sig.get(sig)
            if (prev is None) or (note_time(n) >= note_time(prev)):
                official_by_sig[sig] = n
        elif any("meta_review" in inv for inv in invs):
            meta_notes.append(n)

    def unwrap(v):
        if isinstance(v, dict) and "value" in v:
            return v.get("value")
        return v

    preferred_keys = ["rating", "confidence", "summary", "strengths", "weaknesses", "questions", "review"]

    def format_note_content(n) -> str:
        content = get_attr(n, "content", {}) or {}
        if not isinstance(content, dict):
            return str(content).strip()

        lines = []
        seen = set()

        def add_key(k: str) -> None:
            nonlocal lines
            if k in seen:
                return
            seen.add(k)
            raw = content.get(k)
            val = unwrap(raw)
            if val is None:
                return
            s = str(val).strip()
            if not s:
                return
            lines.append(f"### {k}\n{s}")

        for k in preferred_keys:
            add_key(k)
        for k in sorted([x for x in content.keys() if x not in seen]):
            add_key(k)

        return "\n\n".join(lines).strip()

    reviewer_nums = {}
    used = set()
    reviewer_re = re.compile(r"reviewer[_\s-]*(\d+)", re.IGNORECASE)
    for sig in sorted(official_by_sig.keys()):
        m = reviewer_re.search(sig)
        if m:
            num = int(m.group(1))
            reviewer_nums[sig] = num
            used.add(num)

    next_num = 1
    for sig in sorted(official_by_sig.keys()):
        if sig in reviewer_nums:
            continue
        while next_num in used:
            next_num += 1
        reviewer_nums[sig] = next_num
        used.add(next_num)
        next_num += 1

    md_lines = ["# Reviews (OpenReview)", ""]

    for sig, n in sorted(official_by_sig.items(), key=lambda kv: reviewer_nums.get(kv[0], 10**9)):
        num = reviewer_nums.get(sig, 1)
        md_lines.append(f"## Reviewer {num}")
        body = format_note_content(n)
        md_lines.append(body if body else "(empty)")
        md_lines.append("")

    if meta_notes:
        meta_notes = sorted(meta_notes, key=note_time)
        merged = []
        for n in meta_notes:
            body = format_note_content(n)
            if body:
                merged.append(body)
        if merged:
            md_lines.append("## Reviewer 0 (Meta Review)")
            md_lines.append("\n\n---\n\n".join(merged))
            md_lines.append("")

    if not official_by_sig and not meta_notes:
        raise ValueError("No Official_Review/Meta_Review notes found for this forum.")
    out = "\n".join(md_lines).strip()
    return out + "\n"


def _normalize_lookup_title(title: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", (title or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _title_similarity(query_title: str, candidate_title: str) -> float:
    query_norm = _normalize_lookup_title(query_title)
    candidate_norm = _normalize_lookup_title(candidate_title)
    if not query_norm or not candidate_norm:
        return 0.0
    if query_norm == candidate_norm:
        return 1.0
    if query_norm in candidate_norm or candidate_norm in query_norm:
        return 0.9
    query_tokens = set(query_norm.split())
    candidate_tokens = set(candidate_norm.split())
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / max(1, len(query_tokens | candidate_tokens))


def _strip_trailing_url_punctuation(url: str) -> str:
    return (url or "").strip().rstrip(").,;]>}")


def _url_hostname(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _absolute_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url, path)


def _download_url_bytes(url: str, timeout: int = 60, allow_proxy: bool = True) -> bytes:
    request_headers = dict(DEFAULT_DOWNLOAD_HEADERS)
    req = urllib.request.Request(url, headers=request_headers)
    host = _url_hostname(url)
    use_direct = (host in ARXIV_HOSTS) or any(host.endswith("." + h) for h in ARXIV_HOSTS)
    opener_open = ARXIV_DIRECT_OPENER.open if use_direct and allow_proxy else urllib.request.urlopen
    with opener_open(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_html_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_DOWNLOAD_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": DEFAULT_DOWNLOAD_HEADERS["Accept-Language"],
            "Referer": "https://openreview.net/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def download_pdf_to_local(
    pdf_url: str,
    output_dir: str,
    file_stem: str,
    source_label: str = "auto",
    max_retries: int = 3,
) -> str:
    pdf_url = (pdf_url or "").strip()
    if not pdf_url:
        raise ValueError("PDF URL is empty.")

    os.makedirs(output_dir, exist_ok=True)
    safe_stem = _safe_filename(f"{source_label}_{file_stem}".strip("_")) or f"{source_label}_paper"
    pdf_path = os.path.join(output_dir, f"{safe_stem}.pdf")

    if os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                if f.read(5) == b"%PDF-":
                    return pdf_path
        except Exception:
            pass

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep((attempt + 1) * 2 + random.uniform(0.3, 1.0))
            pdf_data = _download_url_bytes(pdf_url, timeout=60, allow_proxy=True)
            if len(pdf_data) < 100:
                raise ValueError(f"Downloaded file is too small: {len(pdf_data)} bytes")
            if not pdf_data.startswith(b"%PDF-"):
                raise ValueError(f"Downloaded file is not a valid PDF (header: {pdf_data[:20]!r})")
            with open(pdf_path, "wb") as f:
                f.write(pdf_data)
            return pdf_path
        except Exception as e:
            last_error = e
    raise ValueError(f"PDF download failed after {max_retries} attempts: {last_error}")


def _get_openreview_client():
    try:
        import openreview
    except Exception as e:
        raise ValueError(f"openreview-py is not installed or failed to import: {type(e).__name__}: {e}")

    baseurl = (os.environ.get("OPENREVIEW_BASEURL") or "https://api2.openreview.net").strip()
    username = (os.environ.get("OPENREVIEW_USERNAME") or "").strip()
    password = (os.environ.get("OPENREVIEW_PASSWORD") or "").strip()
    cache_key = (baseurl, username, password)
    client = _OPENREVIEW_CLIENT_CACHE.get(cache_key)
    if client is not None:
        return client

    kwargs = {"baseurl": baseurl}
    if username and password:
        kwargs.update({"username": username, "password": password})
    client = openreview.api.OpenReviewClient(**kwargs)
    _OPENREVIEW_CLIENT_CACHE[cache_key] = client
    return client


def _openreview_get_attr(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _unwrap_openreview_value(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _openreview_note_title(note) -> str:
    content = _openreview_get_attr(note, "content", {}) or {}
    if not isinstance(content, dict):
        return ""
    title = _unwrap_openreview_value(content.get("title"))
    return str(title or "").strip()


def _public_openreview_url(note_id: str, forum_id: str) -> Tuple[str, str]:
    note_id = str(note_id or "").strip()
    forum_id = str(forum_id or note_id).strip()
    return (
        f"https://openreview.net/pdf?id={note_id}" if note_id else "",
        f"https://openreview.net/forum?id={forum_id}" if forum_id else "",
    )


def _openreview_note_to_candidate(note, match_note: str) -> Optional[Dict[str, Any]]:
    note_id = str(_openreview_get_attr(note, "id", "") or "").strip()
    forum_id = str(_openreview_get_attr(note, "forum", "") or note_id).strip()
    replyto = str(_openreview_get_attr(note, "replyto", "") or "").strip()
    content = _openreview_get_attr(note, "content", {}) or {}
    title = _openreview_note_title(note)
    raw_pdf = ""
    if isinstance(content, dict):
        raw_pdf = str(_unwrap_openreview_value(content.get("pdf")) or "").strip()
    pdf_url, forum_url = _public_openreview_url(note_id, forum_id)
    if raw_pdf:
        pdf_url = _absolute_url("https://openreview.net", raw_pdf)
    if replyto and replyto != forum_id and not raw_pdf:
        return None
    if not note_id or not title or not pdf_url:
        return None
    return {
        "provider": "openreview",
        "title": title,
        "pdf_url": pdf_url,
        "resolved_url": forum_url or pdf_url,
        "paper_id": note_id,
        "forum_id": forum_id,
        "match_note": match_note,
    }


def _openreview_id_from_url(url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse((url or "").strip())
    query = parse_qs(parsed.query or "")
    for key in ("id", "forum", "noteId"):
        value = (query.get(key, [""]) or [""])[0].strip()
        if value:
            return value
    return ""


def _openreview_candidate_from_html(url: str) -> Optional[Dict[str, Any]]:
    try:
        html = _fetch_html_text(url, timeout=30)
    except Exception:
        return None

    def meta(name: str) -> str:
        match = re.search(
            rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        return unescape(match.group(1)).strip() if match else ""

    title = meta("citation_title")
    pdf_url = meta("citation_pdf_url")
    if not pdf_url:
        note_id = _openreview_id_from_url(url)
        if note_id:
            pdf_url = f"https://openreview.net/pdf?id={note_id}"
    note_id = _openreview_id_from_url(pdf_url) or _openreview_id_from_url(url)
    forum_id = _openreview_id_from_url(url) or note_id
    if not title or not pdf_url:
        return None
    return {
        "provider": "openreview",
        "title": title,
        "pdf_url": pdf_url,
        "resolved_url": f"https://openreview.net/forum?id={forum_id}" if forum_id else url,
        "paper_id": note_id or forum_id,
        "forum_id": forum_id,
        "match_note": "Matched from direct OpenReview link.",
    }


def _search_openreview_notes(term: str) -> List[Any]:
    term = " ".join((term or "").split()).strip()
    if not term:
        return []

    params = {
        "term": term,
        "type": "terms",
        "content": "all",
        "group": "all",
        "source": "all",
        "offset": 0,
        "limit": 10,
    }
    query_url = "https://openreview.net/search?query=" + urllib.parse.quote(term)
    headers = {
        "User-Agent": DEFAULT_DOWNLOAD_HEADERS["User-Agent"],
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": DEFAULT_DOWNLOAD_HEADERS["Accept-Language"],
        "Referer": query_url,
        "Origin": "https://openreview.net",
        "X-Url": query_url,
        "X-Source": "client search",
    }

    notes: List[Any] = []
    seen_ids = set()
    for base in ("https://api2.openreview.net", "https://api.openreview.net"):
        url = base + "/notes/search?" + urllib.parse.urlencode(params)
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20).read()
            payload = json.loads(raw.decode("utf-8", "ignore"))
        except Exception:
            continue
        for note in payload.get("notes", []) or []:
            note_id = str(_openreview_get_attr(note, "id", "") or "").strip()
            if not note_id or note_id in seen_ids:
                continue
            seen_ids.add(note_id)
            notes.append(note)
    return notes


def resolve_openreview_paper(
    direct_url: str = "",
    title: str = "",
) -> Optional[Dict[str, Any]]:
    client = _get_openreview_client()

    direct_url = _strip_trailing_url_punctuation(direct_url)
    if direct_url:
        note_id = _openreview_id_from_url(direct_url)
        if note_id:
            try:
                note = client.get_note(note_id)
                candidate = _openreview_note_to_candidate(note, "Matched from direct OpenReview link.")
                if candidate:
                    return candidate
            except Exception:
                try:
                    notes = client.get_all_notes(forum=note_id)
                except Exception:
                    notes = []
                for note in notes or []:
                    candidate = _openreview_note_to_candidate(note, "Matched from direct OpenReview forum link.")
                    if candidate:
                        return candidate
        html_candidate = _openreview_candidate_from_html(direct_url)
        if html_candidate:
            return html_candidate

    title = " ".join((title or "").split()).strip()
    if not title:
        return None

    best_candidate: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for note in _search_openreview_notes(title):
        candidate = _openreview_note_to_candidate(note, "Matched from OpenReview title search.")
        if not candidate:
            continue
        score = _title_similarity(title, candidate.get("title", ""))
        if score > best_score:
            best_candidate = candidate
            best_score = score
    if best_candidate and best_score >= 0.9:
        return best_candidate
    return None


def _cvf_targets(source_hint: str = "", direct_url: str = "") -> List[str]:
    source_hint = (source_hint or "").strip().lower()
    direct_url = (direct_url or "").strip()
    explicit = re.search(r"((?:cvpr|iccv|eccv|wacv)\d{4})", source_hint)
    if not explicit and direct_url:
        explicit = re.search(r"/((?:CVPR|ICCV|ECCV|WACV)\d{4})(?:[/?]|$)", direct_url, re.IGNORECASE)

    targets: List[str] = []
    if explicit:
        targets.append(explicit.group(1).upper())

    conf_hint_match = re.search(r"\b(cvpr|iccv|eccv|wacv)\b", source_hint)
    confs = [conf_hint_match.group(1).upper()] if conf_hint_match else ["CVPR", "ICCV", "ECCV", "WACV"]
    current_year = max(2020, time.localtime().tm_year)
    years = list(range(current_year, max(2019, current_year - 5), -1))

    for conf in confs:
        for year in years:
            conf_year = f"{conf}{year}"
            if conf_year not in targets:
                targets.append(conf_year)
    return targets


def _parse_cvf_search_results(conf_year: str, html_text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    entry_re = re.compile(
        r'<dt class="ptitle"><br><a href="(?P<html>[^"]+_paper\.html)">(?P<title>.*?)</a></dt>(?P<body>.*?)(?=<dt class="ptitle"|</dl>)',
        re.DOTALL | re.IGNORECASE,
    )
    for match in entry_re.finditer(html_text or ""):
        title = unescape(re.sub(r"<[^>]+>", "", match.group("title"))).strip()
        body = match.group("body") or ""
        pdf_match = re.search(r'href="(?P<pdf>[^"]+_paper\.pdf)"', body, re.IGNORECASE)
        html_path = match.group("html")
        pdf_path = pdf_match.group("pdf") if pdf_match else ""
        if not title or not html_path or not pdf_path:
            continue
        entries.append(
            {
                "provider": "cvf",
                "title": title,
                "resolved_url": _absolute_url(CVF_BASE_URL, html_path),
                "pdf_url": _absolute_url(CVF_BASE_URL, pdf_path),
                "paper_id": f"{conf_year}:{os.path.basename(pdf_path)}",
                "conf_year": conf_year,
                "match_note": "Matched from CVF title search.",
            }
        )
    return entries


def _search_cvf_conf_page(conf_year: str, query: str) -> List[Dict[str, str]]:
    cache_key = (conf_year, query.lower().strip())
    cached = _CVF_QUERY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    request_data = urllib.parse.urlencode({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        f"{CVF_BASE_URL}/{conf_year}",
        data=request_data,
        headers={"User-Agent": DEFAULT_DOWNLOAD_HEADERS["User-Agent"]},
        method="POST",
    )
    html_text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    entries = _parse_cvf_search_results(conf_year, html_text)
    _CVF_QUERY_CACHE[cache_key] = entries
    return entries


def _extract_title_from_cvf_html(html_url: str) -> str:
    html_text = urllib.request.urlopen(
        urllib.request.Request(html_url, headers={"User-Agent": DEFAULT_DOWNLOAD_HEADERS["User-Agent"]}),
        timeout=30,
    ).read().decode("utf-8", "ignore")
    match = re.search(r'<div id="papertitle">\s*(.*?)\s*<dd>', html_text, re.DOTALL | re.IGNORECASE)
    if match:
        return unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    title_match = re.search(r"<title>(.*?)</title>", html_text, re.DOTALL | re.IGNORECASE)
    if title_match:
        return unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
    return ""


def resolve_cvf_paper(
    direct_url: str = "",
    title: str = "",
    source_hint: str = "",
) -> Optional[Dict[str, Any]]:
    direct_url = _strip_trailing_url_punctuation(direct_url)
    host = _url_hostname(direct_url)

    if host in CVF_HOSTS:
        html_url = ""
        pdf_url = ""
        if direct_url.lower().endswith(".pdf"):
            pdf_url = direct_url
            html_url = direct_url.replace("/papers/", "/html/").replace("_paper.pdf", "_paper.html")
        elif direct_url.lower().endswith(".html"):
            html_url = direct_url
            pdf_url = direct_url.replace("/html/", "/papers/").replace("_paper.html", "_paper.pdf")
        else:
            html_url = direct_url
        candidate_title = title
        if html_url:
            try:
                fetched_title = _extract_title_from_cvf_html(html_url)
                if fetched_title:
                    candidate_title = fetched_title
            except Exception:
                pass
        if pdf_url and candidate_title:
            return {
                "provider": "cvf",
                "title": candidate_title,
                "pdf_url": pdf_url,
                "resolved_url": html_url or pdf_url,
                "paper_id": os.path.basename(pdf_url),
                "match_note": "Matched from direct CVF link.",
            }

    title = " ".join((title or "").split()).strip()
    if not title:
        return None

    seen = set()
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for conf_year in _cvf_targets(source_hint=source_hint, direct_url=direct_url):
        try:
            entries = _search_cvf_conf_page(conf_year, title)
        except Exception:
            continue
        for entry in entries:
            key = str(entry.get("resolved_url", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            score = _title_similarity(title, entry.get("title", ""))
            if score > best_score:
                best_candidate = dict(entry)
                best_score = score
        if best_score >= 0.95:
            break

    if best_candidate and best_score >= 0.85:
        return best_candidate
    return None


def resolve_comparison_paper_candidate(
    paper_title: str,
    direct_url: str = "",
    search_query: str = "",
    source_hint: str = "unknown",
) -> Optional[Dict[str, Any]]:
    paper_title = " ".join((paper_title or "").split()).strip()
    direct_url = _strip_trailing_url_punctuation(direct_url)
    search_query = " ".join((search_query or "").split()).strip()
    source_hint = (source_hint or "").strip().lower() or "unknown"

    direct_host = _url_hostname(direct_url)
    if direct_url:
        if direct_host in ARXIV_HOSTS:
            candidate = resolve_arxiv_paper(direct_url=direct_url, title=paper_title, search_query=search_query)
            if candidate:
                return candidate
        if direct_host in OPENREVIEW_HOSTS:
            candidate = resolve_openreview_paper(direct_url=direct_url, title=paper_title)
            if candidate:
                return candidate
        if direct_host in CVF_HOSTS:
            candidate = resolve_cvf_paper(direct_url=direct_url, title=paper_title, source_hint=source_hint)
            if candidate:
                return candidate

    provider_order = ["arxiv", "openreview", "cvf"]
    if source_hint in {"arxiv", "openreview", "cvf"}:
        provider_order = [source_hint] + [x for x in provider_order if x != source_hint]

    for provider in provider_order:
        if provider == "arxiv":
            candidate = resolve_arxiv_paper(title=paper_title, search_query=search_query)
        elif provider == "openreview":
            candidate = resolve_openreview_paper(title=paper_title)
        else:
            candidate = resolve_cvf_paper(title=paper_title, source_hint=source_hint)
        if candidate:
            return candidate
    return None


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', '_', name)[:100]

def download_pdf_and_convert_md(paper: dict, output_dir: str) -> str | None:
    """Download PDF and convert to Markdown.
    
    If download or conversion fails, creates a file containing paper metadata.
    Returns the file path.
    
    Args:
        paper: Dictionary containing paper metadata (title, arxiv_id, pdf_url, etc.)
        output_dir: Directory to save downloaded PDFs and converted Markdown files
    """
    papers_dir = output_dir
    
    if not os.path.exists(papers_dir):
        os.makedirs(papers_dir)
    
    def create_fallback_markdown_file(paper: dict, safe_name: str, error_msg: str = "") -> str:
        """Create a Markdown file containing basic paper information"""
        title = paper.get('title', 'Unknown Paper')
        abstract = paper.get('abstract', 'No abstract available')
        arxiv_id = paper.get('arxiv_id', 'N/A')
        pdf_url = paper.get('pdf_url', '')
        abs_url = paper.get('abs_url', '')
        authors = paper.get('authors', [])
        
        authors_str = ', '.join(authors) if authors else 'Unknown'
        
        md_content = f"""# {title}

**arXiv ID**: {arxiv_id}  
**Authors**: {authors_str}  
**PDF URL**: {pdf_url}  
**Abstract URL**: {abs_url}  

---

**Note**: PDF download or conversion failed. Only metadata is available.
{f"**Error**: {error_msg}" if error_msg else ""}

---

## Abstract

{abstract}

---

**Full text is not available. Please refer to the original paper via the URLs above.**
"""
        
        md_path = os.path.join(papers_dir, f"{safe_name}.md")
        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            print(f"[INFO] Created fallback Markdown file (metadata only): {md_path}")
            return md_path
        except Exception as e:
            print(f"[ERROR] Failed to create fallback Markdown: {e}")
            return None
    
    try:
        print(f"[DEBUG] Starting paper download: {paper.get('title', 'Unknown')[:60]}...")
        print(f"[DEBUG] arXiv ID: {paper.get('arxiv_id', 'N/A')}")
        
        title = paper.get('title') or paper.get('arxiv_id') or 'paper'
        arxiv_id = paper.get('arxiv_id') or ''
        base_name = f"{arxiv_id}_{title[:50]}" if arxiv_id else title[:50]
        safe = _safe_filename(base_name)
        
        pdf_url = paper.get('pdf_url') or ''
        if not pdf_url:
            abs_url = paper.get('abs_url') or ''
            if abs_url:
                pdf_url = abs_url.replace('/abs/', '/pdf/')
        if pdf_url and not pdf_url.endswith('.pdf'):
            pdf_url = pdf_url + '.pdf'
        
        if not pdf_url:
            print(f"[WARNING] Unable to get PDF URL, creating fallback Markdown")
            return create_fallback_markdown_file(paper, safe, "Unable to get PDF URL")
        
        print(f"[DEBUG] PDF URL: {pdf_url}")
        pdf_path = os.path.join(papers_dir, f"{safe}.pdf")
    
        try:
            if not os.path.exists(pdf_path):
                print(f"[DEBUG] Starting PDF download to: {pdf_path}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                parsed = urllib.parse.urlparse(pdf_url)
                host = (parsed.hostname or '').lower()
                use_direct = (host in ARXIV_HOSTS) or any(host.endswith('.' + h) for h in ARXIV_HOSTS)
                
                print(f"[DEBUG] Using proxy mode: {'DIRECT_OPENER' if use_direct else 'urlopen (with proxy)'}")
                
                opener_open = ARXIV_DIRECT_OPENER.open if use_direct else urllib.request.urlopen
                
                max_retries = 3
                retry_delay = 2 
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            wait_time = retry_delay * (attempt + 1) + random.uniform(0.5, 2.0)
                            print(f"[INFO] Waiting {wait_time:.1f} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                            time.sleep(wait_time)
                        
                        print(f"[DEBUG] Sending HTTP request (attempt {attempt + 1}/{max_retries})...")
                        req = urllib.request.Request(pdf_url, headers=headers)
                        
                        with opener_open(req, timeout=60) as resp:
                            pdf_data = resp.read()
                            print(f"[DEBUG] Download complete, size: {len(pdf_data)} bytes")
                            
                            if len(pdf_data) < 100:
                                print(f"[WARNING] Downloaded file is too small ({len(pdf_data)} bytes), may not be a valid PDF")
                                if attempt < max_retries - 1:
                                    continue
                                raise ValueError(f"Downloaded file is too small: {len(pdf_data)} bytes")
                            
                            if not pdf_data.startswith(b'%PDF-'):
                                print(f"[WARNING] Downloaded file is not a valid PDF (header: {pdf_data[:20]})")
                                if attempt < max_retries - 1:
                                    continue
                                raise ValueError("Downloaded file is not a valid PDF format")
                            
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_data)
                            print(f"[SUCCESS] PDF download successful: {pdf_path}")
                            break  
                            
                    except urllib.error.HTTPError as e:
                        error_msg = f"HTTP Error {e.code}: {e.reason}"
                        print(f"[WARNING] {error_msg}")
                        
                        if e.code == 403:
                            print(f"[TIP] 403 error usually indicates:")
                            print(f"  1. Request identified as bot (using real browser User-Agent)")
                            print(f"  2. IP temporarily rate-limited (retrying...)")
                            print(f"  3. Longer request interval needed")
                        
                        if attempt == max_retries - 1:
                            raise  
                    
                    except Exception as e:
                        print(f"[WARNING] Download exception: {type(e).__name__}: {e}")
                        if attempt == max_retries - 1:
                            raise  
                
                time.sleep(random.uniform(1.0, 3.0))
                
            else:
                print(f"[DEBUG] PDF already exists, skipping download: {pdf_path}")
                
        except Exception as e:
            print(f"[ERROR] PDF download failed (all retries exhausted): {type(e).__name__}: {e}")
            print(f"[INFO] Creating fallback Markdown (metadata only)")
            return create_fallback_markdown_file(paper, safe, f"PDF download failed: {str(e)}")
        
        print(f"[DEBUG] Starting PDF to Markdown conversion...")
        md_path = pdf_to_md(pdf_path, papers_dir)
        
        if md_path and os.path.isfile(md_path):
            print(f"[SUCCESS] Markdown conversion successful: {md_path}")
            return md_path
        else:
            print(f"[WARNING] Markdown conversion failed, creating fallback Markdown")
            return create_fallback_markdown_file(paper, safe, "PDF conversion failed")
        
    except Exception as e:
        print(f"[WARNING] download_pdf_and_convert_md exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            title = paper.get('title') or paper.get('arxiv_id') or 'paper'
            arxiv_id = paper.get('arxiv_id') or ''
            base_name = f"{arxiv_id}_{title[:50]}" if arxiv_id else title[:50]
            safe = _safe_filename(base_name)
            return create_fallback_markdown_file(paper, safe, f"Processing exception: {str(e)}")
        except:
            return None



_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(_CURRENT_DIR, "prompts")


import yaml

# Mapping from old prompt names to new YAML names
PROMPT_NAME_MAPPING = {
    "1.txt": "semantic_encoder.yaml",
    "2.txt": "issue_extractor.yaml",
    "2_c.txt": "issue_extractor_checker.yaml",
    "3.txt": "literature_retrieval.yaml",
    "4.txt": "reference_filter.yaml",
    "5.txt": "reference_analyzer.yaml",
    "6.txt": "strategy_generator.yaml",
    "7.txt": "strategy_reviewer.yaml",
    "7_h.txt": "strategy_human_refinement.yaml",
    "8.txt": "rebuttal_writer.yaml",
    "9.txt": "rebuttal_reviewer.yaml",
}

def load_prompt(name: str) -> str:
    """Load prompt from YAML or TXT file.
    
    Supports both new YAML format and legacy TXT format.
    For YAML files, extracts the 'prompt' field.
    """
    # Map old names to new names
    mapped_name = PROMPT_NAME_MAPPING.get(name, name)
    prompt_path = os.path.join(PROMPTS_DIR, mapped_name)
    
    # Try YAML first, then fall back to original name
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(PROMPTS_DIR, name)
    
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # If it's a YAML file, extract the prompt field
    if prompt_path.endswith('.yaml') or prompt_path.endswith('.yml'):
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'prompt' in data:
                return data['prompt']
            return content
        except yaml.YAMLError:
            return content
    
    return content
