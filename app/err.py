from flask import jsonify

def authorize_error_handler(exception):
    from ntessa_next.auth.exception import (
        ParseTokenError, 
        TokenNotFoundError, 
        TokenExpiredError,
        AuthorizeUserError
    )
    if isinstance(exception, ParseTokenError):
        # 解析token异常
        result = {
            'error_msg': 'Token 无法解析',
            'error_code': 10000,
            'detail': {"msg": repr(exception)},
        }
        return jsonify(result), 403
    elif isinstance(exception, TokenNotFoundError):
        # 没有设置token
        result = {
            'error_msg': 'Token 为空',
            'error_code': 10001,
            'detail': {"msg": repr(exception)},
        }
        return jsonify(result), 403
    elif isinstance(exception, TokenExpiredError):
        # token过期（auth token检查expire字段，access_token检查exp字段）
        result = {
            'error_msg': 'Token 已过期',
            'error_code': 10002,
            'detail': {"msg": repr(exception)},
        }
        return jsonify(result), 401
    elif isinstance(exception, AuthorizeUserError):
        # 获取用户数据失败，可能是token已经被拉黑名单
        # error.status_code 为 http 返回码
        # error.msg 为 http 请求返回的内容，如果是json类型的话则会被解析为字典
        result = {
            'error_msg': '失败！',
            'error_code': 10003,
            'detail': {"msg": repr(exception)},
        }
        return jsonify(result), 401
    return jsonify({
        'error_msg': 'Unknown authorize error', 
        'error_code': 10004,
        'detail': {"msg": repr(exception)},
    }), 500
