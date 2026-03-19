import requests
import time
import wave
import os
from pydub import AudioSegment
from utils import util, config_util
from utils import config_util as cfg
import shutil
from gradio_client import Client

# 添加全局变量
GLOBAL_SPEAKER_ID = 0  # 默认为女声
GLOBAL_SDP_RATIO = 0.2
GLOBAL_LENGTH = 1.0  # length>1会慢，<1会快
GLOBAL_SEGMENT_SIZE = 50

# 全局复用 Client，避免每次调用都重新建立连接
# 请将 URL 替换为你实际的新 FastAPI/Gradio 地址
GRADIO_URL = "http://202.120.117.242:23456/"
BASE_URL = "http://202.120.117.242:23456"
# Gradio 的标准预测接口通常是 /run/predict 或 /api/predict
# 如果 /run/predict 报错 404，请尝试改为 /api/predict
PREDICT_API = f"{BASE_URL}/run/predict"

try:
    util.log(1, f"正在连接语音服务 {GRADIO_URL} ...")
    tts_client = Client(GRADIO_URL)
    util.log(1, "连接语音服务成功")
except Exception as e:
    print(f"警告: 连接语音服务失败: {e}")
    tts_client = None


class Speech:
    def __init__(self):
        self.__history_data = []
        # 使用全局变量而不是实例变量

    def connect(self):
        # 如果需要鉴权/初始化，这里写逻辑；否则保留空方法
        pass

    def close(self):
        # 如果需要销毁/收尾，这里写逻辑；否则保留空方法
        pass

    def __get_history(self, voice_name, style, text):
        for data in self.__history_data:
            if data[0] == voice_name and data[1] == style and data[2] == text:
                return data[3]
        return None

    def to_sample(self, text, style):
        """
        使用 requests 直接调用 Gradio 接口 (fn_index=7)
        完全避开 gradio_client 和 WebSocket 问题
        """
        try:
            # 1. 查历史缓存 (保持原有逻辑)
            # voice_name = config_util.config["attribute"]["voice"]
            # history = self.__get_history(voice_name, style, text)
            # if history is not None:
            #     return history

            # -------------------------------
            # 2. 准备参数
            # 引用全局变量
            global GLOBAL_SPEAKER_ID, GLOBAL_SDP_RATIO, GLOBAL_LENGTH

            # 参数清洗与映射
            input_text = text
            model_name = "mix_G_71000.pth"  # 必填：需与网页下拉框一致，若只有一个模型通常填 "Default"
            speaker_name = "jjp"  # 必填：转为字符串，如 "0"
            language = "ZH"
            sdp_ratio = float(GLOBAL_SDP_RATIO)
            noise = 0.6
            noisew = 0.8
            speed = float(GLOBAL_LENGTH)
            auto_split = True
            emotion = style if style else "Neutral"  # 必填：情感

            util.log(
                0, f"正在请求: {input_text} | 角色: {speaker_name} | 情感: {emotion}"
            )

            # -------------------------------
            # 3. 构造 Payload (对应 fn_index=7 的参数顺序)
            # 根据 view_api 输出：
            # [文本, 模型, 说话人, 语言, sdp, noise, noisew, 语速, 切分, 情感]
            payload = {
                "fn_index": 7,  # ★ 核心：指定调用第7号接口
                "data": [
                    input_text,  # 0. 输入文本
                    model_name,  # 1. 选择模型
                    speaker_name,  # 2. 选择说话人
                    language,  # 3. 语言
                    sdp_ratio,  # 4. sdp
                    noise,  # 5. noise
                    noisew,  # 6. noisew
                    speed,  # 7. 语速
                    auto_split,  # 8. 自动切分
                    emotion,  # 9. 情感
                ],
            }

            # -------------------------------
            # 4. 发送 POST 请求
            # 设置超时时间，避免卡死
            response = requests.post(PREDICT_API, json=payload, timeout=60)

            if response.status_code != 200:
                util.log(1, f"[x] 接口调用失败: {response.status_code}")
                util.log(1, f"[x] 返回内容: {response.text}")
                return None

            # -------------------------------
            # 5. 解析返回结果
            # 成功响应通常是: {"data": [{"name": "/tmp/...", ...}, "Success"], ...}
            resp_json = response.json()

            if "data" not in resp_json:
                util.log(1, "[x] 返回数据格式异常")
                return None

            audio_data = resp_json["data"][0]  # 第一个返回值是音频信息

            # 获取文件名
            # 有时候返回是字符串路径，有时候是字典对象
            server_file_path = None
            if isinstance(audio_data, dict) and "name" in audio_data:
                server_file_path = audio_data["name"]
            elif isinstance(audio_data, str):
                server_file_path = audio_data

            if not server_file_path:
                util.log(1, f"[x] 未找到音频文件路径: {audio_data}")
                return None

            # -------------------------------
            # 6. 下载音频文件
            # Gradio 的文件下载地址通常是 /file=<path>
            download_url = f"{BASE_URL}/file={server_file_path}"

            # 本地临时保存
            temp_file = f"./samples/tmp-{int(time.time()*1000)}.wav"

            # 下载流
            with requests.get(download_url, stream=True) as r:
                if r.status_code == 200:
                    with open(temp_file, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    util.log(1, f"[x] 音频下载失败: {r.status_code}")
                    return None

            # -------------------------------
            # 7. 格式转换 (转为 16k)
            final_file_url = f"./samples/sample-{int(time.time() * 1000)}.wav"

            sound = AudioSegment.from_wav(temp_file)  # Gradio 通常返回 wav
            sound_16k = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            sound_16k.export(final_file_url, format="wav")

            # 删除临时下载的文件
            if os.path.exists(temp_file):
                os.remove(temp_file)

            return final_file_url

        except Exception as e:
            util.log(1, "[x] 语音转换异常！")
            util.log(1, f"[x] 原因: {str(e)}")
            return None
