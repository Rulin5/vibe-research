import pytest

import test_database


def test_rejects_non_test_database_url():
    with pytest.raises(RuntimeError, match="_test"):
        test_database.validate_test_database_url(
            "postgresql+psycopg://app:secret@127.0.0.1:5432/vibe_research"
        )


def test_accepts_explicit_test_database_url():
    url = "postgresql+psycopg://tester:secret@127.0.0.1:55432/vibe_research_test"

    assert test_database.validate_test_database_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://tester:secret@127.0.0.1/vibe_research_test",
        "postgresql+psycopg://tester:secret@127.0.0.1/postgres",
    ],
)
def test_rejects_wrong_driver_or_database(url):
    with pytest.raises(RuntimeError):
        test_database.validate_test_database_url(url)
