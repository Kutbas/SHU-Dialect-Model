import os
import asyncio
import traceback
from gradio_client import Client
from app.core.logger import log

# 强制将 ASR 服务器 IP 加入直连白名单，禁止它走全局 SOCKS 代理
os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",202.120.117.242"
os.environ["no_proxy"] = os.environ.get("no_proxy", "") + ",202.120.117.242"

class ShanghaiASR:
    def __init__(self, url="http://202.120.117.242:7860/"):
        self.url = url
        self.client = None
        log.info(f"ASR: 准备连接到 ASR 服务: {self.url} ...")

    def init_client_sync(self):
        """同步初始化 Client，为了不阻塞主线程，我们将在后台调用它"""
        if self.client is None:
            try:
                # gradio_client 的初始化会发起网络请求，所以需要捕获异常
                self.client = Client(self.url)
                log.info("ASR: 客户端连接成功！")
            except Exception as e:
                log.error(f"ASR: 初始化客户端失败: {e}")

    def _recognize_sync(
        self,
        audio_path: str,
        model: str,
        dialect: str,
        use_kaldi: bool,
        use_punctuation: bool,
    ) -> str:
        """核心同步识别逻辑"""
        self.init_client_sync()
        if not self.client:
            return "内部错误: ASR 客户端未初始化"

        if not os.path.exists(audio_path):
            log.error(f"找不到音频文件: {audio_path}")
            return ""

        try:
            log.info(f"ASR: 正在提交音频文件 [{audio_path}] 进行识别...")
            result = self.client.predict(
                audio_path, model, dialect, use_kaldi, use_punctuation, fn_index=3
            )
            # 纯文本结果在索引 1
            recognized_text = result[1]
            log.info(f"ASR: 识别成功 -> {recognized_text}")
            return recognized_text
        except Exception as e:
            error_details = traceback.format_exc()
            log.error(f"ASR: 识别请求发生错误:\n{error_details}")
            return ""

    async def recognize_audio(
        self,
        audio_path: str,
        model="test12",
        dialect="auto",
        use_kaldi=False,
        use_punctuation=True,
    ) -> str:
        """
        供 FastAPI 调用的异步接口。
        使用 asyncio.to_thread 防止 gradio_client 的同步网络请求卡死整个并发服务器。
        """
        return await asyncio.to_thread(
            self._recognize_sync, audio_path, model, dialect, use_kaldi, use_punctuation
        )
