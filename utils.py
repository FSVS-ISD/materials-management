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

    try:
        # 先連接主資料庫查詢 user 表
        conn = sqlite3.connect(default_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT dep_num FROM user WHERE username = ?", (username,))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"查詢主資料庫 user 表失敗: {e}")
        return f"sqlite:///{default_db_path}"
    finally:
        # 確保連接在任何情況下都會被關閉
        if conn:
            conn.close()

    if row:
        dep_num = row[0]
        # 檢查 dep_num 是否為 1~9 的有效部門編號
        if isinstance(dep_num, int) and 1 <= dep_num <= 9:
            db_file = f"materials_{dep_num}.db"
            uri = f"sqlite:///{os.path.join(basedir, db_file)}"
            logger.debug(f"使用者 {username} 對應部門 {dep_num} 資料庫 {uri}")
            return uri

    # 找不到使用者或部門不符，回傳預設資料庫
    default_uri = f"sqlite:///{default_db_path}"
    logger.debug(f"使用者 {username} 使用預設資料庫 {default_uri}")
    return default_uri
