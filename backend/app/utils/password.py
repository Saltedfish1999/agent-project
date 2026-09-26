import bcrypt

# bcrypt 只处理前 72 个字节，超出部分直接抛 ValueError，所以统一在这里截断
MAX_PASSWORD_BYTES = 72

def hash_password(password:str)->str:
    """对密码加密"""
    raw = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(raw,bcrypt.gensalt()).decode("utf-8")

def verify_password(password:str,hashed_password:str) -> bool:
    """验证密码的有效性"""
    if not hashed_password:
        return False
    raw = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(raw,hashed_password.encode("utf-8"))
    except ValueError:
        # 哈希格式非法（例如历史遗留的明文密码），按验证失败处理，不要抛 500
        return False