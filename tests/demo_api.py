import os
import requests
from gradio_client import Client

"""
本文件提供了一个简单的测试脚本，演示如何直接调用后端的 TTS 和 ASR 接口，以及如何通过小沪平台进行文本和语音交互
在运行代码前先安装必要的库: pip install requests gradio-client
"""


# TTS 语音合成接口
class TTSClient:
    def __init__(self, api_base="http://202.120.117.242:23456"):
        self.api_base = api_base
        self.model = "mix_G_71000.pth"

    def generate_audio(
        self, text: str, speaker: str = "ddm", save_path: str = "tts_output.wav"
    ):
        """
        调用 TTS 接口生成语音
        :param text: 需要合成的文本
        :param speaker: 发音人，"ddm" (女声) 或 "jjp" (男声)，请确保后端支持该标识
        :param save_path: 音频保存到本地的路径
        :return: 音频文件的 URL
        """
        print(f"[TTS] 正在为文本合成语音 (发音人: {speaker})...")
        payload = {
            "fn_index": 7,
            "data": [
                text,
                self.model,
                speaker,
                "ZH",
                0.2,
                0.6,
                0.8,
                1.0,
                True,
                "Neutral",
            ],
        }

        try:
            response = requests.post(
                f"{self.api_base}/run/predict", json=payload, timeout=60
            )
            response.raise_for_status()
            result = response.json()

            data_list = result.get("data", [])
            if data_list:
                item = data_list[0]
                path = item.get("name") if isinstance(item, dict) else item
                audio_url = f"{self.api_base}/file={path}"
                print(f"[TTS] 合成成功！音频地址: {audio_url}")

                # 下载到本地
                audio_data = requests.get(audio_url).content
                with open(save_path, "wb") as f:
                    f.write(audio_data)
                print(f"[TTS] 音频已保存至: {save_path}")
                return audio_url
        except Exception as e:
            print(f"[TTS] 合成失败: {e}")
        return None


# ASR 语音识别接口
class ASRClient:
    def __init__(self, url="http://202.120.117.242:7860/"):
        print(f"[ASR] 正在初始化 ASR 客户端 (首次初始化可能稍慢)...")
        # 直接使用原生的 Gradio Client
        self.client = Client(url)
        print("[ASR] 客户端初始化完成！")

    def recognize(self, audio_path: str) -> str:
        """
        调用 ShanghaiASR 识别本地音频文件
        :param audio_path: 本地音频文件路径
        :return: 识别出的文本
        """
        if not os.path.exists(audio_path):
            print(f"[ASR] 错误: 找不到音频文件 {audio_path}")
            return ""

        print(f"[ASR] 正在识别音频文件: {audio_path} ...")
        try:
            # 调用原本的模型参数
            result = self.client.predict(
                audio_path, "test12", "auto", False, True, fn_index=3
            )
            recognized_text = result[1]
            print(f"[ASR] 识别结果: {recognized_text}")
            return recognized_text
        except Exception as e:
            print(f"[ASR] 识别发生错误: {e}")
            return ""


# 小沪交互接口 (文本/语音双链路)
class XiaoHuPlatformClient:
    def __init__(
        self,
        base_url="https://sdxcb.top:60310",
        session_id="session_1774672642_199d37f6",
    ):
        self.base_url = base_url
        self.session_id = session_id

    def chat_text(self, text: str):
        """
        小沪交互 (文本输入 -> 文本+语音输出)
        """
        print(f"\n[XiaoHu] User (文本输入): {text}")
        url = f"{self.base_url}/api/message"
        payload = {"session_id": self.session_id, "message": text}

        try:
            # 这里超时时间设置较长，因为包含了大模型推理和TTS合成的双重时间
            response = requests.post(url, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                reply_text = data["data"]["response"]
                audio_url = data["data"].get("audio_url")

                print(f"[XiaoHu] AI 回复文本: {reply_text}")
                if audio_url:
                    print(f"[XiaoHu] AI 回复语音 (TTS链接): {audio_url}")
                return reply_text, audio_url
            else:
                print(f"[XiaoHu] 请求失败: {data.get('message')}")
        except Exception as e:
            print(f"[XiaoHu] 网络或服务器错误: {e}")

        return None, None

    def chat_voice(self, audio_path: str):
        """
        小沪交互 (语音输入 -> 文本+语音输出)
        实际上是将音频先发给平台识别，再自动进行聊天
        """
        print(f"\n[XiaoHu] User (语音输入): 准备上传 {audio_path}")
        if not os.path.exists(audio_path):
            print(f"[XiaoHu] 错误: 找不到音频文件 {audio_path}")
            return None, None

        recognize_url = f"{self.base_url}/api/audio/recognize"

        try:
            # 语音转文字
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
                data = {"asr_model": "shanghai"}  # 指定使用上海话识别引擎

                response = requests.post(
                    recognize_url, files=files, data=data, timeout=60
                )
                response.raise_for_status()
                res_json = response.json()

            if res_json.get("success"):
                recognized_text = res_json["data"]["text"]
                # 清洗返回文本中的 "上海话：" 前缀
                if "上海话：" in recognized_text:
                    recognized_text = (
                        recognized_text.split("普通话：")[0]
                        .replace("上海话：", "")
                        .strip()
                    )

                print(f"[XiaoHu] 平台 ASR 识别结果: {recognized_text}")

                # 拿着文字去和小沪聊天
                return self.chat_text(recognized_text)
            else:
                print(f"[XiaoHu] 语音识别失败: {res_json.get('message')}")

        except Exception as e:
            print(f"[XiaoHu] 语音上传或识别出错: {e}")

        return None, None


# 测试入口
if __name__ == "__main__":

    # 【请在此处填入用于测试的本地音频文件路径】
    # 比如自己录制一段 wav 或 mp3 用于测试
    TEST_AUDIO_FILE = "demo.wav"

    # 样例 1: 直接调用 TTS
    print("\n" + "=" * 40 + "\n样例 1: 原生 TTS 接口调用\n" + "=" * 40)
    tts_client = TTSClient()
    tts_client.generate_audio(
        "你好，我是直接调用的语音合成系统，这段音频将直接用于ASR测试",
        speaker="jjp",
        save_path="demo.wav",
    )

    # 样例 2: 直接调用 ASR
    print("\n" + "=" * 40 + "\n样例 2: 原生 ASR 接口调用\n" + "=" * 40)
    if os.path.exists(TEST_AUDIO_FILE):
        asr_client = ASRClient()
        asr_client.recognize(TEST_AUDIO_FILE)
    else:
        print(f"跳过 ASR 测试: 未找到本地音频 {TEST_AUDIO_FILE}")

    # 样例 3: 小沪交互 (文本输入)
    print("\n" + "=" * 40 + "\n样例 3: 小沪平台 文本交互\n" + "=" * 40)
    xiaohu_platform = XiaoHuPlatformClient()
    xiaohu_platform.chat_text("你好小沪，给我介绍一下上海的南京路步行街。")

    # 样例 4: 小沪交互 (语音输入)
    print("\n" + "=" * 40 + "\n样例 4: 小沪平台 语音交互\n" + "=" * 40)
    if os.path.exists(TEST_AUDIO_FILE):
        xiaohu_platform.chat_voice(TEST_AUDIO_FILE)
    else:
        print(f"跳过小沪语音交互测试: 未找到本地音频 {TEST_AUDIO_FILE}")
