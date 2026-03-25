import sys
import os

os.environ["OMP_NUM_THREADS"] = "4"

DOCLING_DEVICE = os.environ.get("DOCLING_DEVICE", "cpu").lower()

import re
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.parse
import threading
from typing import Any, Dict, List, Optional
from arxiv import _extract_arxiv_id_from_url, _fetch_metadata_by_id, search_relevant_papers

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ARXIV_DIRECT_OPENER = urllib.request.build_opener()
ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
OPENREVIEW_HOSTS = {"openreview.net", "api2.openreview.net"}
CVF_HOSTS = {"openaccess.thecvf.com", "thecvf.com", "www.thecvf.com"}
CVF_CONFERENCES = ("CVPR", "ICCV", "ECCV", "WACV")
CVF_INDEX_CACHE = {}
            
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


def _http_get_text(url: str, timeout: int = 30) -> str:
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _unwrap_openreview_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _normalize_search_text(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", " ", str(text or "").lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _comparison_match_score(query: str, title: str) -> float:
    query_norm = _normalize_search_text(query)
    title_norm = _normalize_search_text(title)
    if not query_norm or not title_norm:
        return 0.0
    if query_norm == title_norm:
        return 1.0
    if query_norm in title_norm or title_norm in query_norm:
        return 0.92 if len(query_norm.split()) >= 2 else 0.78

    query_tokens = set(query_norm.split())
    title_tokens = set(title_norm.split())
    if not query_tokens or not title_tokens:
        return 0.0

    overlap = len(query_tokens & title_tokens)
    union = len(query_tokens | title_tokens)
    score = overlap / max(1, union)
    if len(query_tokens) <= 3 and query_tokens.issubset(title_tokens):
        score = max(score, 0.8)
    return score


def _is_probable_url(text: str) -> bool:
    try:
        parsed = urllib.parse.urlparse((text or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _hostname_from_url(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _dedupe_paper_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(candidates, key=lambda x: float(x.get("score", 0.0)), reverse=True):
        source = str(item.get("source", "") or "")
        title_key = _normalize_search_text(item.get("title", ""))
        page_key = str(item.get("abs_url", "") or item.get("pdf_url", "") or "")
        key = (source, title_key, page_key)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _candidate_to_saved_hit(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": str(item.get("source", "") or ""),
        "title": str(item.get("title", "") or ""),
        "abs_url": str(item.get("abs_url", "") or ""),
        "pdf_url": str(item.get("pdf_url", "") or ""),
        "paper_id": str(item.get("paper_id", "") or ""),
        "score": round(float(item.get("score", 0.0)), 4),
    }


def _should_auto_download(query: str, candidate: Dict[str, Any]) -> bool:
    reason = str(candidate.get("match_reason", "") or "")
    score = float(candidate.get("score", 0.0) or 0.0)
    query_norm = _normalize_search_text(query)
    title_norm = _normalize_search_text(candidate.get("title", ""))

    if reason == "direct_url":
        return True
    if score >= 0.86:
        return True
    if query_norm and len(query_norm.split()) <= 3 and query_norm in title_norm and score >= 0.72:
        return True
    return False


def _build_openreview_client():
    import openreview

    baseurl = (os.environ.get("OPENREVIEW_BASEURL") or "https://api2.openreview.net").strip()
    username = (os.environ.get("OPENREVIEW_USERNAME") or "").strip()
    password = (os.environ.get("OPENREVIEW_PASSWORD") or "").strip()

    kwargs = {"baseurl": baseurl}
    if username and password:
        kwargs.update({"username": username, "password": password})
    return openreview.api.OpenReviewClient(**kwargs)


def _openreview_note_to_paper(note: Any) -> Dict[str, Any]:
    content = getattr(note, "content", {}) or {}
    title = str(_unwrap_openreview_value(content.get("title", "")) or "").strip()
    abstract = str(_unwrap_openreview_value(content.get("abstract", "")) or "").strip()
    raw_authors = _unwrap_openreview_value(content.get("authors", [])) or []
    if isinstance(raw_authors, str):
        authors = [raw_authors]
    else:
        authors = [str(x).strip() for x in raw_authors if str(x).strip()]

    note_id = str(getattr(note, "id", "") or "").strip()
    forum_id = str(getattr(note, "forum", "") or "").strip() or note_id
    created_at = getattr(note, "cdate", None) or getattr(note, "tcdate", None)
    published = ""
    if isinstance(created_at, (int, float)):
        published = time.strftime("%Y-%m-%d", time.localtime(created_at / 1000 if created_at > 10**12 else created_at))

    return {
        "source": "openreview",
        "paper_id": note_id or forum_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "abs_url": f"https://openreview.net/forum?id={forum_id}" if forum_id else "",
        "pdf_url": f"https://openreview.net/pdf?id={note_id or forum_id}" if (note_id or forum_id) else "",
        "published": published,
    }


def fetch_openreview_submission_markdown(openreview_url: str) -> Optional[Dict[str, Any]]:
    try:
        forum_id = openreview_forum_url_to_id(openreview_url)
        client = _build_openreview_client()
        try:
            note = client.get_note(forum_id)
        except Exception:
            notes = client.get_all_notes(forum=forum_id) or []
            note = None
            for item in notes:
                if str(getattr(item, "id", "") or "") == forum_id:
                    note = item
                    break
            if note is None and notes:
                note = notes[0]
        if note is None:
            return None
        paper = _openreview_note_to_paper(note)
        paper["match_reason"] = "direct_url"
        paper["score"] = 1.0
        return paper
    except Exception:
        return None


def search_openreview_papers(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    query_text = str(query or "").strip()
    if not query_text:
        return []
    if _is_probable_url(query_text):
        item = fetch_openreview_submission_markdown(query_text)
        return [item] if item else []

    try:
        client = _build_openreview_client()
        notes = client.get_notes(content={"title": query_text}, limit=max_results) or []
    except Exception:
        return []

    results: List[Dict[str, Any]] = []
    for note in notes:
        paper = _openreview_note_to_paper(note)
        if not paper.get("title"):
            continue
        paper["score"] = _comparison_match_score(query_text, paper.get("title", ""))
        paper["match_reason"] = "exact_title"
        results.append(paper)
    return _dedupe_paper_candidates(results)[:max_results]


def _derive_cvf_html_url(url: str) -> str:
    if not url:
        return ""
    if url.endswith(".html"):
        return url
    if url.endswith(".pdf"):
        return url.replace("/papers/", "/html/").replace(".pdf", ".html")
    return url


def _derive_cvf_pdf_url(url: str) -> str:
    if not url:
        return ""
    if url.endswith(".pdf"):
        return url
    if url.endswith(".html"):
        return url.replace("/html/", "/papers/").replace(".html", ".pdf")
    return url


def _fetch_cvf_paper_page(url: str) -> Optional[Dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup

        html_url = _derive_cvf_html_url(url)
        soup = BeautifulSoup(_http_get_text(html_url, timeout=40), "html.parser")

        def meta_value(name: str) -> str:
            tag = soup.find("meta", attrs={"name": name})
            return str(tag.get("content", "") or "").strip() if tag else ""

        title = meta_value("citation_title")
        abstract = meta_value("citation_abstract")
        authors = [
            str(tag.get("content", "") or "").strip()
            for tag in soup.find_all("meta", attrs={"name": "citation_author"})
            if str(tag.get("content", "") or "").strip()
        ]
        pdf_url = meta_value("citation_pdf_url") or _derive_cvf_pdf_url(html_url)
        if pdf_url and pdf_url.startswith("/"):
            pdf_url = urllib.parse.urljoin(html_url, pdf_url)

        paper_id = os.path.splitext(os.path.basename(_derive_cvf_pdf_url(pdf_url or html_url)))[0]
        return {
            "source": "cvf",
            "paper_id": paper_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "abs_url": html_url,
            "pdf_url": pdf_url,
            "published": "",
        }
    except Exception:
        return None


def _fetch_cvf_index(conference: str, year: int) -> List[Dict[str, Any]]:
    cache_key = f"{conference}{year}"
    if cache_key in CVF_INDEX_CACHE:
        return CVF_INDEX_CACHE[cache_key]

    try:
        from bs4 import BeautifulSoup
    except Exception:
        CVF_INDEX_CACHE[cache_key] = []
        return []

    url = f"https://openaccess.thecvf.com/{conference}{year}?day=all"
    try:
        soup = BeautifulSoup(_http_get_text(url, timeout=40), "html.parser")
    except Exception:
        CVF_INDEX_CACHE[cache_key] = []
        return []

    items: List[Dict[str, Any]] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "") or "").strip()
        if "/content/" not in href or not href.endswith(".html"):
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if len(title) < 8:
            continue
        abs_url = urllib.parse.urljoin(url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        pdf_url = _derive_cvf_pdf_url(abs_url)
        paper_id = os.path.splitext(os.path.basename(pdf_url))[0]
        items.append(
            {
                "source": "cvf",
                "paper_id": paper_id,
                "title": title,
                "abstract": "",
                "authors": [],
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "published": f"{conference} {year}",
            }
        )

    CVF_INDEX_CACHE[cache_key] = items
    return items


def _candidate_cvf_years(query: str) -> List[int]:
    current_year = time.localtime().tm_year
    years = [int(x) for x in re.findall(r"\b(20\d{2})\b", str(query or ""))]
    if years:
        base = years[0]
        ordered = [base, base + 1, base - 1]
    else:
        ordered = [current_year, current_year - 1, current_year - 2]

    output = []
    seen = set()
    for year in ordered:
        if year < 2018 or year > current_year:
            continue
        if year in seen:
            continue
        seen.add(year)
        output.append(year)
    return output


def _candidate_cvf_conferences(query: str) -> List[str]:
    query_upper = str(query or "").upper()
    hinted = [conf for conf in CVF_CONFERENCES if conf in query_upper]
    if hinted:
        return hinted
    return list(CVF_CONFERENCES)


def search_cvf_papers(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    query_text = str(query or "").strip()
    if not query_text:
        return []
    if _is_probable_url(query_text) and _hostname_from_url(query_text) in CVF_HOSTS:
        item = _fetch_cvf_paper_page(query_text)
        if item:
            item["score"] = 1.0
            item["match_reason"] = "direct_url"
            return [item]
        return []

    candidates: List[Dict[str, Any]] = []
    pages_checked = 0
    for conference in _candidate_cvf_conferences(query_text):
        for year in _candidate_cvf_years(query_text):
            pages_checked += 1
            for item in _fetch_cvf_index(conference, year):
                score = _comparison_match_score(query_text, item.get("title", ""))
                if score < 0.42:
                    continue
                candidate = dict(item)
                candidate["score"] = score
                candidate["match_reason"] = "search"
                candidates.append(candidate)
            if pages_checked >= 6:
                break
        strong_hits = [x for x in candidates if float(x.get("score", 0.0)) >= 0.8]
        if len(strong_hits) >= max_results or pages_checked >= 6:
            break

    output: List[Dict[str, Any]] = []
    for item in _dedupe_paper_candidates(candidates):
        if len(output) >= max_results:
            break
        enriched = _fetch_cvf_paper_page(item.get("abs_url", "")) or item
        enriched["score"] = float(item.get("score", 0.0))
        enriched["match_reason"] = str(item.get("match_reason", "") or "search")
        output.append(enriched)
    return output


def _paper_from_arxiv_url(url: str) -> Optional[Dict[str, Any]]:
    arxiv_id = _extract_arxiv_id_from_url(url)
    if not arxiv_id:
        return None
    data = _fetch_metadata_by_id(arxiv_id)
    if not data:
        return None
    data["source"] = "arxiv"
    data["paper_id"] = str(data.get("arxiv_id", "") or arxiv_id)
    data["match_reason"] = "direct_url"
    data["score"] = 1.0
    return data


def search_arxiv_comparison_papers(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    query_text = str(query or "").strip()
    if not query_text:
        return []
    if _is_probable_url(query_text) and _hostname_from_url(query_text) in ARXIV_HOSTS:
        item = _paper_from_arxiv_url(query_text)
        return [item] if item else []

    candidates: List[Dict[str, Any]] = []
    for field_name in ("title", "all"):
        try:
            papers = search_relevant_papers(query_text, max_results=max_results, field=field_name)
        except Exception:
            papers = []
        for paper in papers:
            item = dict(paper)
            item["source"] = "arxiv"
            item["paper_id"] = str(item.get("arxiv_id", "") or "")
            item["score"] = _comparison_match_score(query_text, item.get("title", ""))
            item["match_reason"] = f"search_{field_name}"
            candidates.append(item)
    return _dedupe_paper_candidates(candidates)[:max_results]


def resolve_comparison_paper(query: str, output_dir: str, max_results_per_source: int = 3) -> Dict[str, Any]:
    query_text = str(query or "").strip()
    if not query_text:
        return {"hits": [], "resolved_source": "", "resolved_md_path": ""}

    candidates: List[Dict[str, Any]] = []
    hostname = _hostname_from_url(query_text) if _is_probable_url(query_text) else ""
    if hostname in ARXIV_HOSTS:
        item = _paper_from_arxiv_url(query_text)
        if item:
            candidates.append(item)
    elif hostname in OPENREVIEW_HOSTS:
        item = fetch_openreview_submission_markdown(query_text)
        if item:
            candidates.append(item)
    elif hostname in CVF_HOSTS:
        item = _fetch_cvf_paper_page(query_text)
        if item:
            item["score"] = 1.0
            item["match_reason"] = "direct_url"
            candidates.append(item)
    else:
        candidates.extend(search_arxiv_comparison_papers(query_text, max_results=max_results_per_source))
        candidates.extend(search_openreview_papers(query_text, max_results=max_results_per_source))
        candidates.extend(search_cvf_papers(query_text, max_results=max_results_per_source))

    ranked = _dedupe_paper_candidates(candidates)
    ranked.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    top_hits = ranked[:max_results_per_source]

    resolved_source = ""
    resolved_md_path = ""
    if top_hits and _should_auto_download(query_text, top_hits[0]):
        os.makedirs(output_dir, exist_ok=True)
        resolved_md_path = download_pdf_and_convert_md(top_hits[0], output_dir, convert_to_markdown=False) or ""
        if resolved_md_path:
            resolved_source = str(top_hits[0].get("source", "") or "")

    return {
        "hits": [_candidate_to_saved_hit(item) for item in top_hits],
        "resolved_source": resolved_source,
        "resolved_md_path": resolved_md_path,
    }


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', '_', name)[:100]

def download_pdf_and_convert_md(paper: dict, output_dir: str, convert_to_markdown: bool = True) -> str | None:
    """Download a paper PDF and convert it to Markdown.

    If download or conversion fails, creates a fallback Markdown file containing
    the available metadata and URLs.
    """
    papers_dir = output_dir
    
    if not os.path.exists(papers_dir):
        os.makedirs(papers_dir)
    
    def create_fallback_markdown_file(paper: dict, safe_name: str, error_msg: str = "") -> str:
        """Create a Markdown file containing basic paper information"""
        title = paper.get('title', 'Unknown Paper')
        abstract = paper.get('abstract', 'No abstract available')
        source = paper.get('source', 'unknown')
        paper_id = paper.get('paper_id') or paper.get('arxiv_id') or 'N/A'
        pdf_url = paper.get('pdf_url', '')
        abs_url = paper.get('abs_url') or paper.get('source_url') or ''
        authors = paper.get('authors', [])
        published = paper.get('published', '')
        
        authors_str = ', '.join(authors) if authors else 'Unknown'
        
        md_content = f"""# {title}

**Source**: {source}  
**Paper ID**: {paper_id}  
**Authors**: {authors_str}  
**Published**: {published}  
**PDF URL**: {pdf_url}  
**Page URL**: {abs_url}  

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
        print(f"[DEBUG] Source: {paper.get('source', 'unknown')}, paper_id: {paper.get('paper_id') or paper.get('arxiv_id', 'N/A')}")
        
        title = paper.get('title') or paper.get('paper_id') or paper.get('arxiv_id') or 'paper'
        paper_id = paper.get('paper_id') or paper.get('arxiv_id') or ''
        base_name = f"{paper_id}_{title[:50]}" if paper_id else title[:50]
        safe = _safe_filename(base_name)
        
        pdf_url = paper.get('pdf_url') or ''
        if not pdf_url:
            abs_url = paper.get('abs_url') or ''
            if abs_url:
                pdf_url = abs_url.replace('/abs/', '/pdf/')
        if pdf_url and not pdf_url.endswith('.pdf'):
            pdf_url = pdf_url + '.pdf'
        
        if not pdf_url:
            print(f"[WARNING] Unable to get PDF URL")
            if not convert_to_markdown:
                return None
            print(f"[INFO] Creating fallback Markdown (metadata only)")
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
            if not convert_to_markdown:
                return None
            print(f"[INFO] Creating fallback Markdown (metadata only)")
            return create_fallback_markdown_file(paper, safe, f"PDF download failed: {str(e)}")
        
        if not convert_to_markdown:
            return pdf_path

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
        if not convert_to_markdown:
            return None
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
