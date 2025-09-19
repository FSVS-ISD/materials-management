import os
from datetime import datetime, timezone
from app import get_session
from models import Material, OutRecord

basedir = os.path.abspath(os.path.dirname(__file__))
db_file = os.path.join(basedir, 'materials_1.db')
db_uri = f"sqlite:///{db_file}"

Session = get_session(db_uri)
session = Session()

try:
    material = session.query(Material).filter_by(item_id='M0001').first()
    if not material:
        print("找不到 item_id='M0001' 的物料")
    else:
        record = OutRecord(
            material_id=material.id,
            quantity=1,
            user='B',
            department='資訊科',
            purpose='B',
            barcode=material.barcode,
            date=datetime.now(timezone.utc),
            source='測試',
            handler='測試人員'
        )
        session.add(record)
        session.commit()
        print("新增出庫紀錄成功")
finally:
    session.close()
