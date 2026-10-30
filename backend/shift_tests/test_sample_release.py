"""The optional sample must be isolated, executable and incapable of delivery."""
from sqlalchemy import func, select
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from shift_app.config import Config, ROOT
from shift_app.db import make_engine, make_factory
from shift_app.models import Attachment, NotificationDelivery, Shift, Approval, User
from shift_app.sample_data import seed_sample


def test_sample_refuses_operational_database_without_connecting():
    config=Config(app_env='test',database_url='sqlite:///operational.db',idempotency_secret='x'*40)
    with pytest.raises(SystemExit,match='bin_doul_sample'):
        seed_sample(lambda:pytest.fail('must reject before connecting'),config)


def test_current_sample_seeds_only_separate_database_without_notifications(tmp_path,monkeypatch):
    url='sqlite:///'+str(tmp_path/'bin_doul_sample_training.db')
    monkeypatch.setenv('DATABASE_URL',url)
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('IDEMPOTENCY_SECRET','x'*40)
    command.upgrade(AlembicConfig(str(ROOT/'backend'/'shift_alembic.ini')),'head')
    engine=make_engine(url);factory=make_factory(engine)
    config=Config(app_env='test',database_url=url,idempotency_secret='x'*40,
                  notification_channels='email,whatsapp',n8n_api_token='y'*40)
    with factory() as db,db.begin():
        db.add(User(username='sample_admin',full_name='مدير العينة',role='admin',active=True,password_hash='unused'))
    seed_sample(factory,config)
    with factory() as db:
        count=db.scalar(select(func.count()).select_from(Shift))
        assert 6<=count<=8
        assert db.scalar(select(func.count()).select_from(Approval))==count-2
        assert db.scalar(select(func.count()).select_from(Attachment))==count
        assert db.scalar(select(func.count()).select_from(NotificationDelivery))==0
        assert all(s.business_date is not None for s in db.scalars(select(Shift)))
    with pytest.raises(SystemExit,match='ليست فارغة'):seed_sample(factory,config)
    engine.dispose()
