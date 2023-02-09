import base64
import hashlib
import hmac

from flask import redirect, url_for
from flask import session, request
from flask import render_template
from flask_restful import reqparse

from flask_sockets import Sockets
from flask import render_template, request
import logging
import re,json
from app.k8s import k8s_client, k8s_stream_thread
from app import app
import app.openid as openid
import app.config.config as Config
import app.common as Common
from app.redis import RedisResource

redis_client = RedisResource()
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


@app.route('/terminal/redis',methods=['POST'])
def set_redis():
    parser = reqparse.RequestParser(bundle_errors=True)
    parser.add_argument('key', type=str, required=True)
    parser.add_argument('expire', type=int, required=True)
    payload = parser.parse_args()
    key = payload['key']
    try:
        redis_client.write(key, 'true', payload['expire'])
        return json.dumps({"code": 200,"msg": 'success'})
    except:
        return json.dumps({"code": 400,"msg": '连接redis失败'}), 400


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
    return render_template('terminal.html')

@sockets.route('/terminal/<region>/<namespace>/<pod>/<container>')
def terminal_socket(ws, region, namespace, pod, container):
    cols = request.args.get('cols') # 控制tty输出的长、宽
    rows = request.args.get('rows')

    # pod: webccmspclog-7c69c997b6-vggfq，deploy、daemonset类型的
    # pod: webccmspclog-0，statefulset类型的，数字结尾
    # redis中的key，有包含控制器（服务名）名字，服务名从pod中获取
    if re.search('^[0-9]*$',pod.split('-')[-1]):  #最后一段全是数字，statefulset类型的
        controller_name = '-'.join(pod.split('-')[:-1])
    else:
        controller_name = '-'.join(pod.split('-')[:-2])
    
    # cc的比较特殊，比如登陆actanchorhotcard2019sandbox，actanchorhotcard2019-stage, 需要查询的服务是actanchorhotcard2019
    if Config.kube_config_dict[region]['project'] == 'cc':
        controller_name =  controller_name.split('sandbox')[0]
        controller_name =  controller_name.split('-stage')[0]

    # 验证redis中的key是否过期
    # redis中key的格式，比如：
    # aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling，默认用户进入
    # aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling_root, root用户进入
    key = 'aladdin-' + Config.kube_config_dict[region]['project'] + '-symconsole-' + namespace + '-' + controller_name + '_' + session.get('email', '').split('@')[0]
    # print(key)
    try:
        if redis_client.read(key + '_root') :
            is_root = True
        elif redis_client.read(key):
            is_root = False
        else:
            ws.send('redis中没有找到以下key:\r\n')
            ws.send(key + '_root' + '(不限制命令执行！)\r\n')
            ws.send(key + '(限制命令执行！))\r\n')
            ws.send('可能未申请或者已过期!\r\n')
            ws.close()
            return
    except:
        ws.send('redis连接失败！')
        ws.close()
        return
    
    kub = k8s_client(region, is_root)

    try:
        # print(Config.kube_config_dict)
        namespace = Config.kube_config_dict[str(region)]['project'] + '-' + namespace
        container_stream = kub.terminal_start(namespace, pod, container, cols, rows)
        # print(namespace,pod,container)
    except Exception as err:
        ws.send('Connect container error: {0}\r\n'.format(err))
        ws.send('可能原因：region参数等输入错误、服务到region的网络不通等！')
        ws.close()
        return

    username = session.get('email', '').split('@')[0] # 用于日志打印
    fullname = session.get('fullname', '')

    kub_stream = k8s_stream_thread(ws, container_stream, region, namespace, pod, username, fullname)
    kub_stream.start()

    try:
        cmd_in = ''
        while not ws.closed: #不停的接收ws数据帧，比如，输入一个ls，会分2条帧l、s过来
            message = ws.receive()
            # print(message.encode('utf-8'))
            if not is_root: # 非root权限才进行输入判断
                #回车后：
                # debian: \r
                # alpine: \r + \x1b[3;41R
                # \t，table，命令补全
                # '\x1b[A' 上箭头
                # '\x1b[B' 下箭头
                if message == '\x04':
                    cmd_in = ''
                    ws.send(' -> 不允许执行 Ctrl + d !' )
                    container_stream.write_stdin('\x03') # 发送ctrl+c
                elif re.match('[/\.\|\w-]', message)  or message == ' ': # \w表示[0-9a-zA-Z-] 
                    cmd_in += message
                    # print(cmd_in.encode('utf-8'))
                elif message == '\x7f':     # 删除键
                    cmd_in = cmd_in[:-1]
                elif message == '\r': # 输入结束
                    if cmd_in == 'exit': # 用户进入可能是普通用户，exit会回到root用户，这里控制下，如果输入exit直接关闭ws
                        container_stream.write_stdin('\r') #退出一下，否则很多sh进程残留
                        container_stream.close()
                        ws.close()
                    if cmd_in != '' and message != '\t': # 排除：回车、或者table键
                        # cmd_in 举例， /usr/bin/wget 'aa.com/a.txt'、ps ux、ip
                        if not Common.is_allow_command(cmd_in.split(' ')[0].split('/')[-1]):
                            message = '\x03' # 发送ctrl+c
                            ws.send(' -> 不允许执行' + cmd_in.split(' ')[0] + '    ')
                        cmd_in = '' # 命令行结束，将变量置空
            if message is not None and message != '__ping__':
                container_stream.write_stdin(message)
                
        container_stream.write_stdin('exit\r') #ws关闭了，到容器的通道也关闭
        container_stream.close() #ws关闭了，到容器的通道也关闭
    except Exception as err:
        logging.error('Connect container error: {}'.format(err))
    finally:
        container_stream.write_stdin('exit\r') #直接刷新浏览器，需要将用户退出下，否则会有很多sh进程残留
        container_stream.close()
        ws.close()

@app.route('/terminal', methods=['GET'])
def index():
    return render_template('index.html')