from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app_v2.presets import TechnicianPreset
from app_v2.registry import ToggleAction, ToolAction

VALID_RISKS = frozenset({"normal", "caution", "danger"})


@dataclass(frozen=True, slots=True)
class OperationImpact:
    key: str
    title: str
    risk: str
    risk_label: str
    effect: str
    target: str
    admin_required: bool
    interruption: str
    rollback: str
    confirmation_stages: int

    def __post_init__(self) -> None:
        _validate_risk(self.risk)
        expected_stages = confirmation_stage_count(
            self.risk,
            admin_required=self.admin_required,
        )
        if self.confirmation_stages != expected_stages:
            raise ValueError(
                "Risk ve yetki bilgisiyle çelişen onay aşaması: "
                f"{self.key}"
            )

    @property
    def is_critical(self) -> bool:
        return self.risk == "danger"


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    action_key: str
    title: str
    category: str
    command: str
    urls: tuple[str, ...]
    admin_required: bool
    keep_open: bool
    success_codes: tuple[int, ...]
    impact: OperationImpact


def _validate_risk(risk: str) -> None:
    if risk not in VALID_RISKS:
        raise ValueError(f"Geçersiz işlem risk seviyesi: {risk}")


def confirmation_stage_count(risk: str, *, admin_required: bool) -> int:
    _validate_risk(risk)
    if risk == "danger":
        return 2
    if risk == "caution" or admin_required:
        return 1
    return 0


def _risk_label(risk: str) -> str:
    return {
        "normal": "BİLGİ",
        "caution": "DİKKAT",
        "danger": "KRİTİK",
    }[risk]


def _default_interruption(risk: str) -> str:
    if risk == "danger":
        return "İşlem sırasında hizmet, uygulama veya oturum kesintisi oluşabilir."
    if risk == "caution":
        return "Kısa süreli kesinti olabilir; açık çalışmalarınızı kaydedin."
    return "Belirgin bir kesinti beklenmiyor."


def _default_rollback(risk: str) -> str:
    if risk == "danger":
        return "Bu kritik işlem için otomatik geri alma tanımlı değildir."
    return (
        "Otomatik geri alma henüz tanımlı değil; sonucu Görev Merkezi'nden "
        "doğrulayın."
    )


def impact_for_action(
    action: ToolAction,
    *,
    target: str | None = None,
    admin_required: bool | None = None,
    effect: str | None = None,
    interruption: str | None = None,
    rollback: str | None = None,
) -> OperationImpact:
    _validate_risk(action.risk)
    resolved_admin = action.admin if admin_required is None else admin_required
    return OperationImpact(
        key=action.key,
        title=action.title,
        risk=action.risk,
        risk_label=_risk_label(action.risk),
        effect=(effect or "").strip() or action.impact.strip() or action.description,
        target=target.strip() if target and target.strip() else action.category,
        admin_required=resolved_admin,
        interruption=(
            (interruption or "").strip()
            or action.interruption.strip()
            or _default_interruption(action.risk)
        ),
        rollback=(
            (rollback or "").strip()
            or action.rollback.strip()
            or _default_rollback(action.risk)
        ),
        confirmation_stages=confirmation_stage_count(
            action.risk,
            admin_required=resolved_admin,
        ),
    )


def execution_plan_for_action(
    action: ToolAction,
    *,
    command: str | None = None,
    urls: Iterable[str] = (),
    target: str | None = None,
    admin_required: bool | None = None,
    keep_open: bool | None = None,
    success_codes: Iterable[int] = (0,),
    effect: str | None = None,
    interruption: str | None = None,
    rollback: str | None = None,
) -> ExecutionPlan:
    resolved_admin = action.admin if admin_required is None else admin_required
    if action.admin and not resolved_admin:
        raise ValueError(
            f"Kayıtlı yönetici gereksinimi düşürülemez: {action.key}"
        )
    resolved_command = action.command if command is None else command
    resolved_urls = tuple(url.strip() for url in urls if url.strip())
    if not resolved_command.strip() and not resolved_urls:
        raise ValueError(f"Çalıştırılabilir işlem planı boş: {action.key}")
    resolved_success_codes = tuple(success_codes)
    if not resolved_success_codes:
        raise ValueError(f"Başarı kodu olmayan işlem planı: {action.key}")
    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        action_key=action.key,
        title=action.title,
        category=action.category,
        command=resolved_command,
        urls=resolved_urls,
        admin_required=resolved_admin,
        keep_open=action.keep_open if keep_open is None else keep_open,
        success_codes=resolved_success_codes,
        impact=impact_for_action(
            action,
            target=target,
            admin_required=resolved_admin,
            effect=effect,
            interruption=interruption,
            rollback=rollback,
        ),
    )


def impact_for_toggle(
    toggle: ToggleAction,
    enabled: bool,
) -> OperationImpact:
    directional_risk = (
        toggle.risk_on if enabled else toggle.risk_off
    ).strip() or toggle.risk
    _validate_risk(directional_risk)
    target_state = "açılacak" if enabled else "kapatılacak"
    explicit_impact = toggle.impact_on if enabled else toggle.impact_off
    inverse_state = "kapatılarak" if enabled else "açılarak"
    return OperationImpact(
        key=f"toggle:{toggle.key}:{'on' if enabled else 'off'}",
        title=toggle.title,
        risk=directional_risk,
        risk_label=_risk_label(directional_risk),
        effect=(
            explicit_impact.strip()
            or f"{toggle.title} ayarı {target_state}. {toggle.description}"
        ),
        target="Windows temel ayarları",
        admin_required=True,
        interruption=(
            toggle.interruption.strip()
            or _default_interruption(directional_risk)
        ),
        rollback=(
            toggle.rollback.strip()
            or f"Ayar ters yönde {inverse_state} önceki duruma döndürülebilir."
        ),
        confirmation_stages=confirmation_stage_count(
            directional_risk,
            admin_required=True,
        ),
    )


def impact_for_preset(preset: TechnicianPreset) -> OperationImpact:
    _validate_risk(preset.risk)
    return OperationImpact(
        key=f"preset:{preset.key}",
        title=preset.title,
        risk=preset.risk,
        risk_label=_risk_label(preset.risk),
        effect=preset.impact.strip() or preset.description,
        target="Teknisyen hazır akışı",
        admin_required=preset.admin,
        interruption=(
            preset.interruption.strip()
            or _default_interruption(preset.risk)
        ),
        rollback=preset.rollback.strip() or _default_rollback(preset.risk),
        confirmation_stages=confirmation_stage_count(
            preset.risk,
            admin_required=preset.admin,
        ),
    )
