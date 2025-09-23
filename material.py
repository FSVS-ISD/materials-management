from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required
from models import Material
from sqlalchemy import func
import logging
import re
import threading

material_bp = Blueprint('material', __name__, url_prefix='/api/materials')
logger = logging.getLogger(__name__)
db_lock = threading.Lock()

def generate_new_item_id(session):
    last_material = session.query(Material).filter(
        Material.item_id.like('M____')
    ).order_by(Material.item_id.desc()).first()

    if last_material:
        match = re.match(r'M(\d{4})', last_material.item_id)
        if match:
            last_num = int(match.group(1))
            new_num = last_num + 1
        else:
            new_num = 1
    else:
        new_num = 1

    new_id = f"M{new_num:04d}"
    return new_id

@material_bp.route('/', methods=['GET', 'POST'], strict_slashes=False)
@jwt_required()
def handle_materials():
    session = g.db_session()
    if request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'error': '缺少資料'}), 400

        required_fields = ['name', 'unit', 'category']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({'error': f"缺少必填欄位：{', '.join(missing)}"}), 400

        try:
            with db_lock:
                item_id = generate_new_item_id(session)
                barcode = f"BC-00{item_id}"

                existing = session.query(Material).filter(Material.barcode == barcode).first()
                if existing:
                    return jsonify({'error': '條碼已存在'}), 409

                material = Material(
                    item_id=item_id,
                    name=data['name'],
                    unit=data['unit'],
                    category=data['category'],
                    safety_stock=data.get('safety_stock', 0),
                    current_stock=0,
                    notes=data.get('notes', ''),
                    barcode=barcode
                )
                session.add(material)
                session.commit()
            logger.info(f"Material 新增成功，item_id={material.item_id}")
            return jsonify({
                'message': '物料新增成功',
                'item_id': material.item_id,
                'barcode': material.barcode
            }), 201

        except Exception as e:
            session.rollback()
            logger.exception(f"新增物料錯誤: {e}")
            return jsonify({'error': '新增物料失敗'}), 500

    else:  # GET
        try:
            query = session.query(Material)
            category = request.args.get('category')
            if category and category.lower() != 'all':
                clean_category = category.strip().lower()
                query = query.filter(func.lower(func.trim(Material.category)) == clean_category)
            materials = query.order_by(Material.item_id).all()
            result = [{
                'item_id': m.item_id,
                'barcode': m.barcode,
                'name': m.name,
                'unit': m.unit,
                'category': m.category,
                'safety_stock': m.safety_stock,
                'current_stock': m.current_stock,
                'notes': m.notes
            } for m in materials]
            logger.debug(f"Fetched {len(materials)} materials.")
            return jsonify(result)
        except Exception as e:
            logger.exception(f"讀取物料資料錯誤: {e}", exc_info=True)
            return jsonify({'error': '讀取物料資料失敗，請稍後再試。'}), 500

@material_bp.route('/<string:item_id>', methods=['PUT', 'DELETE'], strict_slashes=False)
@jwt_required()
def modify_or_delete_material(item_id):
    session = g.db_session()
    material = session.query(Material).filter_by(item_id=item_id).first()
    if not material:
        return jsonify({'error': '物料不存在'}), 404

    if request.method == 'PUT':
        data = request.json
        if not data:
            return jsonify({'error': '缺少更新資料'}), 400
        try:
            if 'name' in data and not data['name']:
                return jsonify({'error': '名稱不可為空'}), 400
            if 'unit' in data and not data['unit']:
                return jsonify({'error': '單位不可為空'}), 400
            if 'category' in data and not data['category']:
                return jsonify({'error': '分類不可為空'}), 400

            if 'barcode' in data:
                new_barcode = data['barcode']
                if new_barcode:
                    new_barcode_clean = new_barcode.strip().lower()
                    existing = session.query(Material).filter(
                        func.lower(func.trim(Material.barcode)) == new_barcode_clean,
                        Material.item_id != item_id
                    ).first()
                    if existing:
                        return jsonify({'error': '條碼已存在'}), 409
                    material.barcode = new_barcode.strip()
                else:
                    material.barcode = None

            material.name = data.get('name', material.name)
            material.unit = data.get('unit', material.unit)
            material.category = data.get('category', material.category)
            material.safety_stock = data.get('safety_stock', material.safety_stock)
            material.notes = data.get('notes', material.notes)

            session.commit()
            logger.info(f"Material {item_id} 更新成功。")
            return jsonify({'message': '物料更新成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"更新物料錯誤: {e}")
            return jsonify({'error': '更新物料失敗'}), 500

    elif request.method == 'DELETE':
        try:
            session.delete(material)
            session.commit()
            logger.info(f"Material {item_id} 刪除成功。")
            return jsonify({'message': '物料刪除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"刪除物料錯誤: {e}")
            return jsonify({'error': '刪除物料失敗'}), 500

@material_bp.route('/barcode/<string:barcode>', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_material_by_barcode(barcode):
    session = g.db_session()
    clean_barcode = barcode.strip()
    material = session.query(Material).filter(func.lower(func.trim(Material.barcode)) == clean_barcode.lower()).first()
    if not material:
        logger.warning(f"找不到條碼: {barcode} (清理後: {clean_barcode})")
        return jsonify({'error': '找不到對應的物料資料'}), 404
    result = {
        'item_id': material.item_id,
        'barcode': material.barcode,
        'name': material.name,
        'unit': material.unit,
        'category': material.category,
        'safety_stock': material.safety_stock,
        'current_stock': material.current_stock,
        'notes': material.notes
    }
    logger.debug(f"條碼 {barcode} 查詢結果: {result}")
    return jsonify(result), 200

@material_bp.route('/summary', methods=['GET'])
@jwt_required()
def material_summary():
    session = g.db_session()
    try:
        total_count = session.query(func.count(Material.item_id)).scalar()
        low_stock_count = session.query(func.count(Material.item_id)).filter(
            Material.current_stock < Material.safety_stock,
            Material.safety_stock > 0
        ).scalar()

        return jsonify({
            'total': total_count,
            'lowStock': low_stock_count
        }), 200

    except Exception as e:
        logger.exception(f"儀表板統計失敗: {e}")
        return jsonify({'error': '獲取統計數據失敗'}), 500
