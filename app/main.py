import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db.data_manager import DataManager
from app.services.session_manager import SessionManager
from app.services.llm_manager import LLMManager
from app.services.chat_sdk import ChatSDK
from app.schemas.chat import APIConfig, OllamaConfig
from app.core.logger import log

from app.core.model_registry import get_all_models

# 生命周期管理
sdk_instance = None  # 全局 SDK 实例


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sdk_instance
    log.info("ChatServer: 正在初始化数据库与 ChatSDK...")

    # 初始化数据库
    # 注意：在实际生产中，数据库 URL 应该写在 .env 配置文件里
    db_manager = DataManager("sqlite+aiosqlite:///./chat.db")
    await db_manager.init_database()

    # 实例化 Managers
    session_manager = SessionManager(db_manager)
    llm_manager = LLMManager()
    sdk_instance = ChatSDK(llm_manager, session_manager)

    # 调用统一配置函数组装模型配置
    configs = get_all_models()

    # 启动 SDK
    if await sdk_instance.init_models(configs):
        log.info(f"ChatServer: 成功挂载了 {len(configs)} 个模型!!!")
    else:
        log.error("ChatServer: ChatSDK 初始化失败!!!")

    yield  # 将控制权交还给 FastAPI，服务器正式开始接收请求

    # 服务器停止时的清理逻辑
    log.info("ChatServer: HTTP 服务已停止，资源清理完毕。")


# FastAPI 实例与中间件配置
app = FastAPI(lifespan=lifespan, title="AI Chat API", version="1.0")

# 允许跨域请求 (对应 C++ 里的 Access-Control-Allow-Origin: *)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic 接收体定义
class CreateSessionReq(BaseModel):
    model: str = "deepseek-chat"


class SendMessageReq(BaseModel):
    session_id: str
    message: str


# 通用响应生成器
def standard_response(
    success: bool, message: str, data: dict = None, status_code: int = 200
):
    content = {"success": success, "message": message}
    if data is not None:
        content["data"] = data
    return JSONResponse(status_code=status_code, content=content)


# HTTP 路由注册


@app.post("/api/session")
async def create_session(req: CreateSessionReq):
    """处理创建会话请求"""
    session_id = await sdk_instance.create_session(req.model)
    if not session_id:
        return standard_response(
            False, "create session failed (Internal Error)", status_code=500
        )

    return standard_response(
        True, "create session success", {"session_id": session_id, "model": req.model}
    )


@app.get("/api/sessions")
async def get_session_lists():
    """处理获取会话列表请求"""
    session_ids = await sdk_instance.get_session_list()
    data_array = []

    for sid in session_ids:
        session = await sdk_instance.get_session(sid)
        if session:
            first_msg = session.messages[0].content if session.messages else "新会话"
            data_array.append(
                {
                    "id": session.session_id,
                    "model": session.model_name,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "message_count": len(session.messages),
                    "first_user_message": first_msg,
                }
            )

    return standard_response(True, "get session lists success", data_array)


@app.get("/api/models")
async def get_model_lists():
    """处理获取可用模型列表请求"""
    models = sdk_instance.get_available_models()
    data_array = [{"name": m.model_name, "desc": m.model_desc} for m in models]
    return standard_response(True, "get model lists success", data_array)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """处理删除会话请求"""
    ret = await sdk_instance.delete_session(session_id)
    if ret:
        return standard_response(True, "delete session success")
    else:
        return standard_response(
            False, "delete session failed, session not found", status_code=404
        )


@app.get("/api/session/{session_id}/history")
async def get_history_messages(session_id: str):
    """处理获取历史消息请求"""
    session = await sdk_instance.get_session(session_id)
    if not session:
        return standard_response(False, "session not found", status_code=404)

    data_array = [
        {
            "id": msg.message_id,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp,
        }
        for msg in session.messages
    ]

    return standard_response(True, "get history messages success", data_array)


@app.post("/api/message")
async def send_message_full(req: SendMessageReq):
    """处理发送消息请求 - 全量返回"""
    response_text = await sdk_instance.send_message(req.session_id, req.message)
    if not response_text:
        return standard_response(
            False, "Failed to send AI response message", status_code=500
        )

    return standard_response(
        True,
        "send message success",
        {"session_id": req.session_id, "response": response_text},
    )


@app.post("/api/message/async")
async def send_message_stream(req: SendMessageReq):
    """
    处理发送消息请求 - 增量返回
    """

    async def event_generator():
        # json.dumps 替代了 C++ 的 Json::valueToQuotedString，确保 \n 被安全转义为 "\\n"
        yield f"data: {json.dumps('', ensure_ascii=False)}\n\n"

        try:
            # 遍历底层的 AsyncGenerator
            async for chunk in sdk_instance.send_message_stream(
                req.session_id, req.message
            ):
                if chunk:
                    # 遵循 SSE 协议格式：data: "文本内容"\n\n
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # 流结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            log.error(f"Streaming Error: {e}")
            yield f"data: {json.dumps('[ERROR] Stream Failed', ensure_ascii=False)}\n\n"

    # StreamingResponse 会自动设置 Transfer-Encoding: chunked
    # 只需设置 media_type 即可
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# 挂载前端静态资源 (必须放在最后面，防止拦截 /api 路由)
# 如果根目录下有 www 文件夹，则开启
if os.path.exists("./www"):
    app.mount("/", StaticFiles(directory="./www", html=True), name="static")
    log.info("ChatServer: 已挂载 ./www 静态资源目录到根路径 /")
