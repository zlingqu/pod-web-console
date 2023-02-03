
from flask import Flask

app = Flask(__name__, static_folder='static',
            static_url_path='/terminal/static')
app.secret_key = 'FiDZjjn1g0sxdVk4'

# from flask import request
# import json
# import re,logging
# from flask import session

# @app.after_request
# def call_after_request_callbacks(response):
#     if not hasattr(request, 'auth'):
#         request.auth = {}
#     username = session.get('email', '').split('@')[0]
#     # 通过referer获取请求来源的项目
#     referer = request.headers.get('referer')
#     source_project = re.search(r'\/\/(.+?)\.', referer).group(1) if referer else '-'
#     # 统计一下server提供了哪些API
#     api = '%s%s' % (request.script_root, request.path)
#     data = {
#         'url': request.url.replace(" ", "") if request.url else '-',
#         'api': api,
#         'method': request.method,
#         'status_code': response.status_code,
#         'host': request.host,
#         'sub_project': request.auth.get('project', '-'),
#         'username': username,
#         'referer': request.headers.get('referer'),
#         'source_project': source_project,
#         'X_Forwarded_For': request.headers.get('X-Forwarded-For')
#     }
#     if request.method == 'PUT' or request.method == 'POST':
#         data.update({
#             'params': request.data,
#             'description': response.response
#         })
#     # logging.info(json.dumps(data))
#     print(json.dumps(data))
#     return response