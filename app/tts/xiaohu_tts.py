import httpx
from typing import Optional
from app.core.logger import log
from app.core.config import settings


class XiaoHuTTS:
    def __init__(self):
        self.api_base = settings.TTS_API_BASE
        self.model = "mix_G_71000.pth"
        self.lang = "ZH"
        self.emotion = "Neutral"
        self.sdp = 0.2
        self.noise = 0.6
        self.noise_w = 0.8
        self.length_scale = 1.0  # 对应 JS 里的 1.0 / uiSpeed
        self.speaker = "ddm"

    async def generate_audio(self, text: str) -> Optional[str]:
        """调用 TTS 接口生成语音，返回音频文件的 URL"""
        if not text:
            return None

        payload = {
            "fn_index": 7,
            "data": [
                text,
                self.model,
                self.speaker,
                self.lang,
                self.sdp,
                self.noise,
                self.noise_w,
                self.length_scale,
                True,
                self.emotion,
            ],
        }

        try:
            # 语音合成可能较慢，设置 60 秒超时
            async with httpx.AsyncClient(timeout=60.0) as client:
                log.info("XiaoHuTTS: 正在向服务器请求合成语音...")
                response = await client.post(
                    f"{self.api_base}/run/predict", json=payload
                )
                response.raise_for_status()
                result = response.json()

                # 解析 Gradio API 返回的数据结构
                data_list = result.get("data", [])
                if data_list and len(data_list) > 0:
                    item = data_list[0]
                    # 有些接口返回字典 {"name": "/tmp/xx.wav"}，有些直接返回路径字符串
                    path = item.get("name") if isinstance(item, dict) else item

                    if path:
                        audio_url = f"{self.api_base}/file={path}"
                        log.info(f"XiaoHuTTS: 语音合成成功 -> {audio_url}")
                        return audio_url

        except Exception as e:
            log.error(f"XiaoHuTTS: 语音合成失败: {e}")

        return None
