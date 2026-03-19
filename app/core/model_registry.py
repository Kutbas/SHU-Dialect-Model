import os
from typing import List, Union
from app.schemas.chat import APIConfig, OllamaConfig

# 集中管理所有提示词
XIAOHU_PROMPT = """你是一位精通上海话的专家，来自上海大学，你叫“小沪”。你的任务是与用户进行上海话的对话互动。
用户可能会用普通话或者英文和你对话，但用户并不完全掌握上海话，因此在跟你对话时可能会使用不标准的发音或包含错别字的上海话书面表达，你需要识别他们并给出正确的回答。
如果用户提出刁钻或不合适的问题，你可以机智地回避或幽默化解，而不直接拒绝回答。
你的职责是：
1、理解用户以不标准上海话或带有错别字的上海话进行的表达。
2、使用标准、地道的上海话文字与用户进行交流，尽量展现上海话的正宗表达，除非你要背诵一首诗歌。
3、你的回答不需要加上“小沪：”的前缀，直接给出回复即可。
记住，你需要始终保持以地道的上海话进行交流，同时用温和、友好的态度帮助用户提高上海话的表达能力。你的名字是“小沪”，但当用户可能会叫错你的名字的时候，不需要纠正用户。
你的回答也不需要用括号表示出你的动作或者表情，直接用文字表达你的意思就好。"""

# 后续可以继续在这里添加 BEIJING_PROMPT, ENGLISH_TEACHER_PROMPT 等...


# 集中配置所有挂载的模型
def get_all_models() -> List[Union[APIConfig, OllamaConfig]]:
    """获取系统需要挂载的所有模型配置列表"""

    return [
        # 基础大模型 - DeepSeek
        APIConfig(
            model_name="deepseek-chat",
            api_key=os.getenv("deepseek_apikey", ""),
            temperature=0.7,
        ),
        # 提示词封装模型 - 小沪 (基于 DeepSeek)
        APIConfig(
            model_name="小沪(上海话专家)",
            real_model="deepseek-chat",  # 底层引擎
            api_key=os.getenv("deepseek_apikey", ""),
            system_prompt=XIAOHU_PROMPT,  # 注入人设
            greeting="侬好！我是上海大学的小沪，很高兴和侬用上海话聊天。有什么我可以帮侬的吗？",
            temperature=0.7,
        ),
        # 基础大模型 - ChatGPT
        APIConfig(
            model_name="gpt-4o-mini",
            api_key=os.getenv("chatgpt_apikey", ""),
            temperature=0.7,
        ),
        # 基础大模型 - Gemini
        APIConfig(
            model_name="gemini-2.5-flash",
            api_key=os.getenv("gemini_apikey", ""),
            endpoint="",
            temperature=0.7,
            max_tokens=8192,
        ),
        # 本地基础模型 - Ollama
        OllamaConfig(
            model_name="deepseek-r1:1.5b",
            model_desc="本地 Ollama 模型",
            endpoint="http://192.168.71.103:11434",
            temperature=0.7,
        ),
    ]
