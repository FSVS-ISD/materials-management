import os
import base64
from flask import Blueprint, jsonify, current_app

font_bp = Blueprint('font', __name__)

@font_bp.route('/api/font/noto_sans_tc', methods=['GET'])
def get_noto_sans_tc_font():
    font_path = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'NotoSansTC-Regular.ttf')
    try:
        with open(font_path, 'rb') as f:
            font_data = f.read()
        font_base64 = base64.b64encode(font_data).decode('utf-8')
        return jsonify({'fontBase64': font_base64})
    except Exception as e:
        current_app.logger.error(f"讀取字型檔失敗: {e}")
        return jsonify({'error': '無法讀取字型檔'}), 500