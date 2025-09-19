import os
import logging
import sqlite3

logger = logging.getLogger(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = os.path.join(basedir, 'materials.db')

def get_db_uri_for_user(username: str) -> str:
    """
    從主資料庫的 user 表查詢 username，取得對應部門編號，
    再回傳對應資料庫 URI。
    """
    if not username:
        logger.debug("username 為空，使用預設資料庫")
        return f"sqlite:///{default_db_path}"

    # 先連接主資料庫查詢 user 表
    try:
        conn = sqlite3.connect(default_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT dep_num FROM user WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"查詢主資料庫 user 表失敗: {e}")
        # 發生錯誤時使用預設資料庫
        return f"sqlite:///{default_db_path}"

    if row:
        dep_num = row[0]
        # 檢查 dep_num 是否為 1~5 的有效部門編號
        if isinstance(dep_num, int) and 1 <= dep_num <= 5:
            db_file = f"materials_{dep_num}.db"
            uri = f"sqlite:///{os.path.join(basedir, db_file)}"
            logger.debug(f"使用者 {username} 對應部門 {dep_num} 資料庫 {uri}")
            return uri

    # 找不到使用者或部門不符，回傳預設資料庫
    default_uri = f"sqlite:///{default_db_path}"
    logger.debug(f"使用者 {username} 使用預設資料庫 {default_uri}")
    return default_uri
