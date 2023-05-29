

from app.redis import RedisResource
import app.config.config as Config
from flask import session
import requests
from ntessa.utils import get_auth_token

redis_client = RedisResource()

def get_is_root(key, project):

    if hasattr(Config,'white_users') and project in Config.white_users: # 有相关配置才进行判断
        # 从redis中获取v2_token
        v2_token_key = 'pod_web_console_k8s_token'
        v2_token_value = redis_client.read(v2_token_key)
        if not v2_token_value:
            v2_token_value = get_auth_token(Config.auth_user, Config.auth_key, auth_url=Config.auth_url + '/api/v2', ttl = 60 * 60 * 24)
            redis_client.write(v2_token_key, v2_token_value, 60 * 60 * 23 )
        user_name = session.get('email', '').split('@')[0]
        headers = {
            'x-access-token': v2_token_value
        }
        user_group = requests.get('{0}/api/v1/users/@{1}?_expand=1'.format(Config.auth_url,user_name),
                                headers = headers ).json()['groups']
        white_role_group = Config.white_users[project].get('group', [])
        white_user = Config.white_users[project].get('user', [])
        for group in user_group:
            if group['code'] in white_role_group or user_name in white_user:
                return 1, key

    try:
        if redis_client.read(key + '_root') :
            return 1, key
        elif redis_client.read(key):
            return 2, key
        else:
            return 3, key
    except:
        return 4, key