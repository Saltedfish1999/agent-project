from operator import or_
from app.common.exceptions import BusinessException
from app.common.response import pageResponse
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.schemas.equipment import (
    EquipmentResponse,
    EquipmentCreateRequest,
    EquipmentUpdateRequest,
)
from sqlalchemy.orm import Session

def get_equipment_page_list(
    db:Session,
    page:int,
    page_size:int,
    keywords:str | None = None,
    lab_id:int | None = None
):
    """分页模糊查询列表"""
    query = db.query(Equipment)
    if lab_id:
        query = query.filter(Equipment.lab_id == lab_id)

    if keywords:
        query = query.fiter(Equipment.name.ilike(f"%{keywords}%"))
    total = query.count()
    items = (
        query.order_by(Equipment.id.desc()) # 按照id降序排序
        .offset((page - 1) * page_size) # 跳过前面的数据
        .limit(page_size) # 最多取多少条数据
        .all()
    )
    result = []
    for item in items:
        res = EquipmentResponse.model_validate(item) # 将数据库对象转换为响应对象
        res.lab_name = item.lab.name if item.lab else None
        result.append(res)
    return pageResponse(list=result,total=total)

def create_equipment(db: Session, data: EquipmentCreateRequest):
    """新增"""
    exist = db.query(Equipment).filter(Equipment.name == data.name).first()
    if exist:
        raise BusinessException(message="实验室设备已存在")
    equipment = Equipment(**data.model_dump()) # 将校验过的数据转为ORM对象
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return res

def update_equipment(db: Session, equipment_id: int, data: EquipmentUpdateRequest):
    """更新"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="实验室设备不存在")
    payload = data.model_dump(exclude_none=True)
    lab_id = payload.get("lab_id", equipment.lab_id)
    name = payload.get("name", equipment.name)
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    exist = (
        db.query(Equipment)
        .filter(
            Equipment.lab_id == lab_id,
            Equipment.name == name,
            Equipment.id != equipment.id,
        )
        .first()
    )
    if exist:
        raise BusinessException(message="同一个实验室不能存在同名的设备")

    for filed, value in payload.items():
        # 按照字典动态给对象复制，逐个写到ORM对象
        setattr(equipment, filed, value)

    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return EquipmentResponse.model_validate(equipment)

def delete_equipment(db: Session, equipment_id: int):
    """删除"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="实验室设备不存在")
    db.delete(equipment)
    db.commit()