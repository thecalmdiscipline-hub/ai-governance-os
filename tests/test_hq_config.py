import pytest

from app.core.config import get_hq_organization_id


def test_hq_organization_id_not_set_is_none(monkeypatch):
    monkeypatch.delenv("HQ_ORGANIZATION_ID", raising=False)
    assert get_hq_organization_id() is None


def test_hq_organization_id_empty_string_is_none(monkeypatch):
    monkeypatch.setenv("HQ_ORGANIZATION_ID", "  ")
    assert get_hq_organization_id() is None


def test_hq_organization_id_valid_number_is_int(monkeypatch):
    monkeypatch.setenv("HQ_ORGANIZATION_ID", "1")
    value = get_hq_organization_id()
    assert value == 1 and isinstance(value, int)


@pytest.mark.parametrize("bad", ["abc", "1.5", "0", "-3", "1,2"])
def test_hq_organization_id_invalid_raises_clear_error(monkeypatch, bad):
    monkeypatch.setenv("HQ_ORGANIZATION_ID", bad)
    with pytest.raises(ValueError, match="HQ_ORGANIZATION_ID must be a positive integer"):
        get_hq_organization_id()
