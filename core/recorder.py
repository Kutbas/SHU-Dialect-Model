import audioop
import math
import time
import threading
from abc import abstractmethod
from queue import Queue

from asr.ali_nls import ALiNls
from asr.xunfei import XunFeiDialectASR
from asr.funasr import FunASR
from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import util
from utils import config_util as cfg
import numpy as np
import tempfile
import wave
from core import fay_core
from core import interact

# 麦克风启动时间 (秒)
_ATTACK = 0.1

# 麦克风释放时间 (秒)
_RELEASE = 4


class Recorder:

    def __init__(self, fay):
        self.__fay = fay
        self.__running = True
        self.__processing = False
        self.__history_level = []
        self.__history_data = []
        self.__dynamic_threshold = 0.5  # 声音识别的音量阈值

        self.__MAX_LEVEL = 25000
        self.__MAX_BLOCK = 100
        self.ASRMode = cfg.ASR_mode
        self.__aLiNls = None
        self.is_awake = False
        self.wakeup_matched = False
        if cfg.config['source']['wake_word_enabled']:
            self.timer = threading.Timer(60, self.reset_wakeup_status)  # 60秒后执行reset_wakeup_status方法
        self.username = 'User'  # 默认用户，子类实现时会重写
        self.channels = 1
        self.sample_rate = 16000
        self.is_reading = False
        self.stream = None

        self.__last_ws_notify_time = 0
        self.__ws_notify_interval = 0.5  # 最小通知间隔（秒）
        self.__ws_notify_thread = None

    # 新增上海话
    def asrclient(self):
        from utils import config_util as cfg  # 新增导入
        current_asr_mode = cfg.ASR_mode  # 直接读取当前配置
        if current_asr_mode == "ali":
            asrcli = ALiNls(self.username)
        elif current_asr_mode == "xunfei":
            asrcli = XunFeiDialectASR(self.username)
        elif current_asr_mode == "funasr" or current_asr_mode == "sensevoice":
            asrcli = FunASR(self.username)
        elif current_asr_mode == "huyu":
            from asr.huyu import HuYuASR
            asrcli = HuYuASR(self.username)
        return asrcli

    def save_buffer_to_file(self, buffer):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir="cache_data")
        wf = wave.open(temp_file.name, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(buffer)
        wf.close()
        return temp_file.name

    def __get_history_average(self, number):
        total = 0
        num = 0
        for i in range(len(self.__history_level) - 1, -1, -1):
            level = self.__history_level[i]
            total += level
            num += 1
            if num >= number:
                break
        return total / num

    def __get_history_percentage(self, number):
        return (self.__get_history_average(number) / self.__MAX_LEVEL) * 1.05 + 0.02

    def reset_wakeup_status(self):
        self.wakeup_matched = False
        with fay_core.auto_play_lock:
            fay_core.can_auto_play = True

    def __waitingResult(self, iat: object, audio_data):
        self.processing = True
        t = time.time()
        tm = time.time()
        if self.ASRMode == "funasr" or self.ASRMode == "sensevoice":
            file_url = self.save_buffer_to_file(audio_data)
            self.__aLiNls.send_url(file_url)
        elif self.ASRMode == "xunfei":
            self.__aLiNls.send_audio(
                self.__process_audio_data(audio_data, self.channels).tobytes(),
                is_last_chunk=False
            )
        elif self.ASRMode == "huyu":
            # 新增：huyu 模型，保存音频文件后调用 recognize 进行识别
            file_url = self.save_buffer_to_file(audio_data)
            self.__aLiNls.recognize(file_url)

        # 等待结果返回
        while not iat.done and time.time() - t < 1:
            time.sleep(0.01)
        text = iat.finalResults
        util.printInfo(1, self.username, "语音处理完成！ 耗时: {} ms".format(math.floor((time.time() - tm) * 1000)))
        if len(text) > 0:
            if cfg.config['source']['wake_word_enabled']:
                # 普通唤醒模式
                if cfg.config['source']['wake_word_type'] == 'common':
                    if not self.wakeup_matched:
                        # 唤醒词判断
                        wake_word = cfg.config['source']['wake_word']
                        wake_word_list = wake_word.split(',')
                        wake_up = False
                        for word in wake_word_list:
                            if word in text:
                                wake_up = True
                        if wake_up:
                            util.printInfo(1, self.username, "唤醒成功！")
                            if wsa_server.get_web_instance().is_connected(self.username):
                                wsa_server.get_web_instance().add_cmd(
                                    {"panelMsg": "唤醒成功！", "Username": self.username,
                                     'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'})
                            if wsa_server.get_instance().is_connected(self.username):
                                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "唤醒成功！"},
                                           'Username': self.username,
                                           'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'}
                                wsa_server.get_instance().add_cmd(content)
                            self.wakeup_matched = True  # 唤醒成功
                            with fay_core.auto_play_lock:
                                fay_core.can_auto_play = False
                            intt = interact.Interact("auto_play", 2, {'user': self.username, 'text': "在呢，你说？"})
                            self.__fay.on_interact(intt)
                            self.processing = False
                            self.timer.cancel()  # 取消之前的计时器任务
                        else:
                            util.printInfo(1, self.username, "[!] 待唤醒！")
                            if wsa_server.get_web_instance().is_connected(self.username):
                                wsa_server.get_web_instance().add_cmd(
                                    {"panelMsg": "[!] 待唤醒！", "Username": self.username,
                                     'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'})
                            if wsa_server.get_instance().is_connected(self.username):
                                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "[!] 待唤醒！"},
                                           'Username': self.username,
                                           'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'}
                                wsa_server.get_instance().add_cmd(content)
                    else:
                        # 创建 Interact 实例
                        self.on_speaking(text)
                        self.processing = False
                        self.timer.cancel()  # 取消之前的计时器任务
                        self.timer = threading.Timer(60, self.reset_wakeup_status)  # 重设计时器为60秒
                        self.timer.start()
                # 前置唤醒词模式
                elif cfg.config['source']['wake_word_type'] == 'front':
                    wake_word = cfg.config['source']['wake_word']
                    wake_word_list = wake_word.split(',')
                    wake_up = False
                    for word in wake_word_list:
                        if text.startswith(word):
                            wake_up_word = word
                            wake_up = True
                            break
                    if wake_up:
                        util.printInfo(1, self.username, "唤醒成功！")
                        if wsa_server.get_web_instance().is_connected(self.username):
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "唤醒成功！", "Username": self.username,
                                                                   'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'})
                        if wsa_server.get_instance().is_connected(self.username):
                            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "唤醒成功！"},
                                       'Username': self.username,
                                       'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'}
                            wsa_server.get_instance().add_cmd(content)
                        question = text  # 可在这里去除唤醒词
                        self.__fay.sound_query = Queue()
                        time.sleep(0.3)
                        # 创建 Interact 实例
                        self.on_speaking(question)
                        self.processing = False
                    else:
                        util.printInfo(1, self.username, "[!] 待唤醒！")
                        if wsa_server.get_web_instance().is_connected(self.username):
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "[!] 待唤醒！", "Username": self.username,
                                                                   'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'})
                        if wsa_server.get_instance().is_connected(self.username):
                            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "[!] 待唤醒！"},
                                       'Username': self.username,
                                       'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'}
                            wsa_server.get_instance().add_cmd(content)
            # 非唤醒模式
            else:
                # 创建 Interact 实例
                self.on_speaking(text)
                self.processing = False
        else:
            self.processing = False
            util.printInfo(1, self.username, "[!] 语音未检测到内容！")
            self.dynamic_threshold = self.__get_history_percentage(30)
            if wsa_server.get_web_instance().is_connected(self.username):
                wsa_server.get_web_instance().add_cmd(
                    {"panelMsg": "", 'Username': self.username, 'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'})
            if wsa_server.get_instance().is_connected(self.username):
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}, 'Username': self.username,
                           'robot': f'http://{cfg.fay_url}:5000/robot/Normal.jpg'}
                wsa_server.get_instance().add_cmd(content)

    def __record(self):
        try:
            stream = self.get_stream()
        except Exception as e:
            print(e)
            util.printInfo(1, self.username, "请检查设备是否有误，再重新启动!")
            return
        isSpeaking = False
        last_mute_time = time.time()
        last_speaking_time = time.time()
        data = None
        concatenated_audio = bytearray()
        audio_data_list = []
        
        # 添加当前ASR模式缓存
        current_asr_mode = cfg.ASR_mode
        
        while self.__running:
            try:
                cfg.load_config()
                # 检查ASR模式是否变化
                if cfg.ASR_mode != current_asr_mode:
                    current_asr_mode = cfg.ASR_mode
                    self.reload_asr_client()
                    util.printInfo(1, self.username, f"ASR模式已切换为{current_asr_mode}")
                
                record = cfg.config['source']['record']
                if not record['enabled'] and not self.is_remote():
                    time.sleep(1)
                    continue
                self.is_reading = True
                data = stream.read(1024, exception_on_overflow=False)
                self.is_reading = False
            except Exception as e:
                data = None
                print(e)
                util.log(1, "请检查录音设备是否有误，再重新启动!")
                self.__running = False
            if not data:
                continue
                # 是否可以拾音,不可以就掉弃录音
            can_listen = True
            if cfg.config['source']['wake_word_enabled'] == False and self.__fay.speaking == True:
                can_listen = False
            if cfg.config['source']['wake_word_enabled'] == True and cfg.config['source'][
                'wake_word_type'] == 'common' and self.wakeup_matched == True and self.__fay.speaking == True:
                can_listen = False

            if can_listen == False:
                data = None
                continue

            level = audioop.rms(data, 2)
            if len(self.__history_data) >= 10:
                self.__history_data.pop(0)
            if len(self.__history_level) >= 500:
                self.__history_level.pop(0)
            self.__history_data.append(data)
            self.__history_level.append(level)
            percentage = level / self.__MAX_LEVEL
            history_percentage = self.__get_history_percentage(30)
            if history_percentage > self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 0.0025
            elif history_percentage < self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 1

            try:
                if percentage > self.__dynamic_threshold:
                    last_speaking_time = time.time()
                    if not self.__processing and not isSpeaking and time.time() - last_mute_time > _ATTACK:
                        isSpeaking = True  # 用户正在说话
                        util.printInfo(1, self.username, "聆听中...")
                        self.__notify_listening_status()
                        concatenated_audio.clear()
                        # 识别
                        self.__aLiNls = self.asrclient()
                        task_id = self.__aLiNls.start()
                        for i in range(len(self.__history_data) - 1):
                            buf = self.__history_data[i]
                            audio_data_list.append(self.__process_audio_data(buf, self.channels))
                            if self.ASRMode == "ali":
                                self.__aLiNls.send(self.__process_audio_data(buf, self.channels).tobytes())
                            elif self.ASRMode == "xunfei":
                                self.__aLiNls.send_audio(
                                    self.__process_audio_data(data, self.channels).tobytes(),
                                    is_last_chunk=False
                                )
                            else:
                                concatenated_audio.extend(self.__process_audio_data(buf, self.channels).tobytes())
                        self.__history_data.clear()
                else:
                    last_mute_time = time.time()
                    if isSpeaking:
                        if time.time() - last_speaking_time > _RELEASE:
                            isSpeaking = False
                            if self.ASRMode == "xunfei":
                                if not self.__aLiNls.done:
                                    self.__aLiNls.send_audio(b'', is_last_chunk=True)
                                    self.__aLiNls.end()
                            if self.ASRMode == "ali":
                                self.__aLiNls.end()
                            util.printInfo(1, self.username, "语音处理中...")
                            mono_data = self.__concatenate_audio_data(audio_data_list)
                            # __waitingResult 识别语音并返回识别文本
                            self.__waitingResult(self.__aLiNls, mono_data)
                            self.__save_audio_to_wav(mono_data, self.sample_rate, "cache_data/input.wav")
                            audio_data_list = []

                if isSpeaking:
                    audio_data_list.append(self.__process_audio_data(data, self.channels))
                    if self.ASRMode == "ali":
                        self.__aLiNls.send(self.__process_audio_data(data, self.channels).tobytes())
                    if self.ASRMode == "xunfei":
                        self.__aLiNls.send_audio(
                            self.__process_audio_data(data, self.channels).tobytes(),
                            is_last_chunk=False
                        )
                    else:
                        concatenated_audio.extend(self.__process_audio_data(data, self.channels).tobytes())
            except Exception as e:
                util.printInfo(1, self.username, "录音失败: " + str(e))

    # 异步发送 WebSocket 通知
    def __notify_listening_status(self):
        current_time = time.time()
        if current_time - self.__last_ws_notify_time < self.__ws_notify_interval:
            return

        def send_ws_notification():
            try:
                if wsa_server.get_web_instance().is_connected(self.username):
                    wsa_server.get_web_instance().add_cmd({
                        "panelMsg": "聆听中...",
                        'Username': self.username,
                        'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'
                    })
                if wsa_server.get_instance().is_connected(self.username):
                    content = {
                        'Topic': 'Unreal',
                        'Data': {'Key': 'log', 'Value': "聆听中..."},
                        'Username': self.username,
                        'robot': f'http://{cfg.fay_url}:5000/robot/Listening.jpg'
                    }
                    wsa_server.get_instance().add_cmd(content)
            except Exception as e:
                util.log(1, f"发送 WebSocket 通知失败: {e}")

        if self.__ws_notify_thread is None or not self.__ws_notify_thread.is_alive():
            self.__ws_notify_thread = threading.Thread(target=send_ws_notification)
            self.__ws_notify_thread.daemon = True
            self.__ws_notify_thread.start()
            self.__last_ws_notify_time = current_time

    def __save_audio_to_wav(self, data, sample_rate, filename):
        if data.dtype != np.int16:
            data = data.astype(np.int16)
        with wave.open(filename, 'wb') as wf:
            n_channels = 1
            sampwidth = 2
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)
            wf.writeframes(data.tobytes())

    def __concatenate_audio_data(self, audio_data_list):
        data = np.concatenate(audio_data_list)
        return data

    def __process_audio_data(self, data, channels):
        data = bytearray(data)
        data = np.frombuffer(data, dtype=np.int16)
        data = np.reshape(data, (-1, channels))
        mono_data = np.mean(data, axis=1).astype(np.int16)
        return mono_data

    def set_processing(self, processing):
        self.__processing = processing

    def start(self):
        MyThread(target=self.__record).start()

    def stop(self):
        self.__running = False

    @abstractmethod
    def on_speaking(self, text):
        pass

    @abstractmethod
    def get_stream(self):
        pass

    @abstractmethod
    def is_remote(self):
        pass

    def reload_asr_client(self):
        """重新加载ASR客户端"""
        if self.__aLiNls is not None:
            try:
                self.__aLiNls.close()  # 关闭现有连接
            except:
                pass
        self.ASRMode = cfg.ASR_mode  # 更新当前ASR模式
        self.__aLiNls = self.asrclient()  # 重新创建ASR客户端
