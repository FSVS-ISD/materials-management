from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import InRecord, OutRecord, Material
from sqlalchemy import func
import threading
import logging
from datetime import datetime, timezone

record_bp = Blueprint('record', __name__)
db_lock = threading.Lock()
logger = logging.getLogger(__name__)

def update_material_current_stock(material_item_id, session):
    material = session.query(Material).filter_by(item_id=material_item_id).first()
    if not material:
        logger.warning(f"嘗試更新不存在的物料庫存: {material_item_id}")
        return False
    total_in = session.query(func.coalesce(func.sum(InRecord.quantity), 0)).filter(InRecord.material_id == material.id).scalar()
    total_out = session.query(func.coalesce(func.sum(OutRecord.quantity), 0)).filter(OutRecord.material_id == material.id).scalar()
    new_stock = total_in - total_out
    if new_stock < 0:
        logger.warning(f"物料 {material_item_id} 計算後庫存為負 ({new_stock})，已校正為 0。")
        new_stock = 0
    material.current_stock = new_stock
    logger.info(f"物料 {material_item_id} 的庫存已在 session 中更新為 {new_stock}。")
    return True

@record_bp.route('/api/barcode/record', methods=['POST'], strict_slashes=False)
@jwt_required()
def barcode_record():
    data = request.json
    if not data or 'item_id' not in data or 'type' not in data or 'quantity' not in data:
        return jsonify({'error': 'item_id, type, quantity 必填'}), 400
    session = g.db_session()
    material = session.query(Material).filter_by(item_id=data['item_id']).first()
    if not material:
        return jsonify({'error': '找不到物料'}), 404
    try:
        qty = int(data['quantity'])
        if qty <= 0:
            return jsonify({'error': '數量必須大於 0'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': '數量格式錯誤'}), 400
    current_user = get_jwt_identity()
    try:
        with db_lock:
            if data['type'] == 'in':
                source = data.get('source', "掃碼" if data.get('scan_mode', False) else None)
                handler = data.get('handler', current_user if data.get('scan_mode', False) else None)
                record = InRecord(
                    material_id=material.id, quantity=qty, source=source,
                    handler=handler, barcode=material.barcode, date=datetime.now(timezone.utc)
                )
                session.add(record)
            elif data['type'] == 'out':
                if material.current_stock < qty:
                    return jsonify({'error': '庫存不足，無法出庫'}), 400
                user = data.get('user', current_user if data.get('scan_mode', False) else None)
                department = data.get('department')
                purpose = data.get('purpose')
                source = data.get('source', "掃碼" if data.get('scan_mode', False) else None)
                handler = data.get('handler', current_user if data.get('scan_mode', False) else None)
                record = OutRecord(
                    material_id=material.id, quantity=qty, user=user, department=department,
                    purpose=purpose, barcode=material.barcode, date=datetime.now(timezone.utc),
                    source=source, handler=handler
                )
                session.add(record)
            else:
                return jsonify({'error': 'type 必須是 in 或 out'}), 400
            session.flush()
            update_material_current_stock(material.item_id, session)
            session.commit()
        return jsonify({
            'success': True,
            'record': {'type': data['type'], 'quantity': qty},
            'material': {
                'item_id': material.item_id, 'name': material.name,
                'category': material.category, 'current_stock': material.current_stock,
                'unit': material.unit, 'barcode': material.barcode
            }
        }), 201
    except Exception as e:
        session.rollback()
        logger.exception(f"新增出入庫紀錄時發生錯誤: {e}")
        return jsonify({'error': f'儲存失敗: {str(e)}'}), 500

@record_bp.route('/api/in-records', methods=['GET', 'POST'], strict_slashes=False)
@jwt_required()
def handle_in_records():
    session = g.db_session()
    if request.method == 'GET':
        try:
            query = session.query(InRecord, Material).join(Material, InRecord.material_id == Material.id)
            category = request.args.get('category')
            if category and category.lower() != 'all':
                clean_category = category.strip().lower()
                query = query.filter(func.lower(func.trim(Material.category)) == clean_category)
            records_with_material = query.order_by(InRecord.date.desc()).all()
            result = []
            for r, material in records_with_material:
                result.append({
                    'id': r.id,
                    'date': r.date.isoformat(),
                    'material_id': material.item_id if material else None,
                    'category': material.category if material else None,
                    'material_name': material.name if material else None,
                    'quantity': r.quantity,
                    'source': r.source,
                    'handler': r.handler,
                    'barcode': r.barcode
                })
            logger.debug(f"Fetched {len(result)} in-records.")
            return jsonify(result), 200
        except Exception as e:
            logger.exception(f"讀取入庫資料錯誤: {e}")
            return jsonify({'error': '讀取入庫資料失敗'}), 500
    else:  # POST
        data = request.json
        if not data or 'material_id' not in data or 'quantity' not in data:
            return jsonify({'error': 'material_id 與 quantity 必填'}), 400
        with db_lock:
            material = session.query(Material).filter_by(item_id=data['material_id']).first()
            if not material:
                return jsonify({'error': '找不到物料'}), 404
            try:
                record = InRecord(
                    material_id=material.id, quantity=data['quantity'], source=data.get('source'),
                    handler=data.get('handler'), barcode=material.barcode, date=datetime.now(timezone.utc)
                )
                session.add(record)
                session.flush()
                update_material_current_stock(material.item_id, session)
                session.commit()
                logger.info(f"InRecord added for material {material.item_id}, quantity {data['quantity']}.")
                return jsonify({
                    'message': '入庫紀錄新增成功',
                    'stock': material.current_stock,
                    'material': {
                        'item_id': material.item_id,
                        'name': material.name,
                        'category': material.category,
                        'current_stock': material.current_stock,
                        'unit': material.unit,
                        'barcode': material.barcode
                    },
                    'record': {
                        'quantity': data['quantity']
                    }
                }), 201
            except Exception as e:
                session.rollback()
                logger.exception(f"新增入庫紀錄錯誤: {e}")
                return jsonify({'error': '新增入庫紀錄失敗'}), 500

@record_bp.route('/api/in-records/<int:record_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_in_record(record_id):
    session = g.db_session()
    with db_lock:
        record = session.query(InRecord).get(record_id)
        if not record:
            return jsonify({'error': '找不到該入庫紀錄'}), 404
        try:
            material = session.query(Material).get(record.material_id)
            session.delete(record)
            session.flush()
            update_material_current_stock(material.item_id, session)
            session.commit()
            logger.info(f"InRecord {record_id} deleted.")
            return jsonify({'message': '入庫紀錄刪除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"刪除入庫紀錄錯誤: {e}")
            return jsonify({'error': '刪除入庫紀錄失敗'}), 500

@record_bp.route('/api/out-records', methods=['GET', 'POST'], strict_slashes=False)
@jwt_required()
def handle_out_records():
    session = g.db_session()
    if request.method == 'GET':
        try:
            query = session.query(OutRecord, Material).join(Material, OutRecord.material_id == Material.id)
            category = request.args.get('category')
            if category and category.lower() != 'all':
                clean_category = category.strip().lower()
                query = query.filter(func.lower(func.trim(Material.category)) == clean_category)
            records_with_material = query.order_by(OutRecord.date.desc()).all()
            result = []
            for r, material in records_with_material:
                result.append({
                    'id': r.id,
                    'date': r.date.isoformat(),
                    'material_id': material.item_id if material else None,
                    'material_name': material.name if material else None,
                    'category': material.category if material else None,
                    'quantity': r.quantity,
                    'user': r.user,
                    'department': r.department,
                    'purpose': r.purpose,
                    'barcode': r.barcode,
                    'source': r.source,
                    'handler': r.handler
                })
            logger.debug(f"Fetched {len(result)} out-records.")
            return jsonify(result), 200
        except Exception as e:
            logger.exception(f"讀取出庫資料錯誤: {e}")
            return jsonify({'error': '讀取出庫資料失敗'}), 500
    else:  # POST
        data = request.json
        if not data or 'material_id' not in data or 'quantity' not in data:
            return jsonify({'error': 'material_id 與 quantity 必填'}), 400
        with db_lock:
            material = session.query(Material).filter_by(item_id=data['material_id']).first()
            if not material:
                return jsonify({'error': '找不到物料'}), 404
            if material.current_stock < data['quantity']:
                return jsonify({'error': '庫存不足，無法出庫'}), 400
            try:
                record = OutRecord(
                    material_id=material.id, quantity=data['quantity'], user=data.get('user'),
                    department=data.get('department'), purpose=data.get('purpose'),
                    barcode=material.barcode, date=datetime.now(timezone.utc), source=data.get('source'),
                    handler=data.get('handler')
                )
                session.add(record)
                session.flush()
                update_material_current_stock(material.item_id, session)
                session.commit()
                logger.info(f"OutRecord added for material {material.item_id}, quantity {data['quantity']}.")
                return jsonify({
                    'message': '出庫紀錄新增成功',
                    'stock': material.current_stock,
                    'material': {
                        'item_id': material.item_id,
                        'name': material.name,
                        'category': material.category,
                        'current_stock': material.current_stock,
                        'unit': material.unit,
                        'barcode': material.barcode
                    },
                    'record': {
                        'quantity': data['quantity']
                    }
                }), 201
            except Exception as e:
                session.rollback()
                logger.exception(f"新增出庫紀錄錯誤: {e}")
                return jsonify({'error': '新增出庫紀錄失敗'}), 500

@record_bp.route('/api/out-records/<int:record_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_out_record(record_id):
    session = g.db_session()
    with db_lock:
        record = session.query(OutRecord).get(record_id)
        if not record:
            return jsonify({'error': '找不到該出庫紀錄'}), 404
        try:
            material = session.query(Material).get(record.material_id)
            session.delete(record)
            session.flush()
            update_material_current_stock(material.item_id, session)
            session.commit()
            logger.info(f"OutRecord {record_id} deleted.")
            return jsonify({'message': '出庫紀錄刪除成功'}), 200
        except Exception as e:
            session.rollback()
            logger.exception(f"刪除出庫紀錄錯誤: {e}")
            return jsonify({'error': '刪除出庫紀錄失敗'}), 500
