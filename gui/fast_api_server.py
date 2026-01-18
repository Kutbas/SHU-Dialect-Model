import json
import os
import time
import asyncio
import datetime
import pytz
import pyaudio
import logging

# FastAPI 核心组件
from fastapi import FastAPI, Depends, HTTPException, status, Form, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

# ----------------- 引入项目核心模块 -----------------
from utils import config_util, util
from core import wsa_server
from tts import tts_voice
import fay_booter
from core.interact import Interact
from core import content_db
from core import member_db
from typing import Optional

# 注意：vits 在函数内部引用，保持与原逻辑一致

# ----------------- 1. 初始化 -----------------

app = FastAPI(title="Fay Digital Human API", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模板与静态文件
templates = Jinja2Templates(directory="gui/templates")
app.mount("/static", StaticFiles(directory="gui/static"), name="static")

# 全局变量
CURRENT_VOICE_MODE = 0

# ----------------- 2. 鉴权逻辑 -----------------
# 关键修改：auto_error=False 防止浏览器直接弹窗
security = HTTPBasic(auto_error=False)


def load_users():
    try:
        if os.path.exists("verifier.json"):
            with open("verifier.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception:
        return {}


users_db = load_users()


def verify_credentials(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    """鉴权函数：兼容桌面模式和无密码访问"""
    # 桌面模式或无用户配置 -> 直接放行
    if not users_db or config_util.start_mode == "common":
        return "guest"

    # 有凭证 -> 验证
    if credentials:
        if (
            credentials.username in users_db
            and users_db[credentials.username] == credentials.password
        ):
            return credentials.username

    # 这里的逻辑是：如果 Web 模式下没传密码，也暂不拦截（模仿 Flask 旧行为）
    # 如果你想强制 Web 端登录，可以取消下面 raise 的注释
    # raise HTTPException(status_code=401, ...)
    return "guest"


# ----------------- 3. 模板兼容层 (解决 filename 报错) -----------------


def flask_compatible_url_for(request: Request, name: str, **path_params):
    """
    兼容函数：拦截模板中的 url_for 调用
    如果发现是请求 'static' 且用了 Flask 的 'filename' 参数，自动转为 'path'
    """
    if name == "static" and "filename" in path_params:
        path_params["path"] = path_params.pop("filename")
    return request.url_for(name, **path_params)


# ----------------- 4. 工具函数 -----------------


def _get_device_list():
    try:
        if config_util.start_mode == "common":
            audio = pyaudio.PyAudio()
            device_list = []
            for i in range(audio.get_device_count()):
                devInfo = audio.get_device_info_by_index(i)
                if devInfo["hostApi"] == 0:
                    name = devInfo["name"]
                    try:
                        name = name.encode("mbcs").decode("utf-8")
                    except:
                        pass
                    device_list.append(name)
            return list(set(device_list))
        return []
    except Exception:
        return []


def _merge_configs(existing, new):
    for key, value in new.items():
        if isinstance(value, dict) and key in existing:
            if isinstance(existing[key], dict):
                _merge_configs(existing[key], value)
            else:
                existing[key] = value
        else:
            existing[key] = value


# ----------------- 5. 路由实现 -----------------


@app.get("/", response_class=HTMLResponse)
async def home_get(request: Request, user: str = Depends(verify_credentials)):
    """首页 - 注入兼容版 url_for"""
    try:
        # 关键修改：将自定义的 url_for 注入到模板上下文中
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "url_for": lambda name, **params: flask_compatible_url_for(
                    request, name, **params
                ),
            },
        )
    except Exception as e:
        return HTMLResponse(content=f"Error loading home page: {e}", status_code=500)


@app.post("/api/get_run_status")
async def api_get_run_status(user: str = Depends(verify_credentials)):
    try:
        status_bool = fay_booter.is_running()
        return {"status": status_bool}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"status": False, "message": str(e)}
        )


@app.post("/api/get-data")
async def api_get_data(user: str = Depends(verify_credentials)):
    try:
        config_util.load_config()
        voice_list = []
        if config_util.tts_module == "ali":
            voice_list = [
                {"id": "abin", "name": "阿斌"},
                {"id": "zhixiaobai", "name": "知小白"},
                {"id": "zhixiaoxia", "name": "知小夏"},
            ]  # (省略部分，保持你原来的完整列表)
        elif config_util.tts_module == "volcano":
            voice_list = [{"id": "BV001_streaming", "name": "通用女声"}]  # (省略部分)
        else:
            raw = tts_voice.get_voice_list()
            for v in raw:
                v_data = v.value if hasattr(v, "value") else v
                voice_list.append({"id": v_data["name"], "name": v_data["name"]})

        # 简化版：复用原来的逻辑填充 voice_list (为节省篇幅略去部分，请确保保留你的完整列表)
        # 如果你之前没把完整列表粘进去，请务必把那些 'abin', 'zhixiaobai' 等加回来

        if wsa_server.get_web_instance():
            wsa_server.get_web_instance().add_cmd({"voiceList": voice_list})
            wsa_server.get_web_instance().add_cmd({"deviceList": _get_device_list()})
            if fay_booter.is_running():
                wsa_server.get_web_instance().add_cmd({"liveState": 1})

        return {"config": config_util.config, "voice_list": voice_list}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/submit")
async def api_submit(data: str = Form(...), user: str = Depends(verify_credentials)):
    if not data:
        return {"result": "error"}
    try:
        config_data = json.loads(data)
        config_util.load_config()
        _merge_configs(config_util.config, config_data["config"])
        config_util.save_config(config_util.config)
        config_util.load_config()
        return {"result": "successful"}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/get-asr-mode")
async def get_asr_mode(user: str = Depends(verify_credentials)):
    return {"asr_mode": config_util.ASR_mode}


@app.post("/api/start-live")
async def api_start_live(user: str = Depends(verify_credentials)):
    try:
        fay_booter.start()
        await asyncio.sleep(1)
        if wsa_server.get_web_instance():
            wsa_server.get_web_instance().add_cmd({"liveState": 1})
        return '{"result":"successful"}'
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/send")
async def api_send(data: str = Form(...), user: str = Depends(verify_credentials)):
    try:
        info = json.loads(data)
        interact = Interact("text", 1, {"user": info["username"], "msg": info["msg"]})
        util.printInfo(1, info["username"], f"[文字发送]{info['msg']}", time.time())
        fay_booter.feiFei.on_interact(interact)
        return '{"result":"successful"}'
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/get-msg")
async def api_get_msg(request: Request, user: str = Depends(verify_credentials)):
    try:
        # 兼容 Form/JSON
        data = None
        ct = request.headers.get("content-type", "")
        if "json" in ct:
            data = await request.json()
        else:
            form = await request.form()
            if form.get("data"):
                data = json.loads(form.get("data"))

        if not data:
            return {"list": []}

        uid = member_db.new_instance().find_user(data["username"])
        if uid == 0:
            return {"list": []}

        db_list = content_db.new_instance().get_list("all", "desc", 1000, uid)
        relist = []
        tz = pytz.timezone("Asia/Shanghai")
        for item in reversed(db_list):
            relist.append(
                {
                    "type": item[0],
                    "way": item[1],
                    "content": item[2],
                    "createtime": item[3],
                    "timetext": datetime.datetime.fromtimestamp(item[3], tz).strftime(
                        "%Y-%m-%d %H:%M:%S.%f"
                    )[:-3],
                    "username": item[5],
                    "id": item[6],
                    "is_adopted": item[7],
                }
            )
        if fay_booter.is_running() and wsa_server.get_web_instance():
            wsa_server.get_web_instance().add_cmd({"liveState": 1})
        return {"list": relist}
    except Exception:
        return {"list": []}


@app.post("/api/change-voice-mode")
async def change_voice_mode(
    data: dict = Body(...), user: str = Depends(verify_credentials)
):
    try:
        voice_mode = data.get("voiceMode")
        global CURRENT_VOICE_MODE
        CURRENT_VOICE_MODE = voice_mode
        from tts import vits

        vits.GLOBAL_SPEAKER_ID = voice_mode
        if voice_mode == 2:
            vits.GLOBAL_SDP_RATIO = 1.2
            vits.GLOBAL_LENGTH = 1.15
            vits.GLOBAL_SEGMENT_SIZE = 11
        else:
            vits.GLOBAL_SDP_RATIO = 0.2
            vits.GLOBAL_LENGTH = 0.8
            vits.GLOBAL_SEGMENT_SIZE = 50

        config_util.load_config()
        if "voice_mode" not in config_util.config:
            config_util.config["voice_mode"] = {}
        # 修正保存逻辑
        config_util.config["voice_mode"] = {
            "mode": voice_mode,
            "ratio": vits.GLOBAL_SDP_RATIO,
        }
        config_util.save_config(config_util.config)
        return {"result": "successful"}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/get-member-list")
async def api_get_member_list(user: str = Depends(verify_credentials)):
    try:
        return {"list": member_db.new_instance().get_all_users()}
    except Exception:
        return {"list": []}


@app.post("/api/clear-history")
async def clear_history(
    data: dict = Body(...), user: str = Depends(verify_credentials)
):
    try:
        uid = member_db.new_instance().find_user(data.get("username"))
        if uid == 0:
            return {"result": "error"}
        content_db.new_instance().clear_user_messages(uid)
        return {"result": "successful"}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )


@app.post("/api/change-asr-mode")
async def change_asr_mode(
    data: dict = Body(...), user: str = Depends(verify_credentials)
):
    try:
        mode = data.get("asrModel")
        config_util.ASR_mode = mode
        if fay_booter.recorderListener:
            fay_booter.recorderListener.reload_asr_client()
        return {"result": "successful"}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"result": "error", "message": str(e)}
        )
