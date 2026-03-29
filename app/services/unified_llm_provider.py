import litellm
from typing import List, Dict, Any, AsyncGenerator

from app.schemas.chat import Message
from app.services.llm_provider import LLMProvider
from app.core.logger import log


class UnifiedLLMProvider(LLMProvider):
    def __init__(self, provider_type: str, model_name: str, model_desc: str = ""):
        """
        :param provider_type: 提供商标识，例如 "openai", "deepseek", "gemini", "ollama"
        :param model_name: 具体的模型名，例如 "gpt-4o", "deepseek-chat", "llama3"
        """
        super().__init__()
        self._provider_type = provider_type.lower()
        self._raw_model_name = model_name
        self._model_desc = model_desc

        # litellm 路由通过 "提供商/模型名" 的格式来自动识别底层 API
        # 例如: "ollama/llama3", "gemini/gemini-1.5-pro", "deepseek/deepseek-chat"
        # OpenAI 的模型通常可以直接写 "gpt-4o"
        if self._provider_type == "openai":
            self._litellm_model = self._raw_model_name
        else:
            self._litellm_model = f"{self._provider_type}/{self._raw_model_name}"

    async def init_model(self, model_config: Dict[str, Any]) -> bool:
        """统一的初始化逻辑：无论是云端 API 还是本地 Ollama 都在这里提取配置"""
        self._api_key = model_config.get("api_key", "")

        # litellm 中自定义请求地址通常使用 api_base 参数
        self._endpoint = model_config.get("endpoint", "")

        # 简单校验：如果是云端模型，通常需要 api_key；如果是 ollama，通常需要 endpoint
        if self._provider_type != "ollama" and not self._api_key:
            log.warning(
                f"[{self._litellm_model}] Initialized without API Key. May fail if required."
            )
        if self._provider_type == "ollama" and not self._endpoint:
            log.error(
                f"[{self._litellm_model}] Ollama requires an endpoint (base_url)."
            )
            return False

        self._is_available = True
        log.info(
            f"Initialized Unified Provider: {self._litellm_model} | Endpoint: {self._endpoint}"
        )
        return True

    def get_model_name(self) -> str:
        return self._raw_model_name

    def get_model_desc(self) -> str:
        return self._model_desc

    def _format_messages(
        self, messages: List[Message], system_prompt: str = ""
    ) -> List[Dict[str, str]]:
        """辅助函数：将 Pydantic Message 对象转换为 litellm 需要的字典数组"""
        formatted = []
        # 【新增】：如果配置了系统提示词，将其作为 system 角色悄悄置于最前端
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        formatted.extend(
            [{"role": msg.role, "content": msg.content} for msg in messages]
        )
        return formatted

    async def send_message(
        self, messages: List[Message], request_param: Dict[str, Any]
    ) -> str:
        """发送消息 - 全量返回 (替代四个 Provider 中的全量发送逻辑)"""
        if not self.is_available:
            log.error(f"[{self._litellm_model}] Model not available.")
            return ""

        system_prompt = request_param.get("system_prompt", "")  # 获取系统提示词

        try:
            # 核心：acompletion 是 litellm 的异步通用接口
            # 它会自动把请求翻译成 OpenAI / Gemini / DeepSeek / Ollama 各自所需的底层格式
            response = await litellm.acompletion(
                model=self._litellm_model,
                messages=self._format_messages(messages, system_prompt),
                api_key=self._api_key if self._api_key else None,
                api_base=self._endpoint if self._endpoint else None,
                temperature=float(request_param.get("temperature", 0.7)),
                max_tokens=int(request_param.get("max_tokens", 2048)),
                stream=False,
            )

            # 无论底层是哪家大模型，litellm 都会把返回值包装成标准的 OpenAI 格式
            reply_content = response.choices[0].message.content
            log.info(f"[{self._litellm_model}] Response: {reply_content[:50]}...")
            return reply_content

        except Exception as e:
            log.error(f"[{self._litellm_model}] Request Error: {str(e)}")
            return f"Error: {str(e)}"

    async def send_message_stream(
        self, messages: List[Message], request_param: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """发送消息 - 流式返回 (完美替代那四个文件中繁琐的 SSE 解析和 Callback)"""
        if not self.is_available:
            log.error(f"[{self._litellm_model}] Model not available for streaming.")
            yield "Error: Model not available."
            return

        system_prompt = request_param.get("system_prompt", "")  # 获取系统提示词

        try:
            # 开启 stream=True
            response_stream = await litellm.acompletion(
                model=self._litellm_model,
                messages=self._format_messages(messages, system_prompt),
                api_key=self._api_key if self._api_key else None,
                api_base=self._endpoint if self._endpoint else None,
                temperature=float(request_param.get("temperature", 0.7)),
                max_tokens=int(request_param.get("max_tokens", 2048)),
                stream=True,
            )

            # 告别 C++ 的粘包、半包、正则表达式和 JSON 解析
            # litellm 已经在底层处理好了所有 SSE 规范，只需要简单迭代即可
            async for chunk in response_stream:
                # 提取增量内容
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        except Exception as e:
            log.error(f"[{self._litellm_model}] Stream Error: {str(e)}")
            yield f"\n[Stream Error: {str(e)}]"
