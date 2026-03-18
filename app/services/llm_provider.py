from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator
from app.schemas.chat import Message  


# LLM 抽象基类
class LLMProvider(ABC):
    def __init__(self):
        # 对应 protected 成员
        self._is_available: bool = False
        self._api_key: str = ""
        self._endpoint: str = ""

    @abstractmethod
    async def init_model(self, model_config: Dict[str, Any]) -> bool:
        """初始化模型"""
        pass

    @property
    def is_available(self) -> bool:
        """检测模型是否有效，用 @property 装饰器变成属性调用"""
        return self._is_available

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass

    @abstractmethod
    def get_model_desc(self) -> str:
        """获取模型描述"""
        pass

    @abstractmethod
    async def send_message(
        self, messages: List[Message], request_param: Dict[str, Any]
    ) -> str:
        """
        发送消息 - 全量返回
        注意：在 FastAPI 中网络请求必须用 async/await，防止阻塞主线程
        """
        pass

    @abstractmethod
    async def send_message_stream(
        self, messages: List[Message], request_param: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        发送消息 - 增量返回 - 流式响应
        通过 async for chunk in provider.send_message_stream(...) 来获取数据。
        """
        pass
