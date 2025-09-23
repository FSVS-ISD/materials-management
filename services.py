import threading
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class LoginStateService:
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._active_user = None
        self._login_queue = []
        self._activity_time = {}
        self._initialized = True
    
    def try_login(self, username):
        with self._lock:
            if self._active_user is None:
                self._active_user = username
                self._activity_time[username] = datetime.now(timezone.utc)
                logger.info(f"使用者 {username} 成功登入 (無其他使用者登入中)")
                return True
            elif username == self._active_user:
                self._activity_time[username] = datetime.now(timezone.utc)
                logger.info(f"使用者 {username} 重複登入，更新活動時間")
                return True
            else:
                if username not in self._login_queue:
                    self._login_queue.append(username)
                    logger.info(f"使用者 {username} 加入等待佇列")
                return False
    
    def notify_logout(self, username):
        with self._lock:
            if self._active_user == username:
                logger.info(f"使用者 {username} 登出，釋放登入權限")
                self._active_user = None
                self._activity_time.pop(username, None)
                if self._login_queue:
                    next_user = self._login_queue.pop(0)
                    self._active_user = next_user
                    self._activity_time[next_user] = datetime.now(timezone.utc)
                    logger.info(f"使用者 {next_user} 從佇列中取得登入權限")
    
    def check_inactivity(self):
        with self._lock:
            if self._active_user:
                last_active = self._activity_time.get(self._active_user)
                if last_active and (datetime.now(timezone.utc) - last_active).total_seconds() > 180:
                    logger.info(f"使用者 {self._active_user} 閒置超過3分鐘，自動登出")
                    self.notify_logout(self._active_user)
                    return True
            return False

# 實例化登入狀態服務
login_service = LoginStateService()
