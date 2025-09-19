from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required
from models import Category, Material  # 確認已正確 import
from sqlalchemy import func
import threading
import logging

category_bp = Blueprint('category', __name__)
db_lock = threading.Lock()
logger = logging.getLogger(__name__)

@category_bp.route('/api/categories', methods=['GET', 'POST'], strict_slashes=False)
@jwt_required()
def handle_categories():
    session = g.db_session()
    if request.method == 'POST':
        data = request.json
        if not data or 'name' not in data:
            return jsonify({'error': '分類名稱必填'}), 400

        name = data['name'].strip()
        if not name:
            return jsonify({'error': '分類名稱不可為空白'}), 400

        with db_lock:
            exists = session.query(Category).filter(
                func.lower(func.trim(Category.name)) == name.lower()
            ).first()
            if exists:
                return jsonify({'error': '分類名稱已存在'}), 409
            try:
                category = Category(name=name)
                session.add(category)
                session.commit()
                logger.info(f"Category '{name}' created.")
                return jsonify({'message': '分類新增成功', 'id': category.id}), 201
            except Exception as e:
                session.rollback()
                logger.exception(f"新增分類錯誤: {e}")
                return jsonify({'error': '新增分類失敗'}), 500

    else:  # GET
        try:
            categories = session.query(Category).order_by(Category.name).all()
            logger.debug(f"Fetched {len(categories)} categories.")
            return jsonify([{'id': c.id, 'name': c.name} for c in categories])
        except Exception as e:
            logger.exception(f"讀取分類資料錯誤: {e}")
            return jsonify({'error': '讀取分類資料失敗'}), 500

@category_bp.route('/api/categories/<int:cat_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_category(cat_id):
    session = g.db_session()
    data = request.json
    if not data or 'name' not in data:
        return jsonify({'error': '分類名稱必填'}), 400

    name = data['name'].strip()
    if not name:
        return jsonify({'error': '分類名稱不可為空白'}), 400

    with db_lock:
        category = session.query(Category).filter_by(id=cat_id).first()
        if not category:
            return jsonify({'error': '找不到該分類'}), 404
        exists = session.query(Category).filter(
            func.lower(func.trim(Category.name)) == name.lower(),
            Category.id != cat_id
        ).first()
        if exists:
            return jsonify({'error': '分類名稱已存在'}), 409
        try:
            category.name = name
            session.commit()
            logger.info(f"Category {cat_id} updated to '{name}'.")
            return jsonify({'message': '分類更新成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"更新分類錯誤: {e}")
            return jsonify({'error': '更新分類失敗'}), 500

@category_bp.route('/api/categories/<int:cat_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_category(cat_id):
    session = g.db_session()
    with db_lock:
        category = session.query(Category).filter_by(id=cat_id).first()
        if not category:
            return jsonify({'error': '找不到該分類'}), 404

        # 檢查是否有物料使用此分類（忽略大小寫與空白）
        materials_using_category = session.query(Material).filter(
            func.lower(func.trim(Material.category)) == category.name.strip().lower()
        ).first()

        if materials_using_category:
            return jsonify({'error': '該分類內有物料，無法刪除'}), 400

        try:
            session.delete(category)
            session.commit()
            logger.info(f"Category {cat_id} deleted.")
            return jsonify({'message': '分類刪除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"刪除分類錯誤: {e}")
            return jsonify({'error': '刪除分類失敗'}), 500