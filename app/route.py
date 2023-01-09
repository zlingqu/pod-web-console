import base64
import hashlib
import hmac

from flask import redirect, url_for
from flask import session, request
from flask import render_template

from flask_sockets import Sockets
from flask import render_template, request
import logging
import re
from app.k8s import k8s_client, k8s_stream_thread
from app import app
import app.openid as openid

# from app.config import Config
import app.config as Config

sockets = Sockets(app)

@app.route('/')
def homepage():
    if not session.get('email'):
        return redirect('openidlogin')
    else:
        return redirect(url_for('index'))

@app.route('/terminal/logout')
def logout():
    session.pop('fullname', None)
    session.pop('email', None)
    return redirect(url_for('homepage'))


@app.route('/terminal/openidlogin')
def openid_login():
    location, mac_key = openid.redirect_url(request.url_root, url_for('index'))
    session['mac_key'] = mac_key
    return redirect(location)

@app.route('/terminal/login_callback')
def login_callback():
    #构造需要检查签名的内容
    OPENID_RESPONSE = dict(request.args)
    '''
    {'next': '/', 
    'openid.assoc_handle': '{HMAC-SHA256}{63b30caa}{7WCQUQ==}', 
    'openid.ax.mode': 'fetch_response', 
    'openid.claimed_id': 'https://login.netease.com/openid/quzhongling/', 
    'openid.identity': 'https://login.netease.com/openid/quzhongling/', 
    'openid.mode': 'id_res', 
    'openid.ns': 'http://specs.openid.net/auth/2.0', 
    'openid.ns.ax': 'http://openid.net/srv/ax/1.0', 
    'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1', 
    'openid.op_endpoint': 'https://login.netease.com/openid/', 
    'openid.response_nonce': '2023-01-02T16:56:13ZKjxrt9', 
    'openid.return_to': 'http://endeavour.nie.netease.com:8000/login_callback?next=%2F', 
    'openid.sig': 'MK3ihHFI7O8ANB7eQBX4WM9srgiFN43214GG3LmbZ/Y=', 
    'openid.signed': 'assoc_handle,ax.mode,claimed_id,identity,mode,ns,ns.ax,ns.sreg,op_endpoint,response_nonce,return_to,signed,sreg.email,sreg.fullname,sreg.nickname', 
    'openid.sreg.email': 'quzhongling@corp.netease.com', 
    'openid.sreg.fullname': '曲中岭', 
    'openid.sreg.nickname': 'quzhongling'}
    '''
    SIGNED_CONTENT = []

    for k in OPENID_RESPONSE['openid.signed'].split(","):
        tmp_data = OPENID_RESPONSE["openid.{}".format(k)]
        SIGNED_CONTENT.append("{0}:{1}\n".format(k,tmp_data))
    SIGNED_CONTENT = "".join(SIGNED_CONTENT).encode("utf-8")
    # 使用associate请求获得的mac_key与SIGNED_CONTENT进行assoc_type hash，
    # 检查是否与OpenID Server返回的一致

    SIGNED_CONTENT_SIG = base64.b64encode(
            hmac.new( base64.b64decode(session.get('mac_key', '')),
            SIGNED_CONTENT, hashlib.sha256 ).digest())
    
    if SIGNED_CONTENT_SIG != OPENID_RESPONSE['openid.sig'].encode('utf-8'):
        return '认证失败，请重新登录验证',403
    
    session.pop('mac_key', None) 
    email = request.args.get('openid.sreg.email', '')
    fullname = request.args.get('openid.sreg.fullname', '')
    next_url = request.args.get('next', '/terminal')
    if not email or not fullname:
        return '无法获取email和fullname',403
    session['email'] = email
    session['fullname'] = fullname 
    return redirect(next_url) 

@app.route('/terminal/window', methods=['GET'])
def terminal():
    if not session.get('email',''): # 未登陆时，先登陆
        location, mac_key = openid.redirect_url(request.url_root, url_for('terminal'))
        session['mac_key'] = mac_key
        return redirect(location)
    

    if not (request.args.get('region', '') and \
       request.args.get('namespace', '') and \
       request.args.get('pod', '') and \
       request.args.get('container', '')) :

        return '''<h1>参数错误</h1> 
            <br /> 必须同时指定4个参数，
                <ul> 
                    <li>region</li>
                    <li>namespace</li>
                    <li>pod</li>
                    <li>container</li> 
                </ul>
            <br /><br /> 
            比如： http://xxx.163.com/terminal/window?region=xxx&namespace=xxx&pod=xxx&container=xxx
            '''
    # 登陆有，验证redis中的key是否过期
    from app.redis import RedisResource
    redis_url = Config.myConfig.REDIS
    host, port, db = re.match(r'redis://(.*):(.*)/(.*)', redis_url).groups()
    redis_client = RedisResource(host=host, port=port, db=db)
    # redis中key的格式，比如：aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling
    # cc的比较特殊，比如登陆actanchorhotcard2019sandbox，需要查询的服务是actanchorhotcard2019
    key = 'aladdin-' + Config.region_info[request.args.get('region')]['project'] + '-symconsole-' + request.args.get('namespace') + '-' + request.args.get('container').split('sandbox')[0] + '_' + session.get('email', '').split('@')[0]
    value = redis_client.read(key)
    if not value:
        return "<h4>redis中没有找到以下key: \
        <h3>{}</h3> \
        <h4>可能未申请或者已过期</h4>".format(key),403
    else:
        return render_template('terminal.html')

@sockets.route('/terminal/<region>/<namespace>/<pod>/<container>')
def terminal_socket(ws, region, namespace, pod, container):
    cols = request.args.get('cols') # 控制tty输出的长、宽
    rows = request.args.get('rows')
    # logging.info('Try create socket connection')
    kub = k8s_client(region)

    try:
        container_stream = kub.terminal_start(Config.region_info[region]['project'] + '-' + namespace, pod, container, cols, rows)
        # print(namespace,pod,container)
    except Exception as err:
        logging.error('Connect container error: {}'.format(err))
        ws.send('Connect container error: {}'.format(err))
        ws.send('可能原因：region参数等输入错误、服务到region的网络不通等！')
        ws.close()
        return

    kub_stream = k8s_stream_thread(ws, container_stream)
    kub_stream.start()

    logging.info('Start terminal')
    try:
        while not ws.closed:
            message = ws.receive()
            if message is not None:
                if message != '__ping__':
                    container_stream.write_stdin(message)
        container_stream.write_stdin('exit\r')
    except Exception as err:
        logging.error('Connect container error: {}'.format(err))
    finally:
        container_stream.close()
        ws.close()

@app.route('/terminal', methods=['GET'])
def index():
    return render_template('index.html')