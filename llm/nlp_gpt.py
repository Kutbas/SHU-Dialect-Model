"""
此代码由 fay 开源开发者社区成员 江湖墨明 提供。
通过修改此代码，可以实现对接本地 Clash 代理或远程代理，Clash 无需设置成系统代理。
以解决在开启系统代理后无法使用部分功能的问题。
"""

import time
import json
import requests
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
import pytz

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

from utils import config_util as cfg
from utils import util
from core import content_db

def get_session():
    session = requests.Session()
    session.verify = False
    httpproxy = cfg.proxy_config
    if httpproxy:
        session.proxies = {
            "http": f"http://{httpproxy}",
            "https": f"https://{httpproxy}"
        }
    return session


def build_prompt(observation):
    person_info = cfg.config["attribute"]
    observation_text = f"以下是当前观测结果：{observation}，观测结果只供参考。" if observation else ""
    prompt=f"""
    你是一位精通上海话的专家，来自上海大学，你叫“小沪”。你的任务是与用户进行上海话的对话互动。
    用户可能会用普通话或者英文和你对话，但用户并不完全掌握上海话，因此在跟你对话时可能会使用不标准的发音或包含错别字的上海话书面表达，你需要识别他们并给出正确的回答。
    如果用户提出刁钻或不合适的问题，你可以机智地回避或幽默化解，而不直接拒绝回答。
    你的职责是：
    1、理解用户以不标准上海话或带有错别字的上海话进行的表达。
    2、使用标准、地道的上海话文字与用户进行交流，尽量展现上海话的正宗表达，除非你要背诵一首诗歌。
    3、**你的回答不需要加上“小沪：”的前缀，直接给出回复即可。**
    记住，你需要始终保持以地道的上海话进行交流，同时用温和、友好的态度帮助用户提高上海话的表达能力。
    你的名字是“小沪”，但当用户可能会叫错你的名字的时候，不需要纠正用户。
    {observation_text}
    """
    return prompt

def get_communication_history(uid=0):
    tz = pytz.timezone('Asia/Shanghai')
    thistime = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    contentdb = content_db.new_instance()
    if uid == 0:
        communication_history = contentdb.get_list('all', 'desc', 11)
    else:
        communication_history = contentdb.get_list('all', 'desc', 11, uid)
    
    messages = []
    if communication_history and len(communication_history) > 1:
        for entry in reversed(communication_history):
            role = entry[0]
            message_content = entry[2]
            if role == "member":
                messages.append({"role": "user", "content": message_content})
            elif role == "fay":
                messages.append({"role": "assistant", "content": message_content})
    print(messages)

    return messages

def send_request(session, data):
    url = cfg.gpt_base_url + "/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.key_gpt_api_key}'
    }
    try:
        response = session.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        response_text = result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        response_text = "抱歉，我现在太忙了，休息一会，请稍后再试。"
    return response_text

def question(content, uid=0, observation="用户现在在上海大学宝山校区的钱伟长图书馆的书香谷，今天是2025年3月10日，星期一，现在是下午，阴天，气温15度"):
    session = get_session()
    prompt = build_prompt(observation)
    messages = [{"role": "system", "content": prompt}]
    history_messages = get_communication_history(uid)
    messages.extend(history_messages)
    data = {
        "model": cfg.gpt_model_engine,
        "messages": messages,
        "temperature": 1.3,
        "max_tokens": 2000,
        "user": f"user_{uid}"
    }
    start_time = time.time()
    response_text = send_request(session, data)
    elapsed_time = time.time() - start_time
    util.log(1, f"接口调用耗时: {elapsed_time:.2f} 秒")
    return response_text

