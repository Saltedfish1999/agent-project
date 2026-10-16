from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy.orm import Session
import json 
from app.common.exceptions import BusinessException
from app.models.reservation import Reservation
from app.models.user import User
from app.service import equipment_service, kb_service, lab_service, reservation_service, web_search_service


def build_tools(db:Session,current_user:User,enable_web:bool=False):

    @tool
    def search_lab_docs(query:str) -> str:
        """根据用户的提问检索知识库"""
        try:
            return kb_service.search(query) or "没有检索到相关知识"
        except Exception as exc:
            return json.dumps({
                "ok":False,
                "error":str(exc)
            },ensure_ascii=False)

    @tool
    def list_open_labs(keywords:str = "") -> str:
        """查询开放的实验室列表"""
        try:
            keywords = keywords.strip() or None
            page = lab_service.get_lab_page_list(
                db,page=1,page_size=10,keywords=keywords,status=1
            )
            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location,
                    "capacity": item.capacity,
                    "open_time": item.open_time,
                    "close_time": item.close_time,
                }
                for item in page.list
            ]
            # 将字典转化为JSON字符串
            return json.dumps({"total":page.total,"labs":rows},ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False)

    @tool
    def list_lab_equipments(lab_id:int,keywords:str="") -> str:
        """查询某个实验室的设备列表"""
        try:
            keywords = keywords.strip() or None
            page = equipment_service.get_equipment_page_list(
                db,page=1,page_size=10,lab_id=int(lab_id),keywords=keywords
            )
            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "lab_id": item.lab_id,
                    "lab_name": item.lab_name,
                    "spec": item.spec,
                    "quantity": item.quantity,
                    "status": item.status,
                }
                for item in page.list
            ]
            return json.dumps(
                {"total":page.total,"equipments":rows},ensure_ascii=False
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @tool
    def create_lab_reservation(
        lab_id:int,
        date:str,
        start_time:str,
        end_time:str,
        equipment_id:int | None = None,
        remark: str | None = None
    ) -> str:
        """创建预约单预约实验室或设备"""
        try:
            data = Reservation(
                lab_id = lab_id,
                equipment_id = equipment_id,
                date = date,
                start_time = start_time,
                end_time = end_time,
                remark = remark
            )
            reservation_service.create_reservation(db,current_user,data)
            return json.dumps(
                {
                    "ok": True,
                    "message": "预约已提交，请等待管理员审核",
                    "lab_id": lab_id,
                    "equipment_id": equipment_id,
                    "date": date,
                    "start_time": start_time,
                    "end_time": end_time, 
                },
                ensure_ascii=False
            )
        except BusinessException as exc:
            return json.dumps({"ok": False, "error": exc.message}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @tool
    def get_today() -> str:
        """获取服务器当前日期"""
        now = datetime.now()
        return now.strftime("%Y-%m-%d")

    @tool
    def get_my_reservations(status:int|None = None) -> str:
        """获取当前用户自己的预约记录。
        status: 0=待审核 1=已通过 2=已拒绝 3=已取消，不传则查全部"""
        STATUS_LABEL = {0: "待审核", 1: "已通过", 2: "已拒绝", 3: "已取消"}
        try:
            page = reservation_service.get_reservation_page_list(db,current_user,page=1,page_size=10,status=status)
            rows = [
                {
                    "id": item.id,
                    "lab_id": item.lab_id,
                    "lab_name": item.lab_name,
                    "equipment_name":item.equipment_name,
                    "status": item.status,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "status_text":STATUS_LABEL.get(item.status,"未知")
                }
                for item in page.list
            ]
            return json.dumps({"ok": True, "total": page.total, "reservations": rows},ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @tool
    def cancel_my_reservation(reservation_id:int) -> str:
        """取消当前用户的预约记录"""
        try:
            reservation_service.cancel_reservation(db, current_user, reservation_id)
            return json.dumps({"ok":True,"reservation_id":reservation_id,"message":"预约已经取消"},ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @tool
    def web_search(query:str) -> str:
        """联网搜索互联网上的最新信息。
        适用于：查询实时信息、新闻、政策，或知识库里找不到答案的问题。
        不适用于：本实验室的规则、开放时间、设备信息（请用 search_lab_docs）。"""
        try:
            results = web_search_service.search_web(query)
            if not results:
                return json.dumps(
                    {"ok": True, "results": [], "message": "没有搜索到相关内容"},
                    ensure_ascii=False,
                )
            return json.dumps(
                {"ok": True, "query": query, "results": results},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    
    tools = [
        search_lab_docs,
        list_open_labs,
        list_lab_equipments,
        create_lab_reservation,
        get_today,
        get_my_reservations,
        cancel_my_reservation,
    ]
    if enable_web:
        tools.append(web_search)
    return tools