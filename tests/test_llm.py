import os
import pytest
from app.schemas.chat import Message
from app.services.unified_llm_provider import UnifiedLLMProvider
from app.core.logger import log


# # 测试用例 1：验证 DeepSeek 全量消息发送
# @pytest.mark.asyncio
# async def test_deepseek_send_message():
#     # 实例化 UnifiedLLMProvider (指定为 DeepSeek)
#     provider = UnifiedLLMProvider(provider_type="deepseek", model_name="deepseek-chat")
#     assert provider is not None

#     # 初始化模型参数 (从环境变量获取 Key)
#     api_key = os.getenv("deepseek_apikey")
#     assert api_key is not None, "Environment variable 'deepseek_apikey' not set!"

#     model_config = {"api_key": api_key, "endpoint": "https://api.deepseek.com"}

#     # 执行初始化
#     init_ret = await provider.init_model(model_config)
#     assert init_ret is True, "Provider initialization failed"
#     # 之前把 is_available 设计成了 @property 属性，所以不带括号
#     assert provider.is_available is True

#     # 准备请求参数
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 构造消息上下文 (使用 Pydantic 模型)
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 DeepSeek 全量返回测试，如果成功请回复：DeepSeek 全量返回测试成功！",
#         )
#     ]

#     # 发送全量消息
#     response = await provider.send_message(messages, request_param)

#     # 验证响应结果
#     assert response is not None
#     assert len(response) > 0

#     # 打印结果到日志 (方便人工确认)
#     log.info(f"DeepSeek Response: {response}")


# # 测试用例 2：验证 DeepSeek 流式响应
# @pytest.mark.asyncio
# async def test_deepseek_send_message_stream():
#     # 实例化
#     provider = UnifiedLLMProvider(provider_type="deepseek", model_name="deepseek-chat")
#     assert provider is not None

#     # 初始化模型参数
#     api_key = os.getenv("deepseek_apikey")
#     assert api_key is not None, "Environment variable 'deepseek_apikey' not set!"

#     model_config = {"api_key": api_key, "endpoint": "https://api.deepseek.com"}

#     init_ret = await provider.init_model(model_config)
#     assert init_ret is True

#     # 准备请求参数
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 构造消息上下文
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 DeepSeek 流式响应测试，如果成功请回复：DeepSeek 流式响应测试成功！",
#         )
#     ]

#     # 调用流式接口并处理返回
#     full_data = ""

#     # 在 C++ 中，这里传了一个 Lambda 闭包 (auto writeChunk = [&](...))
#     # 在 Python 中，直接用 async for 遍历 provider 产出 (yield) 的数据块。
#     async for chunk in provider.send_message_stream(messages, request_param):
#         if chunk:
#             # 打印每一个接收到的数据块
#             log.info(f"chunk : {chunk}")
#             full_data += chunk  # 累积拼接完整的回复

#     # 循环结束，流式发送完毕
#     log.info("[DONE] - Stream finished.")

#     # 验证结果
#     assert len(full_data) > 0
#     log.info(f"Full Response : {full_data}")


# # 测试用例 3：验证 ChatGPT 全量返回
# @pytest.mark.asyncio
# async def test_chatgpt_send_message():
#     # 实例化 Provider
#     # 复用 UnifiedLLMProvider，只需声明类型为 openai，模型为 gpt-3.5-turbo (或 gpt-4o)
#     provider = UnifiedLLMProvider(provider_type="openai", model_name="gpt-3.5-turbo")
#     assert provider is not None

#     # 初始化配置
#     api_key = os.getenv("chatgpt_apikey")
#     assert api_key is not None, "Environment variable 'chatgpt_apikey' not set!"

#     model_param = {
#         "api_key": api_key,
#         # 对于 OpenAI，litellm 默认就知道端点是 api.openai.com，其实可以不传 endpoint。
#         "endpoint": "https://api.openai.com/v1",
#     }

#     init_ret = await provider.init_model(model_param)
#     assert init_ret is True
#     assert provider.is_available is True

#     # 构造请求参数
#     # 在 UnifiedLLMProvider 底层取的是 "max_tokens"，litellm 会自动做兼容转换
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 4. 构造消息
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 ChatGPT 全量返回测试，如果成功请回复：ChatGPT 全量返回测试成功！",
#         )
#     ]

#     # 发送请求并验证
#     full_data = await provider.send_message(messages, request_param)

#     # 确保返回不为空
#     assert full_data is not None
#     assert len(full_data) > 0

#     # 打印模型回复
#     log.info(f"ChatGPT Response: {full_data}")


# # 测试用例 4：验证 ChatGPT 流式响应
# @pytest.mark.asyncio
# async def test_chatgpt_send_message_stream():
#     # 实例化 Provider
#     provider = UnifiedLLMProvider(provider_type="openai", model_name="gpt-3.5-turbo")
#     assert provider is not None

#     # 初始化配置
#     api_key = os.getenv("chatgpt_apikey")
#     assert api_key is not None, "Environment variable 'chatgpt_apikey' not set!"

#     model_param = {"api_key": api_key, "endpoint": "https://api.openai.com/v1"}

#     init_ret = await provider.init_model(model_param)
#     assert init_ret is True

#     # 构造请求参数
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 构造消息上下文
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 ChatGPT 流式响应测试，如果成功请回复：ChatGPT 流式响应测试成功！",
#         )
#     ]

#     full_data = ""

#     # 发送流式请求
#     async for chunk in provider.send_message_stream(messages, request_param):
#         if chunk:
#             log.info(f"chunk : {chunk}")
#             full_data += chunk

#     log.info("[DONE] Stream finished.")

#     # 验证结果
#     assert len(full_data) > 0
#     log.info(f"Full Response : {full_data}")


# # 测试用例 5：验证 Gemini 全量返回
# @pytest.mark.asyncio
# async def test_gemini_send_message():
#     # 实例化 Provider
#     # 指定 provider_type 为 "gemini"，模型指定为 "gemini-1.5-pro" (或 gemini-1.5-flash)
#     provider = UnifiedLLMProvider(provider_type="gemini", model_name="gemini-2.5-flash")
#     assert provider is not None

#     # 初始化配置
#     # 从环境变量获取 Key
#     api_key = os.getenv("gemini_apikey")
#     assert api_key is not None, "Environment variable 'gemini_apikey' not set!"

#     model_param = {
#         "api_key": api_key,
#         # 在 litellm 的底层逻辑中，默认使用 Google AI Studio
#         # 如果强行传入 api_base ，litellm 会误以为试图连接企业版的 Vertex AI 节点
#         # 就会抛出 Vertex_ai_betaException (404 Not Found)
#         # 所以把 endpoint 设为空即可
#         "endpoint": "",
#     }

#     # 执行初始化
#     init_ret = await provider.init_model(model_param)
#     assert init_ret is True
#     assert provider.is_available is True

#     # 构造请求参数
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 构造消息
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 Gemini 全量返回测试，如果成功请回复：Gemini 全量返回测试成功！",
#         )
#     ]

#     # 调用全量发送接口
#     full_data = await provider.send_message(messages, request_param)

#     # 验证结果
#     assert full_data is not None
#     assert len(full_data) > 0

#     # 打印模型回复
#     log.info(f"Gemini Response: {full_data}")


# # 测试用例 6：验证 Gemini 流式响应
# @pytest.mark.asyncio
# async def test_gemini_send_message_stream():
#     # 实例化 Provider
#     provider = UnifiedLLMProvider(provider_type="gemini", model_name="gemini-2.5-flash")
#     assert provider is not None

#     # 初始化配置
#     api_key = os.getenv("gemini_apikey")
#     assert api_key is not None, "Environment variable 'gemini_apikey' not set!"

#     model_param = {
#         "api_key": api_key,
#         "endpoint": "",
#     }

#     init_ret = await provider.init_model(model_param)
#     assert init_ret is True

#     # 构造请求参数
#     request_param = {"temperature": 0.7, "max_tokens": 2048}

#     # 构造消息上下文
#     messages = [
#         Message(
#             role="user",
#             content="我现在正在进行 Gemini 流式响应测试，如果成功请回复：Gemini 流式响应测试成功！",
#         )
#     ]

#     full_data = ""

#     # 调用流式发送接口 (替代 C++ 中的 Lambda 回调)
#     async for chunk in provider.send_message_stream(messages, request_param):
#         if chunk:
#             log.info(f"chunk : {chunk}")
#             full_data += chunk

#     log.info("[DONE] Stream finished.")

#     # 验证结果
#     assert len(full_data) > 0
#     log.info(f"Gemini Full Response : {full_data}")


# 测试用例 7：验证 Ollama 全量返回
@pytest.mark.asyncio
async def test_ollama_send_message():
    # 实例化 Provider
    # 指定 provider_type 为 "ollama"，模型指定为本地的 "deepseek-r1:1.5b"
    # 模型描述也一并传入
    provider = UnifiedLLMProvider(
        provider_type="ollama",
        model_name="deepseek-r1:1.5b",
        model_desc="本地部署 deepseek-r1:1.5b 模型，采用专家混合架构，专注于深度理解与推理",
    )
    assert provider is not None

    # 初始化配置
    # Ollama 不需要 API Key，只需要配置本地或远程服务的 endpoint
    model_param = {
        "endpoint": "http://192.168.71.103:11434"  # 请确保这是实际可访问的 Ollama 地址
    }

    # 执行初始化
    init_ret = await provider.init_model(model_param)
    assert init_ret is True
    assert provider.is_available is True

    # 构造请求参数
    request_param = {"temperature": 0.7, "max_tokens": 2048}

    # 构造消息
    messages = [
        Message(
            role="user",
            content="我现在正在进行 Ollama 全量返回测试，如果成功请回复：Ollama 全量返回测试成功！",
        )
    ]

    # 调用全量发送接口
    full_data = await provider.send_message(messages, request_param)

    # 验证结果
    assert full_data is not None
    assert len(full_data) > 0

    # 打印模型回复
    log.info(f"Ollama Response: {full_data}")


# 测试用例 8：验证 Ollama 流式响应
@pytest.mark.asyncio
async def test_ollama_send_message_stream():
    # 实例化 Provider
    provider = UnifiedLLMProvider(
        provider_type="ollama",
        model_name="deepseek-r1:1.5b",
        model_desc="本地部署deepseek-r1:1.5b模型，采用专家混合架构，专注于深度理解与推理",
    )
    assert provider is not None

    # 初始化配置
    model_param = {"endpoint": "http://192.168.71.103:11434"}

    init_ret = await provider.init_model(model_param)
    assert init_ret is True

    # 构造请求参数
    request_param = {"temperature": 0.7, "max_tokens": 2048}

    # 构造消息上下文
    messages = [
        Message(
            role="user",
            content="我现在正在进行 Ollama 流式响应测试，如果成功请回复：Ollama 流式响应测试成功！",
        )
    ]

    full_data = ""

    # 调用流式发送接口
    async for chunk in provider.send_message_stream(messages, request_param):
        if chunk:
            log.info(f"chunk : {chunk}")
            full_data += chunk

    log.info("[DONE] Stream finished.")

    # 验证结果
    assert len(full_data) > 0
    log.info(f"Ollama Full Response : {full_data}")
