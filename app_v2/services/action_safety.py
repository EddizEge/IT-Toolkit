from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from app_v2.presets import PRESET_LOOKUP, TechnicianPreset
from app_v2.registry import (
    ACTION_LOOKUP,
    TOGGLE_LOOKUP,
    ToggleAction,
    ToolAction,
)

VALID_RISKS = frozenset({"normal", "caution", "danger"})
VALID_RESTORE_POINT_MODES = frozenset({"none", "optional"})
VALID_UNDO_MODES = frozenset(
    {"not_applicable", "available", "unavailable"}
)
UNDOABLE_TOGGLE_KEYS = frozenset(
    {"windows_update", "hibernation", "smb1", "usb_write_protect"}
)
PLAN_ID_LENGTH = 32


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    restore_point_mode: str = "none"
    undo_mode: str = "not_applicable"
    undo_key: str = ""
    unavailable_reason: str = ""

    def __post_init__(self) -> None:
        if self.restore_point_mode not in VALID_RESTORE_POINT_MODES:
            raise ValueError(
                "Geçersiz geri yükleme noktası politikası: "
                f"{self.restore_point_mode}"
            )
        if self.undo_mode not in VALID_UNDO_MODES:
            raise ValueError(f"Geçersiz geri alma politikası: {self.undo_mode}")
        if self.undo_mode == "available":
            if not self.undo_key or self.unavailable_reason:
                raise ValueError("Kullanılabilir geri alma politikası tutarsız.")
        elif self.undo_mode == "unavailable":
            if self.undo_key or not self.unavailable_reason.strip():
                raise ValueError("Kullanılamayan geri alma politikası tutarsız.")
        elif self.undo_key or self.unavailable_reason:
            raise ValueError("Uygulanamaz geri alma politikası tutarsız.")


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
    recovery: RecoveryPolicy = field(default_factory=RecoveryPolicy)

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
    parent_plan_id: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.plan_id, str)
            or len(self.plan_id) != PLAN_ID_LENGTH
        ):
            raise ValueError("Geçersiz işlem planı kimliği.")
        try:
            int(self.plan_id, 16)
        except ValueError as exc:
            raise ValueError("Geçersiz işlem planı kimliği.") from exc
        if self.plan_id != self.plan_id.lower():
            raise ValueError("Geçersiz işlem planı kimliği.")
        if not isinstance(self.parent_plan_id, str):
            raise TypeError("Üst işlem planı kimliği metin olmalıdır.")
        if self.parent_plan_id:
            if (
                len(self.parent_plan_id) != PLAN_ID_LENGTH
                or self.parent_plan_id != self.parent_plan_id.lower()
            ):
                raise ValueError("Geçersiz üst işlem planı kimliği.")
            try:
                int(self.parent_plan_id, 16)
            except ValueError as exc:
                raise ValueError("Geçersiz üst işlem planı kimliği.") from exc
            if self.parent_plan_id == self.plan_id:
                raise ValueError("İşlem planı kendisine bağlanamaz.")


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


def _recovery_policy(
    *,
    restore_point_mode: str,
    undo_key: str = "",
    unavailable_reason: str = "",
    applicable: bool,
) -> RecoveryPolicy:
    if undo_key:
        return RecoveryPolicy(
            restore_point_mode=restore_point_mode,
            undo_mode="available",
            undo_key=undo_key,
        )
    if applicable:
        return RecoveryPolicy(
            restore_point_mode=restore_point_mode,
            undo_mode="unavailable",
            unavailable_reason=unavailable_reason,
        )
    return RecoveryPolicy(restore_point_mode=restore_point_mode)


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
    rollback_text = (
        (rollback or "").strip()
        or action.rollback.strip()
        or _default_rollback(action.risk)
    )
    recovery = _recovery_policy(
        restore_point_mode=action.restore_point_policy,
        undo_key=action.undo_key.strip(),
        unavailable_reason=rollback_text,
        applicable=(
            action.risk != "normal"
            or resolved_admin
            or bool(action.undo_key.strip())
        ),
    )
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
        rollback=rollback_text,
        confirmation_stages=confirmation_stage_count(
            action.risk,
            admin_required=resolved_admin,
        ),
        recovery=recovery,
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
    *,
    previous_enabled: bool | None = None,
) -> OperationImpact:
    directional_risk = (
        toggle.risk_on if enabled else toggle.risk_off
    ).strip() or toggle.risk
    _validate_risk(directional_risk)
    target_state = "açılacak" if enabled else "kapatılacak"
    explicit_impact = toggle.impact_on if enabled else toggle.impact_off
    inverse_state = "kapatılarak" if enabled else "açılarak"
    rollback_text = (
        toggle.rollback.strip()
        or f"Ayar ters yönde {inverse_state} önceki duruma döndürülebilir."
    )
    undo_key = (
        f"toggle:{toggle.key}:{'on' if previous_enabled else 'off'}"
        if (
            toggle.key in UNDOABLE_TOGGLE_KEYS
            and previous_enabled is not None
            and previous_enabled != enabled
        )
        else ""
    )
    recovery = _recovery_policy(
        restore_point_mode=(
            toggle.restore_point_policy if enabled else "none"
        ),
        undo_key=undo_key,
        unavailable_reason=(
            "Önceki ayar durumu doğrulanamadığı için uygulama içi otomatik "
            "geri alma sunulmuyor."
        ),
        applicable=toggle.key in UNDOABLE_TOGGLE_KEYS,
    )
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
        rollback=rollback_text,
        confirmation_stages=confirmation_stage_count(
            directional_risk,
            admin_required=True,
        ),
        recovery=recovery,
    )


def execution_plan_for_toggle(
    toggle: ToggleAction,
    enabled: bool,
    *,
    previous_enabled: bool | None = None,
) -> ExecutionPlan:
    if previous_enabled is not None and previous_enabled == enabled:
        raise ValueError(f"Ayar zaten istenen durumda: {toggle.key}")
    impact = impact_for_toggle(
        toggle,
        enabled,
        previous_enabled=previous_enabled,
    )
    command = toggle.command_on if enabled else toggle.command_off
    if not command.strip():
        raise ValueError(f"Çalıştırılabilir ayar planı boş: {toggle.key}")
    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        action_key=impact.key,
        title=toggle.title,
        category="Windows temel ayarları",
        command=command,
        urls=(),
        admin_required=True,
        keep_open=False,
        success_codes=(0,),
        impact=impact,
    )


def impact_for_preset(preset: TechnicianPreset) -> OperationImpact:
    _validate_risk(preset.risk)
    rollback_text = preset.rollback.strip() or _default_rollback(preset.risk)
    recovery = _recovery_policy(
        restore_point_mode=preset.restore_point_policy,
        undo_key=preset.undo_key.strip(),
        unavailable_reason=rollback_text,
        applicable=(
            preset.risk != "normal"
            or preset.admin
            or bool(preset.undo_key.strip())
        ),
    )
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
        rollback=rollback_text,
        confirmation_stages=confirmation_stage_count(
            preset.risk,
            admin_required=preset.admin,
        ),
        recovery=recovery,
    )


def execution_plan_for_preset(preset: TechnicianPreset) -> ExecutionPlan:
    if not preset.command.strip():
        raise ValueError(f"Çalıştırılabilir hazır akış planı boş: {preset.key}")
    impact = impact_for_preset(preset)
    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        action_key=impact.key,
        title=preset.title,
        category="Teknisyen hazır akışları",
        command=preset.command,
        urls=(),
        admin_required=preset.admin,
        keep_open=False,
        success_codes=(0,),
        impact=impact,
    )


def expected_undo_key(action_key: str) -> str:
    if action_key.startswith(("undo:", "restore_point:")):
        return ""
    if action_key.startswith("toggle:"):
        parts = action_key.split(":")
        if len(parts) != 3 or parts[2] not in {"on", "off"}:
            return ""
        if (
            parts[1] not in TOGGLE_LOOKUP
            or parts[1] not in UNDOABLE_TOGGLE_KEYS
        ):
            return ""
        inverse = "off" if parts[2] == "on" else "on"
        return f"toggle:{parts[1]}:{inverse}"
    if action_key.startswith("preset:"):
        preset = PRESET_LOOKUP.get(action_key.removeprefix("preset:"))
        return preset.undo_key.strip() if preset else ""
    found = ACTION_LOOKUP.get(action_key)
    return found[1].undo_key.strip() if found else ""


def build_undo_plan(
    *,
    action_key: str,
    undo_key: str,
    parent_plan_id: str,
) -> ExecutionPlan | None:
    if not undo_key or expected_undo_key(action_key) != undo_key:
        return None
    if action_key.startswith("toggle:"):
        parts = undo_key.split(":")
        if len(parts) != 3 or parts[2] not in {"on", "off"}:
            return None
        toggle = TOGGLE_LOOKUP.get(parts[1])
        if toggle is None:
            return None
        enabled = parts[2] == "on"
        base_impact = impact_for_toggle(toggle, enabled)
        impact = OperationImpact(
            key=f"undo:{action_key}",
            title=f"Geri al: {toggle.title}",
            risk=base_impact.risk,
            risk_label=base_impact.risk_label,
            effect=(
                f"{toggle.title} ayarı işlem öncesinde doğrulanan duruma "
                "geri döndürülecek."
            ),
            target=base_impact.target,
            admin_required=True,
            interruption=base_impact.interruption,
            rollback=(
                "Bu geri alma adımı tamamlandıktan sonra aynı görev için "
                "ikinci bir otomatik geri alma sunulmaz."
            ),
            confirmation_stages=confirmation_stage_count(
                base_impact.risk,
                admin_required=True,
            ),
            recovery=RecoveryPolicy(
                undo_mode="unavailable",
                unavailable_reason=(
                    "Geri alma görevleri zincirleme otomatik geri alma üretmez."
                ),
            ),
        )
        command = toggle.command_on if enabled else toggle.command_off
        return ExecutionPlan(
            plan_id=uuid.uuid4().hex,
            parent_plan_id=parent_plan_id,
            action_key=f"undo:{action_key}",
            title=impact.title,
            category="Güvenli geri alma",
            command=command,
            urls=(),
            admin_required=True,
            keep_open=False,
            success_codes=(0,),
            impact=impact,
        )

    found = ACTION_LOOKUP.get(action_key)
    if found is None:
        return None
    _page_key, original = found
    undo_found = ACTION_LOOKUP.get(undo_key)
    if undo_found is None:
        return None
    _undo_page, undo_action = undo_found
    if not undo_action.command.strip() or undo_action.handler:
        return None
    risk = "caution"
    impact = OperationImpact(
        key=f"undo:{action_key}",
        title=f"Geri al: {original.title}",
        risk=risk,
        risk_label=_risk_label(risk),
        effect=(
            f"“{original.title}” işlemi için merkezi kayıttaki güvenli "
            "geri alma adımı uygulanacak."
        ),
        target=original.category,
        admin_required=undo_action.admin,
        interruption=(
            undo_action.interruption.strip()
            or _default_interruption(risk)
        ),
        rollback=(
            "Bu geri alma adımı tamamlandıktan sonra aynı görev için ikinci "
            "bir otomatik geri alma sunulmaz."
        ),
        confirmation_stages=confirmation_stage_count(
            risk,
            admin_required=undo_action.admin,
        ),
        recovery=RecoveryPolicy(
            undo_mode="unavailable",
            unavailable_reason=(
                "Geri alma görevleri zincirleme otomatik geri alma üretmez."
            ),
        ),
    )
    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        parent_plan_id=parent_plan_id,
        action_key=f"undo:{action_key}",
        title=impact.title,
        category="Güvenli geri alma",
        command=undo_action.command,
        urls=(),
        admin_required=undo_action.admin,
        keep_open=undo_action.keep_open,
        success_codes=(0,),
        impact=impact,
    )
