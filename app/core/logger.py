import sys
from loguru import logger


def init_logger(logger_name: str, logger_file: str = "stdout", log_level: str = "INFO"):
    """
    初始化日志配置
    """
    # 移除 loguru 默认的控制台输出
    logger.remove()

    # 定义日志格式
    # {time:HH:mm:ss} | {extra[logger_name]} | {level:<7} | {message}
    console_format = (
        "<green>[{time:HH:mm:ss}]</green>"
        "[<cyan>{extra[logger_name]}</cyan>]"
        "[<level>{level:<7}</level>]"
        " <level>{message}</level>"
    )

    file_format = "[{time:HH:mm:ss}][{extra[logger_name]}][{level:<7}] {message}"

    # 配置文件输出或控制台输出
    if logger_file == "stdout":
        logger.add(
            sys.stdout,
            level=log_level.upper(),
            format=console_format,
            colorize=True,  # 启用终端颜色
            enqueue=True,  # 启用异步队列写入，线程安全！
        )
    else:
        logger.add(
            logger_file,
            level=log_level.upper(),
            format=file_format,
            enqueue=True,  # 异步写入（通过独立线程+队列完成）
            rotation="10 MB",  # 文件达到 10MB 自动打包轮转
            retention="7 days",  # 只保留最近7天的日志
        )

    # 绑定自定义的 logger 名称
    bound_logger = logger.bind(logger_name=logger_name)
    return bound_logger


# 导出全局单例 Logger (C++ 中获取单例的逻辑)
# 在 Python 中，模块级别的变量天然就是线程安全的单例
log = init_logger(logger_name="ChatServer", logger_file="stdout", log_level="INFO")
