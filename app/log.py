import logging, logging.config, os
import structlog
from structlog import configure, stdlib
from pythonjsonlogger import jsonlogger
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG = True  # 标记是否在开发环境

# os.m
# os.mkdir('log')
if not  os.path.exists(BASE_DIR + '/log'):
    os.mkdir(BASE_DIR + '/log')

# 给过滤器使用的判断
class RequireDebugTrue(logging.Filter):
    # 实现filter方法
    def filter(self, record):
        return DEBUG

def get_logger():
    LOGGING = {
    # 基本设置
        'version': 1,  # 日志级别
        'disable_existing_loggers': False,  # 是否禁用现有的记录器

    # 日志格式集合
        'formatters': {
        # 标准输出格式
            'json': {
                'format': '[%(asctime)s]',
                'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            }
        },
    # 过滤器
        'filters': {
            'require_debug_true': {
                '()': RequireDebugTrue,
            }
        },
    # 处理器集合
        'handlers': {
        # 输出到控制台，暂时不需要
        # 输出到文件
            'TimeChecklog': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': os.path.join("./log/", 'pod-web-console-command.log'),  # 输出位置
                'maxBytes': 1024 * 1024 * 500,  # 文件大小 500M
                'backupCount': 20,  # 备份份数
                'encoding': 'utf8',  # 文件编码
            },
        },
    # 日志管理器集合
        'loggers': {
        # 管理器
            'proxyCheck': {
                'handlers': ['TimeChecklog'],
                'level': 'DEBUG',
                'propagate': False,  # 是否传递给父记录器
            },
        }
    }

    configure(
        logger_factory=stdlib.LoggerFactory(),
        processors=[
            stdlib.render_to_log_kwargs]
    )


    logging.config.dictConfig(LOGGING)
    logger = logging.getLogger("proxyCheck")
    return logger