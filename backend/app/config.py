from pydantic_settings import BaseSettings,SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # 后端项目的根路径

class Setting(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY:str
    JWT_EXPIRE_HOURS:int=24
    JWT_ALGORITHM:str="HS256"
    LLM_API_KEY:str
    LLM_BASE_URL:str
    LLM_MODEL:str
    GLM_API_KEY:str=""
    GLM_MODEL:str=""
    GLM_BASE_URL:str=""
    TAVILY_API_KEY: str = ""


    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )

setting = Setting()

MODEL_REGISTRY = {
    "deepseek-flash": {
        "label": "DeepSeek Flash",
        "model": "deepseek-flash",
        "base_url": "https://api.deepseek.com",
        "api_key": setting.LLM_API_KEY,
        "supports_tools": True,
    },
    "glm-5.3-flash": {
        "label": "GLM 5.3 Flash",
        "model": "glm-5.3-flash",          # 字符串要和官方文档一致
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": setting.GLM_API_KEY,
        "supports_tools": True,
    },
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip",
}