from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, jwt
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    # 註冊邏輯...

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    # 登入邏輯...