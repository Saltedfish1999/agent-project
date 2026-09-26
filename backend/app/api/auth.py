from fastapi import APIRouter,Depends
from app.schemas.auth import LoginRequest, RegisterRequest
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.common.exceptions import BusinessException
from app.service import auth_service
from app.utils.jwt import create_access_token

from app.common.response import Response

router = APIRouter(prefix="/api/auth",tags=["权限验证"])

@router.post("/login")
def login(data:LoginRequest,db:Session=Depends(get_db)):
    result = auth_service.login(db,data)
    return Response.success(message="登录成功",data=result)

@router.post("/register")
def register(data:RegisterRequest,db:Session=Depends(get_db)):
    auth_service.register(db,data)
    return Response.success(message="注册成功")