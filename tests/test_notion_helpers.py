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
    assert EMP_NOTION_MAP.get("verification") == "SumSub"
    assert EMP_NOTION_MAP.get("nda") == "NDA"
    assert EMP_NOTION_MAP.get("contract") == "Agreement"
    assert EMP_NOTION_MAP.get("wallet") == "Wallet issued"
    assert EMP_NOTION_MAP.get("gmail_access") == "Email access"


def test_hr_notion_map_has_access_keys():
    from notion_sync import HR_NOTION_MAP

    assert HR_NOTION_MAP.get("tariff") == "VIP"
    assert HR_NOTION_MAP.get("slack_access") == "Slack access"
    assert HR_NOTION_MAP.get("crm_access") == "CRM access"
    assert HR_NOTION_MAP.get("notion_access") == "Notion access"


def test_extract_url_and_phone():
    from notion_sync import extract_phone, extract_url

    assert extract_url("Пройди: https://in.sumsub.com/websdk/p/abc123.") == "https://in.sumsub.com/websdk/p/abc123"
    assert extract_url("ссылки нет") is None
    assert extract_phone("Твой номер: +44 7700 900123") == "+44 7700 900123"
    assert extract_phone("без номера") is None
