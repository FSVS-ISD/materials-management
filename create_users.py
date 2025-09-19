import os
from app import get_session, default_db_path
from models import Base, User

basedir = os.path.abspath(os.path.dirname(__file__))
db_uri = f"sqlite:///{default_db_path}"

def create_users():
    Session = get_session(db_uri)
    session = Session()

    # 建立資料表（如果尚未建立）
    Base.metadata.create_all(bind=session.bind)

    # 新增 dep1 ~ dep9 使用者，密碼為 pass1 ~ pass9
    for i in range(1, 10):
        username = f"dep{i}"
        if session.query(User).filter_by(username=username).first():
            print(f"使用者 {username} 已存在，跳過")
        else:
            user = User(username=username)
            user.set_password(f"pass{i}")  # 設定密碼
            session.add(user)
            print(f"新增使用者 {username}")

    # 新增 dep1T ~ dep9T 使用者，密碼皆為 'FSVS'
    for i in range(1, 10):
        username = f"dep{i}T"
        if session.query(User).filter_by(username=username).first():
            print(f"使用者 {username} 已存在，跳過")
        else:
            user = User(username=username)
            user.set_password("FSVS")  # 設定密碼
            session.add(user)
            print(f"新增使用者 {username}")

    session.commit()
    session.close()
    print("使用者新增完成")

if __name__ == "__main__":
    create_users()
