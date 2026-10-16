"""联网搜索"""

import httpx

from app.config import setting

TIMEOUT = 15.0
TAVILY_URL = "https://api.tavily.com/search"

def search_web(query:str,max_results:int=5)->list[dict]:
    resp = httpx.post(
        TAVILY_URL,
        json={
            "api_key":setting.TAVILY_API_KEY,
            "query":query,
            "max_results":max_results,
            "search_depth":"basic"
        },
        timeout=TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "content": (item.get("content") or "")[:300],   # ← 截断省 token
        }
        for item in (data.get("results") or [])
    ]