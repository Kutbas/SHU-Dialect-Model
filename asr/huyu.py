import os
import time
import websocket
import requests
from utils import config_util, util
from core import wsa_server
from scheduler.thread_manager import MyThread

API_URL = "http://202.120.117.242:5000/api/asr"
API_KEY = "test_key"

def recognize_audio_file(audio_file_path, model_id="test4", dialect="auto", use_kaldi="true"):
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError("音频文件不存在: " + audio_file_path)

    with open(audio_file_path, "rb") as f:
        files = {"audio": f}
        data = {
            "model_id": model_id,
            "dialect": dialect,
            "use_kaldi": use_kaldi
        }
        headers = {"apikey": API_KEY}
        start_time = time.time()
        try:
            response = requests.post(f"{API_URL}/recognize", headers=headers, files=files, data=data)
            response.raise_for_status()
        except Exception as e:
            util.log(1, f"请求 TeleSpeech ASR API 失败: {e}")
            raise e
        result = response.json()
        if "duration" not in result:
            result["duration"] = time.time() - start_time
        return result

class HuYuASR:
    def __init__(self, username):
        self.username = username
        self.finalResults = ""
        self.done = False
        self.__endding = False
        self.__is_close = False

    def recognize(self, audio_file_path, model_id="test4", dialect="auto", use_kaldi="true"):
        try:
            util.log(1, f"开始识别音频文件: {audio_file_path}")
            result = recognize_audio_file(audio_file_path, model_id, dialect, use_kaldi)
            self.finalResults = result.get("text", "")
            self.done = True
            util.log(1, f"识别结果: {self.finalResults}")
        except Exception as e:
            util.log(1, f"HuYuASR 识别异常: {e}")
            self.finalResults = ""
            self.done = True
        finally:
            self.on_close()
    
    def start(self):
        pass

    def on_close(self):
        self.__endding = True
        self.__is_close = True
        if wsa_server.get_web_instance().is_connected(self.username):
            wsa_server.get_web_instance().add_cmd({
                "panelMsg": self.finalResults,
                "Username": self.username,
                "name": "SentenceEnd"  # 可用来标识结束事件
            })
        if wsa_server.get_instance().is_connected(self.username):
            content = {
                "Topic": "Unreal",
                "Data": {"Key": "log", "Value": self.finalResults},
                "Username": self.username,
                "name": "SentenceEnd"
            }
            wsa_server.get_instance().add_cmd(content)


def start():
    util.log(1, "HuYuASR 接口已启动")
