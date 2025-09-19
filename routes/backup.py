import os
from flask import Blueprint, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import shutil
import logging

backup_bp = Blueprint('backup', __name__)
logger = logging.getLogger(__name__)

# 請自行調整 basedir 路徑，建議與主程式同目錄或相對路徑
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# 動態資料庫使用者清單（依需求調整）
DYNAMIC_DB_USERS = {'dep1', 'dep2', 'dep3', 'dep4', 'dep5'}

def get_db_uri_for_user(username: str) -> str:
    logger.debug(f"判斷資料庫連線，username={username}")
    if username and username.lower() in DYNAMIC_DB_USERS:
        dep_num = username.lower().replace('dep', '')
        db_file = f"materials_{dep_num}.db"
        uri = f"sqlite:///{os.path.join(basedir, db_file)}"
        logger.debug(f"使用 {username} 對應資料庫 {uri}")
        return uri
    # 非動態資料庫使用者，回傳預設資料庫
    default_uri = f"sqlite:///{os.path.join(basedir, 'materials.db')}"
    logger.debug(f"使用預設資料庫 {default_uri}")
    return default_uri

@backup_bp.route('/api/backup', methods=['GET'])
@jwt_required()
def backup_database():
    try:
        username = get_jwt_identity()
        if not username:
            return jsonify({'error': '無法取得使用者身份'}), 401

        db_uri = get_db_uri_for_user(username)
        # sqlite URI 格式是 sqlite:///<path>，去除前面 sqlite:/// 取得實際檔案路徑
        if not db_uri.startswith("sqlite:///"):
            logger.error(f"資料庫 URI 格式錯誤: {db_uri}")
            return jsonify({'error': '資料庫 URI 格式錯誤'}), 500

        db_path = db_uri.replace("sqlite:///", "")
        db_path = os.path.abspath(db_path)
        logger.debug(f"使用者 {username} 的資料庫路徑: {db_path}")

        if not os.path.exists(db_path):
            logger.error(f"資料庫檔案不存在: {db_path}")
            return jsonify({'error': '資料庫檔案不存在'}), 404

        backup_filename = f"{username}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(os.path.dirname(db_path), backup_filename)

        shutil.copyfile(db_path, backup_path)
        logger.info(f"成功建立備份檔案: {backup_path}")

        response = send_file(backup_path, as_attachment=True, download_name=backup_filename)

        def cleanup_backup_file():
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    logger.info(f"成功刪除備份檔案: {backup_path}")
            except Exception as e:
                logger.error(f"刪除備份檔案失敗: {e}")

        response.call_on_close(cleanup_backup_file)

        return response

    except Exception as e:
        logger.exception(f"資料庫備份失敗: {e}")
        return jsonify({'error': '資料庫備份失敗'}), 500