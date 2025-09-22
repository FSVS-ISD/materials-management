from flask import request, jsonify, g, current_app
from flask import Blueprint
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from models import User
import threading
import logging
from werkzeug.security import check_password_hash
from config import get_session, default_db_path

user_bp = Blueprint('user', __name__, url_prefix='/api')

logger = logging.getLogger(__name__)
db_lock = threading.Lock()

@user_bp.route('/register', methods=['POST'], strict_slashes=False)
def register():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'username and password required'}), 400

    Session = get_session(f"sqlite:///{default_db_path}")
    session = Session()

    with db_lock:
        try:
            if session.query(User).filter_by(username=data['username']).first():
                return jsonify({'error': 'Username exists'}), 409

            user = User(username=data['username'])
            user.set_password(data['password'])

            session.add(user)
            session.commit()
            logger.info(f"User '{data['username']}' registered.")
            return jsonify({'message': 'Registered'}), 201
        except Exception as e:
            session.rollback()
            logger.exception(f"Register error: {e}")
            return jsonify({'error': 'Registration failed'}), 500
        finally:
            session.close()

@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"msg": "username and password required"}), 400

    username = data.get('username')
    password = data.get('password')
    session = g.db_session()
    
    user = session.query(User).filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"msg": "帳號或密碼錯誤"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)

@user_bp.route('/auto-auth', methods=['GET'], strict_slashes=False)
def auto_auth():
    system_username = "system_auto_user"
    session = g.db_session()
    
    with db_lock:
        user = session.query(User).filter_by(username=system_username).first()
        if not user:
            user = User(username=system_username)
            user.set_password("auto_generated_password")  # 考慮使用更安全的生成方法
            session.add(user)
            session.commit()
            logger.info(f"Auto-auth user '{system_username}' created")
    
    token = create_access_token(identity=system_username)
    logger.debug(f"Auto-auth token generated for {system_username}")
    return jsonify({'access_token': token}), 200

@user_bp.route('/userinfo', methods=['GET'])
@jwt_required()
def userinfo():
    current_user = get_jwt_identity()
    session = g.db_session()
    
    user = session.query(User).filter_by(username=current_user).first()
    if not user:
        return jsonify({"msg": "使用者不存在"}), 404

    return jsonify({
        "username": user.username,
        # 可依需求加入更多欄位，如 email、roles 等
    })
