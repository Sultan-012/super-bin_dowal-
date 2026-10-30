import argparse
import getpass
import secrets
from sqlalchemy import select
from .common import audit, lock_store
from .config import Config
from .db import make_engine, make_factory
from .models import User
from .schemas import UserInput
from .security import hasher


def main():
    parser=argparse.ArgumentParser(description='إدارة سوبر ماركت بن دول')
    parser.add_argument('command',choices=['create-admin','seed-sample'])
    args=parser.parse_args()
    config=Config()
    factory=make_factory(make_engine(config.database_url))
    if args.command=='seed-sample':
        from .sample_data import seed_sample
        seed_sample(factory,config)
        return
    username=input('اسم مستخدم المدير: ').strip()
    name=input('الاسم الكامل: ').strip()
    password=getpass.getpass('كلمة المرور (8 خانات أو أكثر): ')
    if password!=getpass.getpass('تأكيد كلمة المرور: '):
        raise SystemExit('كلمتا المرور غير متطابقتين.')
    data=UserInput(username=username,full_name=name,password=password,role='admin')
    with factory() as db,db.begin():
        lock_store(db)
        if db.scalar(select(User.id).where(User.username==data.username)):
            raise SystemExit('اسم المستخدم مسجل بالفعل.')
        admin=User(username=data.username,full_name=data.full_name,
                   password_hash=hasher.hash(data.password),role='admin',active=True)
        db.add(admin)
        db.flush()
        audit(db,admin,'admin.created-cli',admin,{'username':admin.username})
    print('تم إنشاء المدير. لا توجد كلمة مرور افتراضية.')


if __name__=='__main__':
    main()
