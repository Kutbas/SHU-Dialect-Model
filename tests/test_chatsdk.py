import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator

from app.db.data_manager import DataManager
from app.services.session_manager import SessionManager
from app.services.llm_manager import LLMManager
from app.services.chat_sdk import ChatSDK
from app.schemas.chat import APIConfig, OllamaConfig
from app.core.logger import log

# 准备测试夹具
TEST_DB_PATH = "./test_chatsdk.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"


@pytest_asyncio.fixture
async def chat_sdk() -> AsyncGenerator[ChatSDK, None]:
    """ChatSDK 测试夹具：自动准备好 DB、SessionManager 和 LLMManager"""
    # 初始化底层数据库
    dm = DataManager(TEST_DB_URL)
    await dm.init_database()

    # 实例化两大 Manager
    sm = SessionManager(dm)
    lm = LLMManager()

    # 组装最上层的 ChatSDK
    sdk = ChatSDK(llm_manager=lm, session_manager=sm)

    yield sdk  # 将 sdk 交给测试用例

    # 测试结束后的清理工作
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


# 测试用例 1：测试 ChatSDK 的模型全量注册与发送
@pytest.mark.asyncio
async def test_chatsdk_send_message(chat_sdk: ChatSDK):
    log.info("--- 开始测试 ChatSDK 多模型注册与发送 ---")

    # 1. 准备配置列表
    configs = []

    # DeepSeek
    deepseek_key = os.getenv("deepseek_apikey")
    assert deepseek_key, "deepseek_apikey not set"
    configs.append(
        APIConfig(
            model_name="deepseek-chat",
            api_key=deepseek_key,
            temperature=0.7,
            max_tokens=2048,
        )
    )

    # ChatGPT
    chatgpt_key = os.getenv("chatgpt_apikey")
    assert chatgpt_key, "chatgpt_apikey not set"
    configs.append(
        APIConfig(
            model_name="gpt-4o-mini",
            api_key=chatgpt_key,
            temperature=0.7,
            max_tokens=2048,
        )
    )

    # Gemini
    gemini_key = os.getenv("gemini_apikey")
    assert gemini_key, "gemini_apikey not set"
    # 官方 Gemini endpoint 留空以防 Vertex AI 报错
    configs.append(
        APIConfig(
            model_name="gemini-2.5-flash",
            api_key=gemini_key,
            endpoint="",
            temperature=0.7,
            max_tokens=2048,
        )
    )

    # Ollama
    configs.append(
        OllamaConfig(
            model_name="deepseek-r1:1.5b",
            model_desc="本地部署deepseek-r1:1.5b模型，采用专家混合架构，专注于深度理解与推理",
            endpoint="http://192.168.71.103:11434",  # 替换为你的本地地址
            temperature=0.7,
            max_tokens=2048,
        )
    )

    # 初始化所有模型
    init_ret = await chat_sdk.init_models(configs)
    assert init_ret is True

    # 创建会话 (测试使用 Ollama)
    session_id = await chat_sdk.create_session("deepseek-r1:1.5b")
    assert session_id is not None

    # 模拟交互发消息
    msg1 = "测试提问第一句，请回复收到"
    log.info(f">>> User: {msg1}")
    response1 = await chat_sdk.send_message(session_id, msg1)
    assert response1 is not None and len(response1) > 0
    log.info(f">>> AI: {response1}")

    msg2 = "测试提问第二句，无需回复过多"
    log.info(f">>> User: {msg2}")
    response2 = await chat_sdk.send_message(session_id, msg2)
    assert response2 is not None and len(response2) > 0
    log.info(f">>> AI: {response2}")

    # 验证历史记录是否存入
    messages = await chat_sdk._session_manager.get_history_messages(session_id)
    assert len(messages) == 4  # (User1, AI1, User2, AI2)
    log.info("--- ChatSDK 多模型注册与发送 测试通过 ---")


# 测试用例 2：测试完整业务流与多轮上下文记忆
@pytest.mark.asyncio
async def test_chatsdk_full_integration(chat_sdk: ChatSDK):
    log.info("--- 开始测试 ChatSDK 多轮上下文记忆 ---")

    # 准备配置
    deepseek_key = os.getenv("deepseek_apikey")
    assert deepseek_key, "deepseek_apikey not set"
    configs = [
        APIConfig(model_name="deepseek-chat", api_key=deepseek_key, temperature=0.7)
    ]

    # 初始化 SDK
    init_ret = await chat_sdk.init_models(configs)
    assert init_ret is True

    # 创建会话
    session_id = await chat_sdk.create_session("deepseek-chat")
    assert session_id is not None
    log.info(f"Created session: {session_id}")

    # 发送第一条消息
    q1 = "你好，请做一个简短的自我介绍。并记住我的暗号是'天王盖地虎'。"
    log.info(f">>> User: {q1}")
    a1 = await chat_sdk.send_message(session_id, q1)
    assert a1 is not None and len(a1) > 0
    log.info(f">>> AI: {a1}")

    # 发送第二条消息 (测试上下文记忆)
    q2 = "我刚才给你的暗号是什么？"
    log.info(f">>> User: {q2}")
    a2 = await chat_sdk.send_message(session_id, q2)
    assert a2 is not None and len(a2) > 0
    log.info(f">>> AI: {a2}")

    # 确保 AI 回答了暗号
    assert "天王盖地虎" in a2

    # 验证历史记录持久化
    history = await chat_sdk._session_manager.get_history_messages(session_id)

    # 应该包含 4 条消息：User1, AI1, User2, AI2
    assert len(history) == 4

    log.info("\n=== History Dump ===")
    for msg in history:
        log.info(f"[{msg.role}] {msg.content}")

    log.info("--- ChatSDK 多轮上下文记忆 测试通过 ---")
