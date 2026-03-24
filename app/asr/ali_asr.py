import json
import time
import asyncio
import traceback
import nls
from app.core.logger import log

URL = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
APPKEY = "JwPD598XOpL98bYm"
TOKEN = "bdf7d89ea9d64cc7a5374986eb5bb207"


class AliASRTask:
    """内部工作类：由于每次识别都有状态(回调)，必须为每个请求实例化一个 Task 以保证并发安全"""

    def __init__(self, audio_path: str):
        self.audio_path = audio_path
        self.full_text = ""

    def on_sentence_end(self, message, *args):
        try:
            # 提取阿里接口返回的 JSON 结构中的识别结果
            # 格式: {"header":{"name":"SentenceEnd"},"payload":{"result":"你好"}}
            msg_dict = json.loads(message)
            text = msg_dict.get("payload", {}).get("result", "")
            if text:
                self.full_text += text
                log.info(f"AliASR 句段结果: {text}")
        except Exception as e:
            log.error(f"AliASR 解析消息失败: {e}")

    def on_error(self, message, *args):
        log.error(f"AliASR 发生错误: {message}")

    def run(self) -> str:
        """核心执行逻辑"""
        log.info(f"AliASR: 准备识别文件 {self.audio_path}")
        try:
            with open(self.audio_path, "rb") as f:
                data = f.read()

            # 初始化 NLS
            sr = nls.NlsSpeechTranscriber(
                url=URL,
                token=TOKEN,
                appkey=APPKEY,
                on_sentence_end=self.on_sentence_end,
                on_error=self.on_error,
            )

            # 启动识别，格式指定为 wav
            sr.start(
                aformat="wav",
                enable_intermediate_result=False,
                enable_punctuation_prediction=True,
                enable_inverse_text_normalization=True,
            )

            # 使用更安全的分块方式，绝不丢弃尾部音频字节！
            chunk_size = 3200  # 每次发送 3200 字节 (约 100ms 音频)
            for i in range(0, len(data), chunk_size):
                sr.send_audio(data[i:i+chunk_size])
                time.sleep(0.01)

            # 发送完成，阻塞等待最终结果返回
            sr.stop()
            log.info(f"AliASR: 识别完成 -> {self.full_text}")
            return self.full_text

        except Exception as e:
            log.error(f"AliASR 内部执行错误: {e}")
            return ""


class AliASR:
    """供 FastAPI 调用的异步对外接口"""

    async def recognize_audio(self, audio_path: str) -> str:
        try:
            task = AliASRTask(audio_path)
            # 由于 nls 是完全阻塞的同步请求，为了防止卡死主 Web 服务，放入线程池执行
            result = await asyncio.to_thread(task.run)
            return result
        except Exception as e:
            log.error(f"AliASR 调度出错: {traceback.format_exc()}")
            return ""
