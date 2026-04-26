from texts import (
    ACCESS_FLOW,
    EMP_CHECKLIST,
    FLOW,
    FLOW_BY_FIELD,
    FLOW_ORDER,
    HR_ROADMAP,
    INTRO_MESSAGE,
    OFFER_TEMPLATE,
    SELF_REGISTER_PROMPT,
    SLACK_PRESENTATION_DRAFT,
)


def test_flow_all_have_required_keys():
    for s in FLOW + ACCESS_FLOW:
        assert "field" in s and "ask" in s and "header" in s


def test_flow_by_field_covers_all():
    expected = {s["field"] for s in FLOW + ACCESS_FLOW}
    assert set(FLOW_BY_FIELD.keys()) == expected


def test_flow_order_is_materials_only():
    # Авто-цепочка не включает доступы — они стоят как отдельные действия
    assert FLOW_ORDER == ["verify", "email", "phone", "nda", "wallet"]


def test_offer_template_renders():
    rendered = OFFER_TEMPLATE.format(
        salary="3000 USDT/мес",
        growth="Senior через 6 мес",
        probation="3 месяца",
        start_date="2026-05-01",
    )
    assert "3000 USDT/мес" in rendered
    assert "2026-05-01" in rendered


def test_slack_draft_renders_with_name():
    rendered = SLACK_PRESENTATION_DRAFT.format(name="Ivan Ivanov")
    assert "Ivan Ivanov" in rendered


def test_intro_mentions_emma():
    """Интро представляется от имени Эмма (HR-бот персона)."""
    assert "Эмма" in INTRO_MESSAGE


def test_self_register_has_no_placeholders():
    # Проверяем что текст не содержит несостыкованных {} плейсхолдеров
    assert "{" not in SELF_REGISTER_PROMPT or "}" in SELF_REGISTER_PROMPT


def test_emp_checklist_has_7_items():
    # По ТЗ — 7 пунктов (gmail доступ + 2FA разделены)
    assert len(EMP_CHECKLIST) == 7
    keys = {k for k, _ in EMP_CHECKLIST}
    assert "gmail_access" in keys
    assert "email_2fa" in keys


def test_hr_roadmap_has_offer_first():
    # По ТЗ шаг 1 — оффер
    assert HR_ROADMAP[0][0] == "offer"
