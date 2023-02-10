from kubernetes import client, config
from kubernetes.stream import stream
import logging
import threading
import json,re
import app.config.config as Config
import app.log as Log
from flask import session
from app.redis import RedisResource
from ntessa.utils import get_auth_token

redis_client = RedisResource()
logger = Log.get_logger()

class k8s_client(object):
    def __init__(self, cluster, is_root):
        self.cluster = cluster
        self._update_token()
        self.is_root = is_root
        self.project = Config.kube_config_dict[cluster]['project']
        config.load_kube_config_from_dict(config_dict=Config.kube_config_dict[str(cluster)]['kube'])
        self.client_core_v1 = client.CoreV1Api()
        

    def _update_token(self):
        key = 'pod_web_console_k8s_token'
        value = redis_client.read( key)
        if value:
            Config.kube_config_dict[str(self.cluster)]['kube']['users'][0]['user']['token'] = value
        else:
            token = get_auth_token(Config.auth_user, Config.auth_key, ttl = 60 * 60 * 24)
            redis_client.write(key, token, 60 * 60 * 23 )
            Config.kube_config_dict[str(self.cluster)]['kube']['users'][0]['user']['token'] = token

    def get_ns(self):
        ret = self.client_core_v1.list_namespace()
        result = [ ns.metadata.name for ns in ret.items ]
        return result

    def terminal_start(self, namespace, pod, container, cols, rows):
        if self.is_root:
            command = [ #默认是项目用户
            "/bin/sh",
            "-c",
            '''(id {0} > /dev/null 2>&1 && su - {0}) || exec /bin/bash || exec /bin/sh'''.format(self.project)
            ]
        else:
            command = [
            "/bin/sh",
            "-c",
            '''(id {0} > /dev/null 2>&1 || useradd -m {0} > /dev/null 2>&1 || adduser -D {0} ) && \
            ([ -e /home/{0}/.bashrc ] && sed -i '/alias ls=/d' /home/{0}/.bashrc && sed -i 's/xterm*\|rxvt*/xxxterm/g' /home/{0}/.bashrc) && \
            su - {0} && (exec /bin/bash || exec /bin/sh) \
            '''.format(Config.default_user)
            ]

        container_stream = stream(
            self.client_core_v1.connect_get_namespaced_pod_exec,
            name=pod,
            namespace=namespace,
            container=container,
            command=command,
            stderr=True, stdin=True,
            stdout=True, tty=True,
            _preload_content=False
        )
        container_stream.write_channel(4, json.dumps({"Height": int(rows), "Width": int(cols)}))
        # print(namespace,pod,container, cols, rows)
        return container_stream

class k8s_stream_thread(threading.Thread):

    def __init__(self, ws, container_stream, cluster, namespace, pod, username, fullname):
        super(k8s_stream_thread, self).__init__()
        self.ws = ws
        self.stream = container_stream
        self.project = Config.kube_config_dict[cluster]['project']
        self.cluster = cluster
        self.namespace = namespace
        self.pod = pod
        self.username = username
        self.fullname = fullname
        # nguser@jeventproxynew-7776d48b44-sxvdg:~$
        # root@jeventproxynew-7776d48b44-sxvdg:/var/log#
        # (pythonappvenv) nguser@agmhsyjh2023-dcd64db4c-wrfs8:/home/cc/.virtualenvs/pythonapp/agmhsyjh2023/bin$ 
        self.ps1 = '[()\w ]*@' + self.pod + ':[~/\.\w]*[\$#]{1}\s'
    
    def _is_include_ps1(self,string):
        if re.search(self.ps1,string):
            return True, re.findall(self.ps1, string)[0]
        return False, ''
    
    def run(self):
        cmd_out = ''
        while not self.ws.closed:
            if not self.stream.is_open():
                logging.info('container stream closed')
                self.ws.close()
            try:
                if self.stream.peek_stdout():
                    stdout = self.stream.read_stdout(timeout=3)
                    # print('stdout:', stdout.encode('utf8'))
                    cmd_out += stdout
                    # print('cmd_out:',cmd_out.encode('utf8'))
                    code, subStr = self._is_include_ps1(cmd_out) # 输出结束
                    # print('cmd_out:',cmd_out.encode('utf8'),code,subStr.encode('utf8'))
                    if code:
                        cmd_out_tmp = cmd_out.replace(subStr,'')
                        # print('cmd_out_tmp:',cmd_out_tmp.encode('utf8'))
                        if cmd_out_tmp not in ['\r\n', '']:
                            # print(cmd_out_tmp.encode('utf8'))
                            command_in = cmd_out_tmp.split('\r\n')[0]
                            command_out = '\n'.join(cmd_out_tmp.split('\r\n')[1:])
                            if command_in.startswith('vi') or command_in.startswith('nano'):
                                command_out = ''
                            logger.info({
                                'username': self.username,
                                'fullname': self.fullname,
                                'project': self.project,
                                'cluster': self.cluster,
                                'namespace': self.namespace,
                                'pod': self.pod,
                                'command_in': command_in,
                                'command_out': command_out,
                                })
                        cmd_out = ''
                    self.ws.send(stdout)

                if self.stream.peek_stderr():
                    stderr = self.stream.read_stderr()
                    self.ws.send(stderr)
            except Exception as err:
                logging.error('container stream err: {}'.format(err))
                self.ws.close()
                break