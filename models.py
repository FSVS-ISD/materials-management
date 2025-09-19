from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    item_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    unit = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    safety_stock = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)
    notes = Column(Text)
    barcode = Column(String(100), unique=True, index=True)

    in_records = relationship('InRecord', backref='material_ref', lazy=True, cascade="all, delete-orphan")
    out_records = relationship('OutRecord', backref='material_ref', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Material(item_id='{self.item_id}', name='{self.name}')>"

    def to_dict(self):
        return {
            'item_id': self.item_id,
            'barcode': self.barcode,
            'name': self.name,
            'unit': self.unit,
            'category': self.category,
            'safety_stock': self.safety_stock,
            'current_stock': self.current_stock,
            'notes': self.notes
        }

class InRecord(Base):
    __tablename__ = 'in_record'
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    source = Column(String(100))
    handler = Column(String(50))
    barcode = Column(String(100))

class OutRecord(Base):
    __tablename__ = 'out_record'
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    user = Column(String(50))
    department = Column(String(50))
    purpose = Column(String(100))
    barcode = Column(String(100))
    source = Column(String(100))
    handler = Column(String(50))

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    password_last_changed = Column(DateTime, nullable=True)  # 密碼最後修改時間
    role = Column(String(20), default='user')

    def set_password(self, password: str):
        """將明文密碼加密並存入，更新密碼修改時間"""
        self.password_hash = generate_password_hash(password)
        self.password_last_changed = datetime.utcnow()

    def check_password(self, password: str) -> bool:
        """驗證明文密碼是否與密碼雜湊相符"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """回傳不含密碼的使用者資訊字典"""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'password_last_changed': self.password_last_changed.isoformat() if self.password_last_changed else None
        }

class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
