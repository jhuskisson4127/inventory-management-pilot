import argparse
import getpass
import sys
import warnings

from sqlalchemy.exc import IntegrityError

from .auth import normalize_username, password_hasher
from .db import Base, SessionLocal, engine
from .models import User


def main():
    parser = argparse.ArgumentParser(description="Create an inventory login")
    parser.add_argument("username")
    args = parser.parse_args()
    try:
        username = normalize_username(args.username)
    except ValueError as exc:
        parser.error(str(exc))
    if not sys.stdin.isatty():
        parser.error("Run this command in an interactive terminal.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            password = getpass.getpass("New password: ")
            if not 15 <= len(password) <= 1024:
                parser.error("Use a password between 15 and 1024 characters.")
            if password != getpass.getpass("Confirm password: "):
                parser.error("Passwords did not match.")
        except getpass.GetPassWarning:
            parser.error("A terminal with hidden input is required.")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(User(username=username, password_hash=password_hasher.hash(password)))
        try:
            db.commit()
        except IntegrityError:
            parser.error("Could not create that account. Check whether the username already exists.")
    print("Account created.")


if __name__ == "__main__":
    main()
