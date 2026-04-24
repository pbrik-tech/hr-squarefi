def test_create_and_get(tmp_db):
    token = tmp_db.create_employee("Test User")
    emp = tmp_db.get_by_token(token)
    assert emp["name"] == "Test User"
    assert emp["flow_step"] == "new"
    assert emp["telegram_id"] is None


def test_link_employee(tmp_db):
    token = tmp_db.create_employee("User A")
    ok = tmp_db.link_employee(token, 12345)
    assert ok is True
    emp = tmp_db.get_by_token(token)
    assert emp["telegram_id"] == 12345
    assert emp["flow_step"] == "joined"


def test_link_releases_previous_telegram_id(tmp_db):
    """Тот же TG ID, открытый второй ссылки, должен освободить старую запись."""
    t1 = tmp_db.create_employee("First")
    t2 = tmp_db.create_employee("Second")
    tmp_db.link_employee(t1, 999)
    tmp_db.link_employee(t2, 999)
    assert tmp_db.get_by_token(t1)["telegram_id"] is None
    assert tmp_db.get_by_token(t2)["telegram_id"] == 999


def test_self_register(tmp_db):
    token = tmp_db.create_employee_self("Self User", 555)
    emp = tmp_db.get_by_token(token)
    assert emp["telegram_id"] == 555
    assert emp["flow_step"] == "pending_approval"


def test_toggle_check_emp(tmp_db):
    token = tmp_db.create_employee("User")
    d1 = tmp_db.toggle_check(token, "emp", "verification")
    assert d1["verification"] is True
    d2 = tmp_db.toggle_check(token, "emp", "verification")
    assert d2["verification"] is False


def test_set_wallet(tmp_db):
    token = tmp_db.create_employee("Wallet User")
    tmp_db.set_wallet(token, "TXabc123")
    assert tmp_db.get_by_token(token)["tron_wallet"] == "TXabc123"


def test_audit_log(tmp_db):
    token = tmp_db.create_employee("Audit User")
    tmp_db.audit(token, "hr", "test_event", {"k": "v"})
    events = tmp_db.get_audit_log(token)
    assert len(events) == 1
    assert events[0]["event"] == "test_event"
    assert events[0]["actor"] == "hr"


def test_audit_updates_last_action(tmp_db):
    token = tmp_db.create_employee("Movement User")
    before = tmp_db.get_by_token(token)["last_action_at"]
    tmp_db.audit(token, "hr", "move")
    after = tmp_db.get_by_token(token)["last_action_at"]
    assert before is None
    assert after is not None


def test_messages_log(tmp_db):
    token = tmp_db.create_employee("Msg User")
    tmp_db.log_msg(token, "bot_to_emp", "Hello")
    logs = tmp_db.get_messages_log(token)
    assert len(logs) == 1
    assert logs[0]["direction"] == "bot_to_emp"
    assert logs[0]["text"] == "Hello"


def test_delete_employee(tmp_db):
    token = tmp_db.create_employee("To Delete")
    tmp_db.delete_employee(token)
    assert tmp_db.get_by_token(token) is None


def test_list_all_reverse_order(tmp_db):
    import time
    t1 = tmp_db.create_employee("First")
    time.sleep(0.01)
    t2 = tmp_db.create_employee("Second")
    all_emp = tmp_db.list_all()
    # list_all сортирует по created_at DESC — последний созданный первый
    assert all_emp[0]["token"] == t2
    assert all_emp[1]["token"] == t1
