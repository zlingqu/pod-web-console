
from flask import Flask,request
from ntessa_next.auth.web import init_flask_app, authorize_request
from .err import authorize_error_handler
from ntessa_next.auth.exception import (
    AuthorizeError,AuthorizeUserError
)
import app.config.config as Config
app = Flask(__name__, static_folder='static',
            static_url_path='/terminal/static')
app.secret_key = 'FiDZjjn1g0sxdVk4'


app.config.update({
    'NTESSA_AUTH_FLASK_BEFORE_REQUEST': False, # 不要全局注入
    'NTESSA_AUTH_SYSTEM_USER': Config.auth_user,
    'NTESSA_AUTH_KEY': Config.auth_key,
    'NTESSA_AUTH_ENABLE_DEBUG': False,
    'NTESSA_AUTH_BASE_URL': Config.auth_url
})


# 注入 auth 校验
init_flask_app(app)
# 注入错误
app.register_error_handler(AuthorizeError,authorize_error_handler)

# 请求前的处理
@app.before_request
def call_before_request_callbacks():
    # print('request.path:',request.path)
    if request.path == '/terminal/redis':
        authorize_request()
        if request.auth['name'] not in Config.redis_post_user : # 阿拉丁执行，进行redis授权
            raise AuthorizeUserError(msg='该接口必须是管理员用户才可以调用！')
    return