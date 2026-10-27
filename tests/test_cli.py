from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app import cli
from app.auth import password_hasher
from app.config import Settings
from app.db import make_engine
from app.models import Admin


def test_cli_creates_hashed_admin_and_refuses_replacement(tmp_path, monkeypatch, capsys):
    import secrets

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cli.db'}", _env_file=None)
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr("sys.argv", ["cli", "create-admin"])
    password = secrets.token_urlsafe(24)
    with (
        patch("builtins.input", return_value="fictional-admin"),
        patch("app.cli.getpass", side_effect=[password, password]),
    ):
        cli.main()
    output = capsys.readouterr().out
    assert "Administrator created" in output
    assert password not in output
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as db:
            admins = db.exec(select(Admin)).all()
            assert len(admins) == 1
            assert admins[0].password_hash.startswith("$argon2")
            assert password_hasher.verify(password, admins[0].password_hash)
            original = admins[0].password_hash
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
        with Session(engine) as db:
            assert db.get(Admin, 1).password_hash == original
    finally:
        engine.dispose()


@pytest.mark.parametrize("password,confirmation", [("short", "short"), ("a" * 12, "different")])
def test_cli_rejects_unsafe_creation(tmp_path, monkeypatch, password, confirmation):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cli.db'}", _env_file=None)
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr("sys.argv", ["cli", "create-admin"])
    with (
        patch("builtins.input", return_value="fictional-admin"),
        patch("app.cli.getpass", side_effect=[password, confirmation]),
        pytest.raises(SystemExit) as exc,
    ):
        cli.main()
    assert exc.value.code == 1
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as db:
            assert not db.exec(select(Admin)).all()
    finally:
        engine.dispose()
