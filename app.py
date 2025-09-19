import os
import threading
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, g, send_from_directory, request, make_response
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, verify_jwt_in_request, get_jwt_identity, get_jwt, create_access_token, jwt_required
)
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

# 匯入共用模型模組與 Base
from models import Base, User, Material, Category, InRecord, OutRecord

# 匯入拆分後的藍圖（修改路徑）
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

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{default_db_path}"
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

# 全域快取 engine 和 session factory，避免重複建立
engine_cache = {}
session_factory_cache = {}

# --- 啟用 CORS ---
CORS(app, supports_credentials=True)

# 新增 Private Network Access 標頭
@app.after_request
def add_private_network_header(response):
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Private-Network'] = 'true'
    return response

# --- 欄位自動新增函式 ---
def add_missing_columns(engine, table_model):
    inspector = inspect(engine)
    table_name = table_model.__tablename__
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    model_columns = table_model.__table__.columns

    for col in model_columns:
        if col.name not in existing_columns:
            col_type = str(col.type)
            nullable = 'NULL' if col.nullable else 'NOT NULL'
            default = ''
            if col.default is not None and col.default.is_scalar:
                default_val = col.default.arg
                default = f"DEFAULT '{default_val}'"
            sql = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable} {default}'
            logger.info(f"資料表 {table_name} 欄位 {col.name} 不存在，執行: {sql}")
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()  # 確保 DDL 操作被提交

# --- 建立資料表並檢查欄位 ---
def create_tables_if_not_exist(db_uri):
    engine = get_engine(db_uri)
    inspector = inspect(engine)

    # 一次建立所有模型的表格（如果不存在）
    Base.metadata.create_all(engine)

    # 可選：檢查欄位並自動新增（依需求保留）
    for model in [User, Material, Category, InRecord, OutRecord]:
        if inspector.has_table(model.__tablename__):
            add_missing_columns(engine, model)

# --- 動態建立 Engine 與 Session (快取) ---
def get_engine(db_uri):
    if db_uri not in engine_cache:
        engine_cache[db_uri] = create_engine(db_uri, connect_args={"check_same_thread": False})
    return engine_cache[db_uri]

def get_session(db_uri):
    engine = get_engine(db_uri)
    if db_uri not in session_factory_cache:
        session_factory_cache[db_uri] = scoped_session(sessionmaker(bind=engine))
    return session_factory_cache[db_uri]

# --- 根據 username 決定資料庫 URI ---
def get_db_uri_for_user(username: str) -> str:
    logger.debug(f"判斷資料庫連線，username={username}")
    if username:
        uname = username.lower()
        if uname.startswith('dep'):
            suffix = uname[3:]
            # 如果尾巴是 't'，去掉它
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

# --- 根據 username 回傳對應資料庫 URI 的 API ---
@app.route('/api/get-db-uri', methods=['GET'])
def get_db_uri_api():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    db_uri = get_db_uri_for_user(username)
    return jsonify({"db_uri": db_uri})

# --- 請求前設定資料庫 session ---
@app.before_request
def set_db_session_per_user():
    if request.method == 'OPTIONS':
        return  # 跳過 CORS 預檢請求

    # 將路徑尾巴斜線去除，方便比對
    path = request.path.rstrip('/')

    # 新增 /api/auto-auth 進入公開路徑清單
    public_paths = ['/api/health', '/api/login', '/api/get-db-uri', '/api/register', '/api/auto-auth']

    if path.startswith('/api') and path not in public_paths:
        try:
            verify_jwt_in_request(optional=False)
            claims = get_jwt()
            db_uri = claims.get('db_uri')

            if not db_uri:
                logger.warning(f"Token for identity '{get_jwt_identity()}' is missing 'db_uri' claim.")
                return jsonify({"msg": "Token is missing necessary information"}), 400

            with db_uri_lock:
                if db_uri not in checked_dbs:
                    create_tables_if_not_exist(db_uri)
                    checked_dbs.add(db_uri)

            Session = get_session(db_uri)
            g.db_session = Session

        except Exception as e:
            logger.error(f"設定資料庫連線時發生錯誤或 JWT 驗證失敗: {e}", exc_info=True)
            return jsonify({"msg": "Missing or invalid token"}), 401

@app.teardown_request
def remove_db_session(exception=None):
    sess = getattr(g, 'db_session', None)
    if sess is not None:
        sess.remove()
    # 不 dispose engine，因為使用快取共用 engine

# --- 登入 API ---
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "Missing JSON in request"}), 400
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if not username or not password:
            return jsonify({"msg": "Missing username or password"}), 400

        # 登入驗證一律在預設(主)資料庫的 User 表進行
        Session = get_session(f"sqlite:///{default_db_path}")
        session = Session()
        user = session.query(User).filter_by(username=username).first()
        session.close()

        if not user or not user.check_password(password):
            return jsonify({"msg": "Invalid username or password"}), 401

        # 登入成功，決定資料庫 URI 並放入 JWT claims
        db_uri = get_db_uri_for_user(username)
        additional_claims = {'db_uri': db_uri}
        access_token = create_access_token(identity=username, additional_claims=additional_claims)

        return jsonify(access_token=access_token)
    except Exception as e:
        logger.error(f"登入失敗: {e}", exc_info=True)
        return jsonify({"msg": "Internal server error"}), 500

# --- 系統自動用戶取得 token API ---
@app.route('/api/auto-auth', methods=['GET'])
def auto_auth():
    """
    此路由改為公開路由，不強制需要 JWT。
    若前端有帶 Authorization header，則回傳同 token。
    否則回傳提示訊息。
    """
    auth_header = request.headers.get('Authorization', None)
    if not auth_header:
        return jsonify({"msg": "No Authorization header provided"}), 401

    # Authorization 格式通常是 "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return jsonify({"msg": "Invalid Authorization header format"}), 401

    token = parts[1]

    # 直接回傳相同 token，避免資料庫不一致問題
    return jsonify(access_token=token)

#--------禁止瀏覽器快取 dashboard.html----------
@app.route('/dashboard.html')
def dashboard():
    # 從 static 資料夾讀取 dashboard.html
    response = make_response(send_from_directory('static', 'dashboard.html'))
    # 設定禁止快取的 HTTP Headers
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# --- 新增 /api/materials API ---
@app.route('/api/materials', methods=['GET'])
@jwt_required()
def get_materials():
    username = get_jwt_identity()
    logger.debug(f"API /api/materials called by user: {username}")

    # 從 g 取得目前 session
    session = getattr(g, 'db_session', None)
    if session is None:
        logger.error("No DB session found in g")
        return jsonify({"error": "資料庫連線未建立"}), 500

    try:
        materials = session.query(Material).all()
        logger.debug(f"Fetched {len(materials)} materials from DB for user {username}")

        materials_data = [m.to_dict() for m in materials]  # 請確保 Material 有 to_dict() 方法
        return jsonify(materials_data), 200

    except Exception as e:
        logger.error(f"Error fetching materials: {e}", exc_info=True)
        return jsonify({"error": "取得物料資料失敗"}), 500

# --- 列出所有使用者 API（僅限 admin） ---
@app.route('/api/users', methods=['GET'])
@jwt_required()
def list_users():
    current_user = get_jwt_identity()

    # 強制使用預設資料庫 session
    Session = get_session(f"sqlite:///{default_db_path}")
    session = Session()

    try:
        current_user_obj = session.query(User).filter_by(username=current_user).first()
        if not current_user_obj:
            app.logger.warning(f"User {current_user} not found in DB")
            return jsonify({"msg": "User not found"}), 404

        app.logger.debug(f"User {current_user} role: {current_user_obj.role}")

        if current_user_obj.role != 'admin':
            return jsonify({"msg": "Permission denied"}), 403

        users = session.query(User).all()
        users_data = [{"username": u.username, "role": u.role} for u in users]
        return jsonify(users_data), 200

    except Exception as e:
        app.logger.error(f"Error in /api/users: {e}", exc_info=True)
        return jsonify({"msg": "Internal server error"}), 500

    finally:
        session.close()

# --- 優化後的修改密碼 API ---
@app.route('/api/user/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    修改密碼路由：
    前端需傳 JSON 格式：
    {
      "username": "要修改的帳號",
      "old_password": "舊密碼（使用者自己修改時必填）",
      "new_password": "新密碼"
    }
    管理員可無需舊密碼修改任何帳號密碼。
    一般使用者只能修改自己密碼，且須提供舊密碼。
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "Missing JSON data"}), 400

        username = data.get("username", "").strip()
        old_password = data.get("old_password", "").strip()
        new_password = data.get("new_password", "").strip()

        if not username or not new_password:
            return jsonify({"msg": "Username and new password are required"}), 400

        current_user = get_jwt_identity()
        session = getattr(g, 'db_session', None)
        if not session:
            return jsonify({"msg": "Database session not found"}), 500

        current_user_obj = session.query(User).filter_by(username=current_user).first()
        if not current_user_obj:
            return jsonify({"msg": "Current user not found"}), 404

        user = session.query(User).filter_by(username=username).first()
        if not user:
            return jsonify({"msg": "User not found"}), 404

        # 管理員修改他人密碼，不需驗證舊密碼
        if current_user_obj.role == 'admin' and username != current_user:
            pass
        else:
            # 一般使用者修改自己密碼，須驗證舊密碼
            if username != current_user:
                return jsonify({"msg": "Permission denied: cannot change other users' passwords"}), 403
            if not old_password:
                return jsonify({"msg": "Old password is required"}), 400
            if not user.check_password(old_password):
                return jsonify({"msg": "Old password is incorrect"}), 400

        user.set_password(new_password)
        session.commit()

        return jsonify({"msg": f"Password for user '{username}' updated successfully."}), 200

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error on password change: {e}", exc_info=True)
        return jsonify({"msg": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error in change_password: {e}", exc_info=True)
        return jsonify({"msg": "Internal server error"}), 500

# --- 註冊藍圖 ---
app.register_blueprint(user_bp)
app.register_blueprint(material_bp)
app.register_blueprint(category_bp)
app.register_blueprint(record_bp)
app.register_blueprint(report_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(font_bp)

# --- 靜態頁面路由 ---
@app.route('/', defaults={'path': 'login.html'})
@app.route('/<path:path>')
def serve_static(path):
    static_folder = os.path.join(basedir, 'static')
    if os.path.exists(os.path.join(static_folder, path)):
        return send_from_directory(static_folder, path)
    else:
        # 找不到檔案，一律回傳 login.html，讓前端 Vue Router 處理
        return send_from_directory(static_folder, 'login.html')

# --- 健康檢查 API ---
@app.route('/api/health', methods=['GET'], strict_slashes=False)
def health_check():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

# --- 主程式啟動 ---
if __name__ == '__main__':
    with db_uri_lock:
        create_tables_if_not_exist(f"sqlite:///{default_db_path}")
        checked_dbs.add(f"sqlite:///{default_db_path}")
    app.run(host='0.0.0.0', port=5000, debug=True)
