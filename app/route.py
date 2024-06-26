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
from app.k8s import k8s_client, k8s_stream_thread, multi_k8s_stream_thread
from app import app
import app.openid as openid
import app.config.config as Config
import app.handler as handler
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
    

    if (request.args.get('cluster', '') and \
       request.args.get('namespace', '') and \
       request.args.get('pod', '') and \
       request.args.get('container', '')) :
        # 登陆单个pod
        return render_template('terminal.html')
    if (request.args.get('project', '') and \
       request.args.get('namespace', '') and \
       (request.args.get('deployment', '') or request.args.get('statefulset', '')) and \
       request.args.get('container', '')) :
        # 登陆多个pod，指定deployment或者statefulset名字
        return render_template('terminal.html')

    return '''<h1>参数错误</h1> 
        <br /> 支持以下3种使用方式:
            <ul> 
                <li><h2>单pod登录：</h2>http://xxx.163.com/terminal/window?cluster=xxx&namespace=xxx&pod=xxx&container=xxx</li>
                <li><h2>deployment 多pod登录：</h2>http://xxx.163.com/terminal/window?project=xxx&namespace=xxx&deployment=xxx&container=xxx</li>
                <li><h2>statefulset 多pod登录：</h2>http://xxx.163.com/terminal/window?project=xxx&namespace=xxx&statefulset=xxx&container=xxx</li>

            </ul>
        <br /><br /> 
        '''
    

@sockets.route('/terminal/<cluster>/<namespace>/<pod>/<container>')
def terminal_socket(ws, cluster, namespace, pod, container):
    if not session.get('email'):
        return redirect('openidlogin')
    
    origin_domain = request.headers.get('Origin','').split('//')[1].split(':')[0]
    if origin_domain not in Config.origin_domain:
        ws.send('不允许跨域！')
        ws.close()
        return

    if str(cluster) not in Config.kube_config_dict.keys():
        ws.send('cluster【{}】还没有接入该系统！！ \r\n'.format(cluster))
        ws.close()
        return

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
    if Config.kube_config_dict[cluster]['project'] == 'cc':
        controller_name =  controller_name.split('sandbox')[0]
        controller_name =  controller_name.split('-stage')[0]

    # redis中key的格式有2种：
    # aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling，普通用户nguser进入，有命令限制
    # aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling_root, 容器默认用户(一般是root）用户进入，命令无限制
    key = 'aladdin-' + Config.kube_config_dict[cluster]['project'] + '-symconsole-' + namespace + '-' + controller_name + '_' + session.get('email', '').split('@')[0]
    is_root,key = handler.get_is_root(key, Config.kube_config_dict[cluster]['project'])
    if is_root == 1:
        is_root = True
    elif is_root == 2:
        is_root = False
    elif is_root == 3:
        ws.send('redis中没有找到以下key:\r\n')
        ws.send(key + '_root' + '(不限制命令执行！)\r\n')
        ws.send(key + '(限制命令执行！))\r\n')
        ws.send('可能未申请或者已过期!\r\n')
        ws.close()
        return
    else:
        ws.send('redis连接失败！')
        ws.close()
        return
    
    kub = k8s_client(cluster, is_root)

    try:
        # print(Config.kube_config_dict)
        namespace = Config.kube_config_dict[str(cluster)]['project'] + '-' + namespace
        container_stream = kub.terminal_start(namespace, pod, container, cols, rows)
        # print(namespace,pod,container)
    except Exception as err:
        ws.send('连接容器遇到错误: {0}\r\n'.format(err))
        ws.send('可能原因：cluster参数等输入错误、服务到cluster的网络不通等！')
        ws.close()
        return

    username = session.get('email', '').split('@')[0] # 用于日志打印
    fullname = session.get('fullname', '')

    kub_stream = k8s_stream_thread(ws, container_stream, cluster, namespace, pod, username, fullname)
    kub_stream.start()

    try:
        cmd_in = ''
        is_vim = False # vim模式下，不做命令输入判断
        is_up_down = False # up_down模式，使用上下箭头获取输入历史，历史命令有权限，也认为当前操作也有权限，不用判定
        while not ws.closed: #不停的接收ws数据帧，比如，输入一个ls，会分2条帧l、s过来
            message = ws.receive()
            if not is_root: # 非root权限才进行输入判断
                #回车后：
                # debian: \r
                # alpine: \r + \x1b[3;41R
                # \t，table，命令补全
                # '\x1b[A' 上箭头
                # '\x1b[B' 下箭头
                if message == '\x04': # Ctrl + d = '\x04'，否则用户从nguser返回root用户
                    cmd_in = ''
                    ws.send(' -> 不允许执行 Ctrl + d !' )
                    container_stream.write_stdin('\x03') # 发送ctrl+c
                elif message.encode('utf-8') in [b'\x1b[A', b'\x1b[B']: # 进入up_down模式
                    is_up_down = True
                elif re.match('[/\.\|\w\:-]', message)  or message == ' ': # \w表示[0-9a-zA-Z-] 
                    cmd_in += message
                elif message == '\x7f':     # 删除键
                    cmd_in = cmd_in[:-1]
                elif message == '\r': # 输入结束
                    if cmd_in == 'exit': # 用户进入可能是普通用户，exit会回到root用户，这里控制下，如果输入exit直接关闭ws
                        container_stream.write_stdin('\r') #退出一下，否则很多sh进程残留
                        container_stream.close()
                        ws.close()
                    cmd_in_first = cmd_in.split(' ')[0].split('/')[-1]
                    if  cmd_in_first in ['vi','vim']:
                        is_vim = True  # 进入vim模式
                    if cmd_in in [':q', ':q!', ':wq', ':wq!', ':x', ':x!', ':exit', ':qa', 'cq']:
                        is_vim = False # 退出vim模式
                    
                    if cmd_in != '' and message != '\t' and not is_vim and not is_up_down: # 排除：回车、或者table键、不是vim模式
                        # cmd_in 举例， /usr/bin/wget 'http://aa.com/a.txt'、ps ux、ip,
                        if not Common.is_allow_command(cmd_in_first):
                            message = '\x03' # 发送ctrl+c
                            ws.send(' -> 不允许执行' + cmd_in.split(' ')[0] + '    ')
                    is_up_down = False  # 命令行结束，关闭up_down模式
                    cmd_in = ''         # 命令行结束，将变量置空
            if message is not None and message != '__ping__':
                container_stream.write_stdin(message)
                
        container_stream.write_stdin('exit\r') #ws关闭了，到容器的通道也关闭
        container_stream.close() #ws关闭了，到容器的通道也关闭
    except Exception as err:
        logging.error('连接容器遇到错误: {}'.format(err))
    finally:
        container_stream.write_stdin('exit\r') #直接刷新浏览器，需要将用户退出下，否则会有很多sh进程残留
        container_stream.close()
        ws.close()
# 批量登陆pod
@sockets.route('/terminal/multi/<project>/<namespace>/<name>/<container>')
def terminal_socket(ws, project, namespace, name, container):
    if not session.get('email'):
        return redirect('openidlogin')
    
    origin_domain = request.headers.get('Origin','').split('//')[1].split(':')[0]
    if origin_domain not in Config.origin_domain:
        ws.send('不允许跨域！')
        ws.close()
        return

    if project not in [v['project'] for v in Config.kube_config_dict.values()]:
        ws.send('项目【{}】还没有接入该系统！！ \r\n'.format(project))
        ws.close()
        return

    cols = request.args.get('cols') # 控制tty输出的长、宽
    rows = request.args.get('rows')
    controller_type = request.args.get('controller')

    controller_name = name
    # cc的比较特殊，比如登陆actanchorhotcard2019sandbox，actanchorhotcard2019-stage, 需要查询的服务是actanchorhotcard2019
    if project == 'cc':
        controller_name =  controller_name.split('sandbox')[0]
        controller_name =  controller_name.split('-stage')[0]

    # redis中key的格式
    # aladdin-cc-symconsole-pythonapp-actanchorhotcard2019_quzhongling_root, 容器默认用户(一般是root）用户进入，命令无限制
    key = 'aladdin-' + project + '-symconsole-' + namespace + '-' + controller_name + '_' + session.get('email', '').split('@')[0] + '_root'

    is_root,key = handler.get_is_root(key, project)

    if is_root == 1:
        is_root = True
    elif is_root == 2:
        is_root = False
    elif is_root == 3:
        ws.send('redis中没有找到以下key:\r\n')
        ws.send(key + '(不限制命令执行！)\r\n')
        ws.send('批量登陆容器需要root权限！\r\n')
        ws.send('可能未申请或者已过期!\r\n')
        ws.close()
        return
    else:
        ws.send('redis连接失败！')
        ws.close()
        return
    pod_list = []
        # 找出该服务所拥有的所有pod
    for k,v in Config.kube_config_dict.items():
        if v['project'] == project:
            # print('k:',k, name, project + '-' + namespace)
            sub_pod_list = k8s_client(k, True).get_controller_pod(project + '-' + namespace, name, controller_type)
            pod_list += sub_pod_list
    # print('pod_list',pod_list)
    if not pod_list: # 没有找到pod
        ws.send('遇到错误，没有找到pod，可能原因: \r\n')
        ws.send('1. 本代理到集群api server的网络不通！\r\n')
        ws.send('2. 服务和namespace、project等不匹配 \r\n')
        ws.send('3. 不存在本服务 \r\n')
        ws.send('4. 本服务副本是0 \r\n')
        ws.close()
        return
    container_stream_list = []
    for pod in pod_list:
        c = pod.split('-')[-1]
        p = '-'.join(pod.split('-')[0:-1])
        try:
            container_stream_list.append({
                'stream': k8s_client(c,True).terminal_start(project + '-' + namespace, p, container, cols, rows),
                'pod': pod
            })
        except:
            pass
            #  多集群时，有些个别集群container参数不符合
            print('链接失败～～',project + '-' + namespace, c,p,container)


    username = session.get('email', '').split('@')[0] # 用于日志打印
    fullname = session.get('fullname', '')
    kub_stream = multi_k8s_stream_thread(ws, container_stream_list , project, namespace, username, fullname)
    kub_stream.start()

    try:
        while not ws.closed: # 不停的接收ws数据帧，比如，输入一个ls，会分2条帧l、s过来
            message = ws.receive()
            ws.send(message)
            if message is not None and message != '__ping__':
                for container_stream in container_stream_list:
                    container_stream['stream'].write_stdin(message)
        for container_stream in container_stream_list:
            container_stream['stream'].write_stdin('exit\r') #ws关闭了，到容器的通道也关闭
            container_stream['stream'].close() #ws关闭了，到容器的通道也关闭
    except Exception as err:
        logging.error('连接容器遇到错误: {}'.format(err))
    finally:
        for container_stream in container_stream_list:
            container_stream['stream'].write_stdin('exit\r') #直接刷新浏览器，需要将用户退出下，否则会有很多sh进程残留
            container_stream['stream'].close() #ws关闭了，到容器的通道也关闭
        ws.close()
        return


@app.route('/terminal', methods=['GET'])
def index():
    return render_template('index.html')