import os
import threading
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token
)
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# 匯入共用模型模組與 Base
from models import Base, User, Material, Category, InRecord, OutRecord

# 匯入拆分後的藍圖
from routes.user import user_bp
from routes.material import material_bp
from routes.category import category_bp
from routes.record import record_bp
from routes.report import report_bp
from routes.backup import backup_bp
from routes.font import font_bp

# --- 初始化與設定 ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = os.path.join(basedir, 'materials.db')

# 使用環境變數設定資料庫 URI
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f"sqlite:///{default_db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your_test_secret_key_1234567890')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600 * 8  # 8小時（秒）
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'query_string']
app.config['JWT_QUERY_STRING_NAME'] = 'token'

jwt = JWTManager(app)
CORS(app, supports_credentials=True)

# --- 設定 logging 輸出到 APP.log 和 console ---
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

log_file = os.path.join(basedir, 'APP.log')
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

db_uri_lock = threading.Lock()
checked_dbs = set()

# --- 根據 username 決定資料庫 URI ---
def get_db_uri_for_user(username: str) -> str:
    logger.debug(f"判斷資料庫連線，username={username}")
    if username:
        uname = username.lower()
        if uname.startswith('dep'):
            suffix = uname[3:]
            if suffix.endswith('t'):
                suffix = suffix[:-1]
            if suffix.isdigit():
                dep_num = int(suffix)
                if 1 <= dep_num <= 9:
                    db_file = f"materials_{dep_num}.db"
                    uri = f"sqlite:///{os.path.join(basedir, db_file)}"
                    logger.debug(f"使用 {username} 對應資料庫 {uri}")
                    return uri
    default_uri = f"sqlite:///{default_db_path}"
    logger.debug(f"使用預設資料庫 {default_uri}")
    return default_uri

# --- 創建資料表的函數 ---
def create_tables_if_not_exist(database_uri):
    engine = create_engine(database_uri)
    try:
        Base.metadata.create_all(engine)  # 創建所有資料表
        logger.info("資料表已成功創建或已存在。")
    except SQLAlchemyError as e:
        logger.error(f"資料表創建失敗: {e}")
        raise

# --- 健康檢查 API ---
@app.route('/api/health', methods=['GET'], strict_slashes=False)
def health_check():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

# --- 登入 API ---
@user_bp.route('/login', methods=['POST'], endpoint='user_login')
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"msg": "用戶名和密碼為必填項"}), 400

    session = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI']))()
    try:
        user = session.query(User).filter_by(username=username).first()
        logger.debug(f"查詢用戶: {username}, 查詢結果: {user}")

        if user and user.verify_password(password):
            access_token = create_access_token(identity=username)
            return jsonify(access_token=access_token), 200
        else:
            return jsonify({"msg": "用戶名或密碼錯誤"}), 401
    except SQLAlchemyError as e:
        logger.error(f"資料庫查詢失敗: {e}")
        return jsonify({"msg": "伺服器錯誤"}), 500
    finally:
        session.close()

# --- 註冊藍圖 ---
app.register_blueprint(user_bp)
app.register_blueprint(material_bp)
app.register_blueprint(category_bp)
app.register_blueprint(record_bp)
app.register_blueprint(report_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(font_bp)

# --- 主程式啟動 ---
if __name__ == '__main__':
    with db_uri_lock:
        try:
            create_tables_if_not_exist(app.config['SQLALCHEMY_DATABASE_URI'])
            checked_dbs.add(app.config['SQLALCHEMY_DATABASE_URI'])
        except SQLAlchemyError as e:
            logger.error(f"資料表創建失敗: {e}")
            exit(1)

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
