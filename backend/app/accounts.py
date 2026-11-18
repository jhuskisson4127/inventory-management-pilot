import argparse
import getpass
import subprocess
import sys
import warnings

from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from .auth import normalize_username, password_hasher
from .db import Base, SessionLocal, engine
from .models import User


def main():
    parser = argparse.ArgumentParser(description="Create an inventory login")
    parser.add_argument("username")
    parser.add_argument("--iscs2", action="store_true",
                        help="Provision the account through the pilot's ISCS2 MySQL console")
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

    password_hash = password_hasher.hash(password)
    if args.iscs2:
        table = User.__table__
        dialect = mysql.dialect()
        create = CreateTable(table, if_not_exists=True).compile(dialect=dialect)
        insert = table.insert().values(username=username, password_hash=password_hash).compile(
            dialect=dialect, compile_kwargs={"literal_binds": True}
        )
        result = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "dokku@iscs2.gcsu.edu",
             "mysql:console", "david-morris-6299-project"],
            input=f"{create};\n{insert};\n", text=True, capture_output=True,
        )
        if result.returncode != 0:
            parser.error("ISCS2 could not create the account. Check SSH access or whether the username exists.")
        print("Account created.")
        return

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(User(username=username, password_hash=password_hash))
        try:
            db.commit()
        except IntegrityError:
            parser.error("Could not create that account. Check whether the username already exists.")
    print("Account created.")


if __name__ == "__main__":
    main()
