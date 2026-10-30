"""Explicit loader: refuses databases not named *Sample*, or non-empty financial DBs."""
import argparse
from datetime import date
from pathlib import Path
import json
from sqlalchemy import select
from sqlalchemy.engine import make_url
from . import schemas as s, services as svc
from .common import lock_store
from .config import Config
from .db import make_engine, make_factory
from .models import CashSession, Customer, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirm-sample-database', action='store_true', required=True)
    parser.parse_args()
    config = Config()
    db_name = make_url(config.database_url).database or ''
    if 'sample' not in db_name.lower():
        raise SystemExit('Refused: use a separate database whose name contains Sample')
    data = json.loads((Path(__file__).resolve().parents[2] / 'sample-data' / 'acceptance-example.json').read_text('utf-8'))
    factory = make_factory(make_engine(config.database_url))
    with factory() as db, db.begin():
        lock_store(db)
        if db.scalar(select(CashSession.id)) or db.scalar(select(Customer.id)):
            raise SystemExit('Refused: sample database already contains customers or sessions')
        actor = db.scalar(select(User).where(User.role == 'admin', User.is_active.is_(True)))
        if not actor:
            raise SystemExit('Create the sample database administrator interactively first')
        day = data['business_date']
        current = svc.create_session(db, actor, s.OpenInput(business_date=day, opening_cash=data['opening_cash']))
        sid = current['id']
        svc.update_sales(db, actor, sid, s.SalesInput(total_sales=data['total_sales'], pos_sales=data['pos_sales'], expected_version=1))
        c1 = svc.save_customer(db, actor, s.CustomerInput(name=data['credit_customer']))
        svc.create_debt(db, actor, s.DebtInput(customer_id=c1['id'], debt_date=day, amount=data['new_credit_sales'], kind='credit', session_id=sid))
        c2 = svc.save_customer(db, actor, s.CustomerInput(name=data['opening_debt_customer']))
        debt = svc.create_debt(db, actor, s.DebtInput(customer_id=c2['id'], debt_date=day, amount=data['opening_debt_amount'], kind='opening'))
        svc.create_payment(db, actor, s.PaymentInput(debt_id=debt['id'], session_id=sid, payment_date=day, amount=data['cash_collection'], payment_method='cash'))
        svc.create_purchase(db, actor, s.PurchaseInput(session_id=sid,purchase_date=day,description='فاتورة مثال', amount=data['cash_purchase'], payment_method='cash',from_drawer=True))
        svc.create_movement(db, actor, s.MovementInput(session_id=sid,movement_date=day,description='مصروف مثال',amount=data['cash_expense'],kind='expense'))
    print('Sample data saved ONLY in the named Sample database. Expected cash: 1700.00')


if __name__ == '__main__':
    main()
