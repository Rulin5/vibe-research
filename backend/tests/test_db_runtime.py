from sqlalchemy import text
from sqlalchemy.engine import make_url

from db import database_url, session_factory


def test_database_runtime_connects_to_configured_application_database():
    configured_name = make_url(database_url()).database
    assert configured_name
    with session_factory()() as session:
        assert session.execute(text("SELECT current_database()")).scalar_one() == configured_name
