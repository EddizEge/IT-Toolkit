from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from app_v2 import __version__
from app_v2.services.error_logging import (
    public_environment_summary,
    sanitize_text,
)

GITHUB_ISSUE_URL = "https://github.com/EddizEge/IT-Toolkit/issues/new"
FEEDBACK_TEMPLATE = "app_feedback.yml"
MAX_ISSUE_URL_LENGTH = 7_500


@dataclass(frozen=True)
class FeedbackDraft:
    category: str
    title: str
    details: str
    steps: str = ""
    diagnostics: str = ""


def feedback_report_text(draft: FeedbackDraft) -> str:
    category = sanitize_text(draft.category.strip()) or "Genel"
    title = sanitize_text(draft.title.strip()) or "Başlıksız geri bildirim"
    details = sanitize_text(draft.details.strip()) or "Açıklama eklenmedi."
    steps = sanitize_text(draft.steps.strip()) or "Belirtilmedi."
    diagnostics = sanitize_text(draft.diagnostics.strip()) or "Eklenmedi."
    return "\n".join(
        (
            "IT Toolkit Uygulama Geri Bildirimi",
            "=" * 36,
            f"Kategori: {category}",
            f"Başlık: {title}",
            f"Sürüm: v{__version__}",
            "",
            "Açıklama",
            "-" * 20,
            details,
            "",
            "Yeniden üretme adımları",
            "-" * 20,
            steps,
            "",
            "Ortam ve maskelenmiş günlük",
            "-" * 20,
            diagnostics,
        )
    )


def _issue_parameters(
    draft: FeedbackDraft,
    diagnostics: str,
) -> dict[str, str]:
    return {
        "template": FEEDBACK_TEMPLATE,
        "title": (
            "[Uygulama Geri Bildirimi] "
            f"{sanitize_text(draft.title.strip())[:100]}"
        ),
        "category": sanitize_text(draft.category.strip())[:120],
        "version": f"v{__version__}",
        "windows_info": public_environment_summary(),
        "details": sanitize_text(draft.details.strip())[:4_000],
        "steps": sanitize_text(draft.steps.strip())[:2_500],
        "diagnostics": diagnostics,
    }


def github_issue_url(draft: FeedbackDraft) -> str:
    diagnostics = sanitize_text(draft.diagnostics.strip())
    parameters = _issue_parameters(draft, diagnostics)

    def encoded_url() -> str:
        return f"{GITHUB_ISSUE_URL}?{urlencode(parameters)}"

    url = encoded_url()
    truncation_order = ("diagnostics", "steps", "details")
    for key in truncation_order:
        while len(url) > MAX_ISSUE_URL_LENGTH and parameters[key]:
            previous_length = len(url)
            value = parameters[key]
            keep = max(0, len(value) - max(200, len(url) - MAX_ISSUE_URL_LENGTH))
            if key == "diagnostics":
                marker = (
                    "[Bağlantı sınırı nedeniyle son bölüm gösteriliyor; "
                    "tam rapor panoda]\n"
                )
                parameters[key] = marker + value[-keep:] if keep else marker
            else:
                marker = "\n[Bağlantı sınırı nedeniyle kısaltıldı]"
                parameters[key] = value[:keep] + marker if keep else marker
            url = encoded_url()
            if len(url) >= previous_length:
                parameters[key] = ""
                url = encoded_url()
                break
    return url
