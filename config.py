import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 取得專案根目錄（假設 config.py 與 app.py 在同一層）
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 資料庫檔案直接放在根目錄，檔名為 materials.db
default_db_path = os.path.join(BASE_DIR, "materials.db")

# 確保資料庫資料夾存在（此處資料庫在根目錄，不需要建立資料夾）

# 資料庫連線字串
DATABASE_URL = f"sqlite:///{default_db_path}"

# 建立 SQLAlchemy Session factory
def get_session(db_url=None):
    if db_url is None:
        db_url = DATABASE_URL
    try:
        engine = create_engine(db_url, echo=False, future=True)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        raise RuntimeError(f"無法建立資料庫連線: {e}")

