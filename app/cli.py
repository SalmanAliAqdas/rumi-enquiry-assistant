"""Run: python -m app.cli create-admin"""

import argparse
import warnings
from getpass import GetPassWarning, getpass

from sqlmodel import Session

from app.auth import password_hasher
from app.config import Settings
from app.db import init_db, make_engine
from app.models import Admin


def main():
    parser = argparse.ArgumentParser(description="Private database and administrator setup")
    parser.add_argument("command", choices=["create-admin", "migrate-db"])
    parser.add_argument(
        "--database-url-prompt",
        action="store_true",
        help="Prompt without echo for a PostgreSQL TLS URL; ignore the local .env",
    )
    args = parser.parse_args()
    if args.database_url_prompt:
        from sqlalchemy.engine import make_url
        from sqlalchemy.exc import ArgumentError

        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            url = getpass("Fresh Rumi PostgreSQL connection URL (hidden): ").strip()
        try:
            parsed = make_url(url)
        except ArgumentError:
            parser.exit(1, "Invalid PostgreSQL connection URL. No changes made.\n")
        if parsed.get_backend_name() != "postgresql" or parsed.query.get("sslmode") not in {
            "require",
            "verify-full",
        }:
            parser.exit(1, "A PostgreSQL URL with sslmode=require or verify-full is required.\n")
        settings = Settings(database_url=url, _env_file=None)
    else:
        settings = Settings()
    if args.command == "migrate-db":
        from app.migrations import migrate_database

        backup = migrate_database(settings.database_url)
        print("Schema ready. " + (f"SQLite backup: {backup}" if backup else "No data imported."))
        return
    engine = make_engine(settings.database_url)
    try:
        init_db(engine)
        with Session(engine) as db:
            if db.get(Admin, 1):
                parser.exit(1, "An administrator already exists. No changes made.\n")
        # Do not leave a read transaction open while waiting for terminal input.
        username = input("Admin username: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Password (at least 12 characters): ")
            confirmation = getpass("Confirm password: ")
        if not 1 <= len(username) <= 100:
            parser.exit(1, "Username must contain 1–100 characters.\n")
        if not 12 <= len(password) <= 256 or password.isspace() or password != confirmation:
            parser.exit(1, "Passwords must match and contain 12–256 characters.\n")
        with Session(engine) as db:
            db.add(Admin(username=username, password_hash=password_hasher.hash(password)))
            db.commit()
            print("Administrator created. No password was saved in plain text.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
