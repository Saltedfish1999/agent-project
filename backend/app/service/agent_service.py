from typing import Any, Iterator,AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
import traceback
from app.schemas.conversation import ChatMessageResponse
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session
from langgraph.checkpoint.memory import InMemorySaver

from app.common.exceptions import BusinessException
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.service import agent_tools, conversation_service
from app.config import setting
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.config import BASE_DIR,MODEL_REGISTRY,setting


CHECKPOINT_PATH = BASE_DIR / "data" / "checkpoints.sqlite"
_checkpointer: AsyncSqliteSaver | None = None
SYSTEM_PROMPT = """你是智能实验室预约系统的 Agent，回答要简洁。
你可以：
1. 使用 search_lab_docs 查询实验室的规则、安全、开放时间等问题
2. 使用 list_open_labs / list_lab_equipments  查询真实的实验室和设备
3. 再用户进行了预约确认后，使用 create_lab_reservation 来进行真实的预约落库
4. 使用 get_today 来进行日期的换算

## 必须遵守
当用户提到了 今天、明天、后天 等日期相关的问题，请先调用 get_today 来获取日期，**不要直接返回 我需要确定明天的具体日期**。

在提交预约之前必须向用户复述：实验室ID与名称（或设备ID和名称）、日期、开始时间、结束时间。并得到用户确认再进行实际操作。
用户没说【确认】【确认预约】【就这样预约】等确定性回复之前，不要调用 create_lab_reservation。
工作流的确认环节里如果缺少了 lab_id，请先 list_open_labs 查到了 lab_id 再创建，不要瞎写。
工作流的确认环节里如果缺少了 equipment_id，请先 list_lab_equipments 查到了 equipment_id 再创建，不要瞎写。

预约成功后状态是待审核，必须管理员确认后实验室（或设备）才能使用。
不要瞎编数据库里没有的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用 search_lab_docs，不要凭空回复。
"""

# 工具英文名 → 页面上给人看的中文过程文案
TOOL_LABELS = {
    "search_lab_docs": "检索实验室知识库",
    "list_open_labs": "查询开放实验室",
    "list_lab_equipments": "查询实验室设备",
    "create_lab_reservation": "提交预约",
    "get_today": "获取今天日期",
}

def build_agent(db:Session,current_user:User,model_id:str | None = None,enable_web:bool=False):
    if _checkpointer is None:
        raise BusinessException(message="检查点未初始化，请重启服务")
    tools = agent_tools.build_tools(db,current_user,enable_web)
    cfg = _resolve_model(model_id)
    llm = ChatOpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        temperature=0,
        streaming=True
    ).bind_tools(tools)

    def agent_node(state:MessagesState):
        """langGraph执行的工作流的节点"""
        response = llm.invoke(state["messages"])
        return {"messages":[response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent",agent_node) #调用大模型的节点
    graph.add_node("tools",ToolNode(tools)) # tool call的节点
    graph.add_edge(START,"agent") # 流程的起点， call LLM
    graph.add_conditional_edges(
        "agent",tools_condition
    ) # 查看是否有tool_call,没有就end输出
    graph.add_edge("tools","agent")
    return graph.compile(checkpointer=_checkpointer)

def run_agent(db:Session,current_user:User,data:ChatRequest):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")

    # 挑出最后一条用户信息作为提问
    question = next(
        (m.content.strip() for m in reversed(data.messages or [])
        if m.role == "user" and m.content.strip()),
        ""
    )

    if not question:
        raise BusinessException(message="请输入您要对话的内容")

    # 获取当前对话的线程id
    thread_id = conversation_service.resolve_thread(db,current_user,data.thread_id,question)
    agent = build_agent(db,current_user,data.model,data.enable_web)

    try:
        result = agent.invoke(
            {"messages":[SystemMessage(content=SYSTEM_PROMPT,id="system"),HumanMessage(content=question)]},
            config={"configurable":{"thread_id":thread_id},"recursion_limit":10}
        ) # 设置对话循环的上限是10轮
    except BusinessException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise BusinessException(message=f"大模型调用失败，请稍后重试：{exc}") from exc

    messages = result.get("messages") or []
    if not messages:
        raise BusinessException(message="大模型没有返回内容")
    for message in reversed(messages):
        if isinstance(message,AIMessage) and message.content.strip():
            content = message.content.strip()
            if isinstance(content,list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            if str(content).strip():
                return str(content).strip()


def _chunk_text(chunk:Any) -> str:
    """从流式模型中抠出文本"""
    if chunk is None:
        return ""
    # chunk中的内容在content
    content = getattr(chunk,"content",None)
    if isinstance(content,str):
        return content
    if isinstance(content,list):
        parts = []
        for part in content:
            if isinstance(part,dict):
                parts.append(part.get("text") or "")
            elif isinstance(part,str):
                parts.append(part)
        return "".join(parts)
    return str(content) if content is not None else ""

def _tool_output_preview(output:Any,limit:int = 200) -> str:
    """把工具结果收成短预览,避免整段JSON刷到前端过程区"""
    if isinstance(output,ToolMessage):
        output = output.content
    text = output if isinstance(output,str) else str(output)
    # 避免太长 直接截断
    return text if len(text) <= limit else text[:limit] + "..."

def _build_history(data:ChatRequest) -> list:
    """前端只传user/assistant文本，转成LangChain信息对象"""
    history = []
    for message in data.messages or []:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")
    return history

async def stream_agent(db:Session,current_user:User,data:ChatRequest) -> AsyncIterator[dict]:
    """生成器：边跑agent边yield事件
    事件类型：status / tool_start / tool_end / token / done / error
    """
    try:
        # history = _build_history(data)
        question = next(
            (m.content.strip() for m in reversed(data.messages or [])
             if m.role == "user" and m.content.strip()),
            ""
        )
        if not question:
            raise BusinessException(message="请输入您要对话的内容")
        #拿到thread_id
        thread_id = conversation_service.resolve_thread(db,current_user,data.thread_id,question)

        inputs = {"messages":[SystemMessage(content = SYSTEM_PROMPT,id="system"),HumanMessage(content=question)]}
        agent = build_agent(db,current_user,data.model,data.enable_web)

        yield{"type":"status","message":"正在思考..."}

        async for event in agent.astream_events(
            inputs,
            version="v2",
            config={"configurable":{"thread_id":thread_id},"recursion_limit":10} # tool调用上限，防止空转
        ):
            kind = event.get("event")
            if kind == "on_tool_start":
                name = event.get("name") or ""
                yield{
                   "type":"tool_start",
                   "name":name,
                   "label":TOOL_LABELS.get(name,name) 
                }
            elif kind == "on_tool_end":
                name = event.get("name") or ""
                yield{
                    "type":"tool_end",
                    "name":name,
                    "label":TOOL_LABELS.get(name,name),
                    "preview":_tool_output_preview(
                        (event.get("data") or {}).get("output")
                    )
                }
            elif kind == "on_chat_model_stream":
                # 只收 agent 节点的字；其它内部节点的噪声丢掉
                meta = event.get("metadata") or {}
                if meta.get("langgraph_node") not in (None, "agent"):
                    continue
                text = _chunk_text((event.get("data") or {}).get("chunk"))
                if text:
                    yield {"type": "token", "content": text}
                # 正常跑完：不要在 done 里再带一份全文，前端已经用 token 拼好了
        yield {"type": "done"}
    except BusinessException as exc:
        yield {"type": "error", "message": exc.message}
    except Exception:
        traceback.print_exc()
        yield {"type": "error", "message": "大模型调用失败，请稍后重试"}


async def load_messages(thread_id:str) -> list:
    """读取会话的原始消息"""
    tup = await _checkpointer.aget_tuple({"configurable":{"thread_id":thread_id}})
    if tup is None:
        return []
    return tup.checkpoint.get("channel_values",{}).get("messages",[])

def to_chat_messages(messages:list) -> list:
    """过滤成展示文本"""
    out = []
    for m in messages:
        if not isinstance(m,(HumanMessage,AIMessage)):
            continue
        if getattr(m,"tool_calls",None):
            continue
        if not isinstance(m.content,str) or not m.content.strip():
            continue
        out.append(ChatMessageResponse(
            role="user" if isinstance(m,HumanMessage) else "assistant",
            content=m.content.strip()
        ))
    return out

async def delete_thread(thread_id:str) -> None:
    """删除对话状态"""
    await _checkpointer.adelete_thread(thread_id)

async def init_checkpointer() -> None:
    """启动调用一次，建立持久化检查点"""
    global _checkpointer
    if _checkpointer is not None:
        return 
    conn  = await aiosqlite.connect(str(CHECKPOINT_PATH))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    _checkpointer = saver

async def close_checkpointer() -> None:
    """关闭时释放连接"""
    global _checkpointer
    if _checkpointer is not None:
        await _checkpointer.conn.close()
        _checkpointer = None

def _resolve_model(model_id:str | None) -> dict:
    """前端传来的模型id解析成实际连接参数"""
    if not model_id:
        return {
            "model": setting.LLM_MODEL,
            "base_url": setting.LLM_BASE_URL,
            "api_key": setting.LLM_API_KEY,
        }
    cfg = MODEL_REGISTRY.get(model_id)
    if not cfg:
        raise BusinessException(message=f"不支持的模型：{model_id}")
    if not cfg["api_key"]:
        raise BusinessException(message=f"模型「{cfg['label']}」未配置 API Key")
    return cfg