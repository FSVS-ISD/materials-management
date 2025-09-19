# routes/__init__.py
from .user import user_bp
from .material import material_bp
from .category import category_bp
from .record import record_bp
from .report import report_bp
from .backup import backup_bp

from . import user, material, category, record, report, backup