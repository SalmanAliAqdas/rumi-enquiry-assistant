"""Run: python -m app.cli create-admin"""

import argparse
from getpass import getpass

from sqlmodel import Session

from app.auth import password_hasher
from app.config import Settings
from app.db import init_db, make_engine
from app.models import Admin


def main():
    parser = argparse.ArgumentParser(description="Local administrator setup")
    parser.add_argument("command", choices=["create-admin"])
    parser.parse_args()
    engine = make_engine(Settings().database_url)
    init_db(engine)
    try:
        with Session(engine) as db:
            if db.get(Admin, 1):
                parser.exit(1, "An administrator already exists. No changes made.\n")
            username = input("Admin username: ").strip()
            password = getpass("Password (at least 12 characters): ")
            confirmation = getpass("Confirm password: ")
            if not 1 <= len(username) <= 100:
                parser.exit(1, "Username must contain 1–100 characters.\n")
            if not 12 <= len(password) <= 256 or password.isspace() or password != confirmation:
                parser.exit(1, "Passwords must match and contain 12–256 characters.\n")
            db.add(Admin(username=username, password_hash=password_hasher.hash(password)))
            db.commit()
            print("Administrator created. No password was saved in plain text.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
