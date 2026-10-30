from logging.config import fileConfig
from alembic import context
from app.config import Config
from app.db import make_engine
from app.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)
url = Config().database_url
target_metadata = Base.metadata
if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
