# xunfei_dialect.py
import websocket
import json
import time
import ssl
import wave
import _thread as thread
import hmac
import hashlib
import base64
import datetime
from threading import Thread, Lock
from utils import util
from utils import config_util as cfg
from core import wsa_server


def rfc1123_date():
    now = datetime.datetime.utcnow()
    return now.strftime('%a, %d %b %Y %H:%M:%S GMT')
def create_signature_date_host():
    """
    根据文档，生成鉴权所需的 date, host, authorization 拼接到URL上
    """
    # 1) host
    host = "iat.cn-huabei-1.xf-yun.com"  # 不带 wss:// 前缀
    # 2) date (RFC1123格式)
    date_str = rfc1123_date()
    # 3) request-line
    #   GET /v1 HTTP/1.1
    request_line = "GET /v1 HTTP/1.1"

    # 4) 拼出 signature_origin
    #   形如：
    #     host: iat.cn-huabei-1.xf-yun.com
    #     date: Tue, 14 May 2024 08:46:48 GMT
    #     GET /v1 HTTP/1.1
    signature_origin = f"host: {host}\n"
    signature_origin += f"date: {date_str}\n"
    signature_origin += request_line

    # 5) hmac-sha256签名
    api_secret = cfg.key_xf_api_secret.strip()
    api_key = cfg.key_xf_api_key.strip()
    digest = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        hashlib.sha256
    ).digest()
    # 6) 对签名结果做base64编码
    sign = base64.b64encode(digest).decode('utf-8')

    # 7) 再拼出 authorization_origin 形如：
    #   api_key="xxx", algorithm="hmac-sha256", headers="host date request-line", signature="xxxx"
    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{sign}"'
    # 8) 再对 authorization_origin 做base64
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

    return date_str, host, authorization


class XunFeiDialectASR:

    def __init__(self, username):
        self.__ws = None
        self.__frames = []
        self.username = username
        self.data = b''
        self.finalResults = ""
        self.done = False
        self.started = False
        self.__endding = False
        self.__is_close = False
        self.__closing = False
        self.lock = Lock()
        self.__seq = 0

    def __create_url(self):
        date_str, host, authorization = create_signature_date_host()
        url = f"wss://iat.cn-huabei-1.xf-yun.com/v1?" \
              f"authorization={authorization}" \
              f"&date={util.url_encode(date_str)}" \
              f"&host={host}"
        return url

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            code = data.get("header", {}).get("code", -1)
            if code != 0:
                print("XunFei ASR Error:", data.get("header", {}).get("message", ""))
                self.done = True
                ws.close()
                return

            header_status = data["header"].get("status", 1)
            payload = data.get("payload", {})
            result = payload.get("result", {})
            text_b64 = result.get("text", "")
            if text_b64:
                try:
                    text_decode = base64.b64decode(text_b64).decode('utf-8')
                    text_json = json.loads(text_decode)
                    sentence = self.__parse_text_json(text_json)  # 拼所有 cw.w 得到字符串
                except Exception as e:
                    print("parse text failed:", e)
                    sentence = ""

                # 判断是否是最终结果
                is_final = text_json.get("ls", False) or (header_status == 2)
                if is_final:
                    print(sentence)
                    self.finalResults += sentence
                    if wsa_server.get_web_instance().is_connected(self.username):
                        wsa_server.get_web_instance().add_cmd({
                            "panelMsg": self.finalResults,
                            "Username": self.username
                        })
                    if wsa_server.get_instance().is_connected(self.username):
                        content = {
                            'Topic': 'Unreal',
                            'Data': {'Key': 'log', 'Value': self.finalResults},
                            'Username': self.username
                        }
                        wsa_server.get_instance().add_cmd(content)
                    self.done = True
                    ws.close()
                else:
                    self.finalResults += sentence
                    print(sentence)
                    if wsa_server.get_web_instance().is_connected(self.username):
                        wsa_server.get_web_instance().add_cmd({
                            "panelMsg": sentence,
                            "Username": self.username
                        })
                    if wsa_server.get_instance().is_connected(self.username):
                        content = {
                            'Topic': 'Unreal',
                            'Data': {'Key': 'log', 'Value': sentence},
                            'Username': self.username
                        }
                        wsa_server.get_instance().add_cmd(content)

            # 如果 header_status == 2，但上面 text_b64 为空，也会走到这里。可再次处理:
            if header_status == 2 and not self.done:
                self.done = True
                ws.close()

        except Exception as e:
            print("on_message error:", e)
            self.done = True
            ws.close()

    def __parse_text_json(self, text_json):
        """
        解析讯飞返回的 result.text 里的 ws[] => cw[] => w
        拼成一整段文本（包含这次的增量或最终结果）
        """
        if not isinstance(text_json, dict):
            return ""
        ws_list = text_json.get("ws", [])
        sentence = ""
        for wss in ws_list:
            cw_list = wss.get("cw", [])
            for cw in cw_list:
                w = cw.get("w", "")
                sentence += w
        return sentence

    def on_error(self, ws, error):
        print("XunFei asr error:", error)
        self.started = True  # 避免阻塞

    def on_close(self, ws, code, msg):
        self.__endding = True
        self.__is_close = True

    def on_open(self, ws):
        """
        连接成功后，启动发送线程。
        """
        self.__endding = False

        def run(*args):
            while not self.__endding:
                try:
                    if len(self.__frames) > 0:
                        with self.lock:
                            frame = self.__frames.pop(0)
                        ws.send(json.dumps(frame))
                    else:
                        time.sleep(0.01)
                except Exception as e:
                    print("on_open run error:", e)
                    break

            # 还有剩余未发的帧，最后再发一次
            if not self.__is_close:
                with self.lock:
                    for f in self.__frames:
                        ws.send(json.dumps(f))
                # 也可以这里不显式再发送，因为可能end()已经把结束帧塞进去了

        thread.start_new_thread(run, ())

    def __connect(self):
        url = self.__create_url()
        self.__ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.__ws.on_open = self.on_open
        # 跟 ali_nls 一样，忽略ssl证书
        self.__ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def start(self):
        Thread(target=self.__connect).start()
        data = {
            "header": {
                "app_id": cfg.key_xf_app_id,
                "status": 0
            },
            "parameter": {
                "iat": {
                    "language": "zh_cn",  # 语种
                    "accent": "mulacc",  # 方言免切
                    "domain": "slm",  # 固定
                    # 开启流式识别
                    "dwa": "raw",
                    "ptt": 1,
                    "nunum": 1,
                    "ltc": 1,
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json"
                    }
                }
            },
            "payload": {
                "audio": {
                    "encoding": "raw",
                    "sample_rate": 16000,
                    "channels": 1,
                    "bit_depth": 16,
                    "status": 0,
                    "seq": self.__seq,
                    "audio": "" 
                }
            }
        }
        with self.lock:
            self.__frames.append(data)
        self.started = True

    def send_audio(self, buf, is_last_chunk=False):
        """
        发送音频帧。若 is_last_chunk=True 则发送 status=2。
        其他情况 status=1。
        """
        if not self.started:
            return
        audio_base64 = base64.b64encode(buf).decode('utf-8')
        self.data += buf  # 用于后面存到本地wav

        self.__seq += 1
        status_flag = 1
        if is_last_chunk:
            status_flag = 2

        frame = {
            "header": {
                "app_id": cfg.key_xf_app_id,
                "status": status_flag
            },
            "parameter": {
                "iat": {
                    "language": "zh_cn",
                    "accent": "mulacc",
                    "domain": "slm",
                    "dwa": "raw",
                    "ptt": 1,
                    "nunum": 1,
                    "ltc": 1,
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json"
                    }
                }
            },
            "payload": {
                "audio": {
                    "encoding": "raw",
                    "sample_rate": 16000,
                    "channels": 1,
                    "bit_depth": 16,
                    "status": status_flag,
                    "seq": self.__seq,
                    "audio": audio_base64
                }
            }
        }
        with self.lock:
            self.__frames.append(frame)

    def end(self):
        self.__endding = True
        # 写一个wav缓存，方便调试
        with wave.open('cache_data/xf_input.wav', 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(self.data)
        self.data = b''



__running = False
__my_thread = None


def start():
    global __running
    global __my_thread
    if __running:
        return
    __running = True


def stop():
    global __runnin
