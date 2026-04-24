def test_extract_email_finds_address():
    from notion_sync import extract_email

    assert extract_email("Твой логин: john.doe@squarefi.co, пароль: X7hjk") == "john.doe@squarefi.co"


def test_extract_email_no_match():
    from notion_sync import extract_email

    assert extract_email("нет почты тут") is None


def test_extract_email_ignores_text_before():
    from notion_sync import extract_email

    assert extract_email("Email = a.b+tag@example.org") == "a.b+tag@example.org"


def test_emp_notion_map_covers_expected_keys():
    from notion_sync import EMP_NOTION_MAP

    # Ключи чек-листа сотрудника, которые должны синкаться в Notion
    assert EMP_NOTION_MAP.get("verification") == "Personа"  # с русской «а»
    assert EMP_NOTION_MAP.get("nda") == "NDA"
    assert EMP_NOTION_MAP.get("contract") == "Agreement"
    assert EMP_NOTION_MAP.get("wallet") == "Wallet"
    assert EMP_NOTION_MAP.get("gmail_access") == "Email"


def test_hr_notion_map_has_access_keys():
    from notion_sync import HR_NOTION_MAP

    assert HR_NOTION_MAP.get("tariff") == "VIP"
    assert HR_NOTION_MAP.get("slack_access") == "Slack"
    assert HR_NOTION_MAP.get("crm_access") == "CRM"
    assert HR_NOTION_MAP.get("notion_access") == "Notion"
