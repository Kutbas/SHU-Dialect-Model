import requests
import time
import wave
import os
from pydub import AudioSegment
from utils import util, config_util
from utils import config_util as cfg

# 添加全局变量
GLOBAL_SPEAKER_ID = 0  # 默认为女声
GLOBAL_SDP_RATIO = 0.2
GLOBAL_LENGTH = 1.0 # length>1会慢，<1会快
GLOBAL_SEGMENT_SIZE= 50
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
        仿照 ali_tss.py:
         1. 查历史缓存
         2. 组织 URL + 参数
         3. 发起请求获取音频
         4. 如有必要，用pydub转换成16k WAV
         5. 保存文件 & 记录缓存
        """
        try:
            # -------------------------------
            # 1. 查历史缓存
            # voice_name = config_util.config["attribute"]["voice"]
            # history = self.__get_history(voice_name, style, text)
            # if history is not None:
            #     return history

            # -------------------------------
            # 2. 组织 API 调用
            # 你的服务 API: http://202.120.117.242:23456/voice/bert-vits2?id=0&length=0.8&sdp_ratio=0.2&text=你好
            # "http://10.10.36.121:23456/"
            base_url = "http://202.120.117.242:23456/"
            # 使用全局变量而不是实例变量
            global GLOBAL_SPEAKER_ID, GLOBAL_SDP_RATIO, GLOBAL_LENGTH
            speaker_id = GLOBAL_SPEAKER_ID
            sdp_ratio = GLOBAL_SDP_RATIO
            length = GLOBAL_LENGTH
            segement_size=GLOBAL_SEGMENT_SIZE

            # 也可以把 noise/noisew/lang 等参数加进来
            # 比如:
            # &lang=auto&noise=0.33&noisew=0.4&emotion=0&style_text=Happy&style_weight=0.7
            # 这里演示把 length 带上：
            url = (f"{base_url}/voice/bert-vits2"
                   f"?id={speaker_id}"
                   f"&sdp_ratio={sdp_ratio}"
                   f"&format=wav"
                   f"&segment_size={segement_size}"
                   f"&text={text}"
                   f"&length={length}")

            # 发请求
            response = requests.get(url, stream=True)
            if response.status_code != 200:
                util.log(1, "[x] 语音转换失败！")
                util.log(1, "[x] 原因: " + response.text)
                return None

            # -------------------------------
            # 3. 先把接口返回内容存成一个临时文件
            #    VITS 通常返回 22050Hz / 24000Hz 的 wav
            temp_file = f'./samples/tmp-{int(time.time()*1000)}.wav'
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)

            # -------------------------------
            # 4. 若数字人前端只认 16k WAV，可用 pydub 转换
            file_url = f'./samples/sample-{int(time.time() * 1000)}.wav'
            sound = AudioSegment.from_wav(temp_file)

            # 强制转为 16k / 16bit / 单声道
            sound_16k = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            sound_16k.export(file_url, format="wav")

            # 删除临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)

            # -------------------------------
            # 5. 记录缓存并返回
            # self.__history_data.append((voice_name, style, text, file_url))
            return file_url

        except Exception as e:
            util.log(1, "[x] 语音转换失败！")
            util.log(1, "[x] 原因: " + str(e))
            return None
