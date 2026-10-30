from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str):
    kwargs = {'pool_pre_ping': True, 'hide_parameters': True}
    if url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 30}
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def sqlite_settings(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA journal_mode=WAL')
    return engine


def make_factory(engine):
    return sessionmaker(engine, class_=Session, expire_on_commit=False)
