from typing import Dict, List, Any, AsyncGenerator

from app.schemas.chat import Message, ModelInfo
from app.services.llm_provider import LLMProvider
from app.core.logger import log


class LLMManager:
    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._model_infos: Dict[str, ModelInfo] = {}

    def register_provider(self, model_name: str, provider: LLMProvider) -> bool:
        """
        注册 LLM 提供者
        C++ 中的 std::unique_ptr 和 std::move 在 Python 中自然体现为引用传递
        """
        if provider is None:
            log.error(
                f"LLMManager.register_provider: cannot register None provider, model_name = {model_name}"
            )
            return False

        # 保存 Provider 实例
        self._providers[model_name] = provider

        # 使用 Pydantic 模型初始化元数据缓存
        self._model_infos[model_name] = ModelInfo(
            model_name=model_name,
            is_available=False,  # 刚注册时，尚未初始化，默认不可用
        )

        log.info(f"LLMManager: register provider success, model_name = {model_name}")
        return True

    async def init_model(self, model_name: str, model_param: Dict[str, Any]) -> bool:
        """
        初始化指定模型
        注意：因为 Provider 的 init_model 是异步的，所以这里也要加上 async
        """
        # 查找模型是否已注册
        provider = self._providers.get(model_name)
        if not provider:
            log.error(
                f"LLMManager.init_model: model provider not found, model_name = {model_name}"
            )
            return False

        # 通过多态调用具体 Provider 的初始化逻辑
        is_success = await provider.init_model(model_param)

        # 更新元数据状态
        if not is_success:
            log.error(f"LLMManager.init_model: init failed, model_name = {model_name}")
        else:
            log.info(f"LLMManager.init_model: init success, model_name = {model_name}")
            # 更新缓存的描述信息和可用状态
            self._model_infos[model_name].model_desc = provider.get_model_desc()
            self._model_infos[model_name].is_available = True

        return is_success

    def get_available_models(self) -> List[ModelInfo]:
        """获取所有可用模型"""
        models = []
        for info in self._model_infos.values():
            if info.is_available:
                models.append(info)
        return models

    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用"""
        info = self._model_infos.get(model_name)
        return info.is_available if info else False

    async def send_message(
        self, model_name: str, messages: List[Message], request_param: Dict[str, Any]
    ) -> str:
        """发送消息给指定模型 (全量返回)"""
        provider = self._providers.get(model_name)
        if not provider:
            log.error(
                f"LLMManager.send_message: provider not found, model_name = {model_name}"
            )
            return ""

        if not provider.is_available:
            log.error(
                f"LLMManager.send_message: model not available, model_name = {model_name}"
            )
            return ""

        # 路由转发
        return await provider.send_message(messages, request_param)

    async def send_message_stream(
        self, model_name: str, messages: List[Message], request_param: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        发送消息流给指定模型 (流式响应)
        在 Python 中，路由转发流式请求只需要用 async for 接收，再用 yield 抛出去即可
        """
        provider = self._providers.get(model_name)
        if not provider:
            log.error(
                f"LLMManager.send_message_stream: provider not found, model_name = {model_name}"
            )
            yield f"Error: Provider {model_name} not found."
            return

        if not provider.is_available:
            log.error(
                f"LLMManager.send_message_stream: model not available, model_name = {model_name}"
            )
            yield f"Error: Model {model_name} not available."
            return

        # 路由转发流式数据流
        async for chunk in provider.send_message_stream(messages, request_param):
            yield chunk


# 导出全局单例 LLMManager
llm_manager = LLMManager()
