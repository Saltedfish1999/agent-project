from chromadb import logger
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.conversation import Conversation
from app.config import UPLOAD_DIR
from app.database import Base,engine
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.files import router as files_router
from app.api.lab import router as lab_router
from app.api.equipment import router as equipment_router
from app.api.reservation import router as reservation_router
from app.api.ai import router as ai_router
from app.models.reservation import Reservation
from starlette.middleware.cors import CORSMiddleware
from app.common.exceptions import (
    BusinessException,
    business_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)
import asyncio

from app.service import kb_service, reservation_service

origins = [
	"http://localhost:5173",
	"http://127.0.0.1:5173",
]

Base.metadata.create_all(bind=engine)
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(
        reservation_service.run_expire_scan()
    )  # 启动项目开启异步的扫描任务
    yield
    task.cancel()  # 关闭项目同时取消异步任务

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(files_router)
app.include_router(lab_router)
app.include_router(equipment_router)
app.include_router(reservation_router)
app.include_router(ai_router)


# 注册异常处理器
app.add_exception_handler(BusinessException,business_exception_handler)
app.add_exception_handler(HTTPException,http_exception_handler)
app.add_exception_handler(RequestValidationError,validation_exception_handler)

# 全局异常兜底，最好注册
app.add_exception_handler(Exception,global_exception_handler)

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,        # 允许的前端源，不要直接写 ["*"]
	allow_credentials=True,       # ✅ 关键：允许前端携带 Authorization token
	allow_methods=["*"],          # 允许所有请求方法 GET POST PUT DELETE OPTIONS
	allow_headers=["*"],          # 允许所有请求头（包含Authorization）
)

@asynccontextmanager
async def listspan(app:FastAPI):
    # 预热向量库
    try:
        await asyncio.to_thread(kb_service.warmup) # 不会阻塞事件循环
    except Exception:
        logger.exception("向量库预热失败，服务继续启动")
    # 启动项目开启的异步扫描任务
    task = asyncio.create_task(reservation_service.run_expire_scan())
    yield
    task.cancel() # 关闭项目同时取消异步任务

# 挂载静态资源：/uploads/xxx.jpg → uploads/xxx.jpg
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {"message": "Hello FastAPI"}