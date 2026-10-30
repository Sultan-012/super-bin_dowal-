"""Interactive local operator commands. Passwords never go in command arguments."""
import argparse
import getpass
from sqlalchemy import select
from .common import audit, lock_store
from .config import Config
from .db import make_engine, make_factory
from .models import Store, User
from .schemas import UserInput, SettingsInput
from .security import hasher


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['create-admin'])
    args = parser.parse_args()
    username = input('Username (Latin, 3-64 characters): ').strip()
    full_name = input('Full name: ').strip()
    password = getpass.getpass('Password (at least 12 characters): ')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match')
    data = UserInput(username=username, full_name=full_name, password=password, role='admin')
    config = Config()
    factory = make_factory(make_engine(config.database_url))
    with factory() as db, db.begin():
        lock_store(db)
        if db.scalar(select(User.id)):
            raise SystemExit('Initial administrator already created. Use Settings to manage users.')
        store = db.get(Store, 1)
        initial = SettingsInput(store_name=store.store_name, currency=config.default_currency, timezone=config.default_timezone)
        store.currency, store.timezone = initial.currency, initial.timezone
        user = User(username=data.username.lower(), full_name=data.full_name,
                    role='admin', password_hash=hasher.hash(data.password))
        db.add(user)
        db.flush()
        audit(db, user, 'bootstrap_admin', user, reason='Interactive local first-administrator setup')
    print('Administrator created. No sample transactions were added.')


if __name__ == '__main__':
    main()
