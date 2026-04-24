import os
import sys
import tempfile

import pytest

# Подставляем тестовые env ДО импорта модулей
os.environ.setdefault("HR_BOT_TOKEN", "111111:AAAAA_test_token_for_hr_AAAAAAAAAAAAAAA")
os.environ.setdefault("HR_BOT_USERNAME", "test_hr_bot")
os.environ.setdefault("EMP_BOT_TOKEN", "222222:BBBBB_test_token_for_emp_BBBBBBBBBBBBB")
os.environ.setdefault("EMP_BOT_USERNAME", "test_emp_bot")
os.environ.setdefault("HR_ID", "1")
os.environ.setdefault("HR_NAME", "Test HR")

# Каждый тест получает свою БД (не трогаем прод)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    # Переимпортируем db с новым путём
    import importlib
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    yield db_module
    os.unlink(path)
