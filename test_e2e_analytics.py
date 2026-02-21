from app.utils.sql_safety import validate_dataset_table_name
from app.services.analytics import generate_sql

def test_invalid_table_name_is_rejected():
    try:
        validate_dataset_table_name("not_a_real_table;DROP TABLE users")
        assert False, "Expected ValueError for invalid table name"
    except ValueError as exc:
        assert "Invalid table name format" in str(exc)


def test_sql_safety_accepts_expected_dataset_name():
    value = validate_dataset_table_name("dataset_0123456789abcdef0123456789abcdef")
    assert value == "dataset_0123456789abcdef0123456789abcdef"


def test_generate_sql_uses_quoted_safe_identifier():
    sql = generate_sql(
        "marketing_roi",
        "dataset_0123456789abcdef0123456789abcdef",
    )
    assert 'FROM "dataset_0123456789abcdef0123456789abcdef"' in sql
