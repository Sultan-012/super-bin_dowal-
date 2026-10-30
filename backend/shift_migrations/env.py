from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine
from shift_app.config import Config
from shift_app.models import Base

alembic_config=context.config
if alembic_config.config_file_name:
    fileConfig(alembic_config.config_file_name)
url=Config().database_url
target_metadata=Base.metadata

if context.is_offline_mode():
    context.configure(url=url,target_metadata=target_metadata,literal_binds=True,
                      dialect_opts={'paramstyle':'named'},version_table='shift_alembic_version')
    with context.begin_transaction():
        context.run_migrations()
else:
    engine=create_engine(url,hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata,
                          compare_type=True,version_table='shift_alembic_version')
        with context.begin_transaction():
            context.run_migrations()
