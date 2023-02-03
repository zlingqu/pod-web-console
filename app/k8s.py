from kubernetes import client, config
from kubernetes.stream import stream
import logging
import threading
import json,re
import app.config as Config
import app.log as Log
from flask import session

logger = Log.get_logger()

class k8s_client(object):
    def __init__(self, region, is_root):
        if not Config.kube_config_dict.get(str(region),''): # region输入错误
            return None
        config.load_kube_config_from_dict(config_dict=Config.kube_config_dict.get(str(region),'')['kube'])
        self.region = region
        self.is_root = is_root
        self.project = Config.kube_config_dict[region]['project']
        self.client_core_v1 = client.CoreV1Api()

    def get_ns(self):
        ret = self.client_core_v1.list_namespace()
        result = [ ns.metadata.name for ns in ret.items ]
        return result

    def terminal_start(self, namespace, pod, container, cols, rows):
        if self.is_root:
            command = [ #默认是项目用户
            "/bin/sh",
            "-c",
            '''[ -x /bin/bash ] && su - {0} && exec /bin/bash || su - {0} && exec /bin/sh'''.format(self.project)
            ]
        else:
            command = [
            "/bin/sh",
            "-c",
            '''(id {0} > /dev/null 2>&1 || useradd -m {0} > /dev/null 2>&1 || adduser -D {0} ) || \
            [ -x /home/{0}/.bashrc ] && \
            sed -i '/alias ls=/d' /home/{0}/.bashrc && \
            sed -i 's/xterm*\|rxvt*/xxxterm/g' /home/{0}/.bashrc && \
            (su - {0} && exec /bin/bash || su - {0} && exec /bin/sh) \
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

    def __init__(self, ws, container_stream, region, namespace, pod, username, fullname):
        super(k8s_stream_thread, self).__init__()
        self.ws = ws
        self.stream = container_stream
        self.project = Config.kube_config_dict[region]['project']
        self.region = region
        self.namespace = namespace
        self.pod = pod
        self.username = username
        self.fullname = fullname
        # nguser@jeventproxynew-7776d48b44-sxvdg:~$
        # root@jeventproxynew-7776d48b44-sxvdg:/var/log#
        self.ps1 = '[\w].*@' + self.pod + ':[~/\w].*[\$#]{1}\s'
    
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
                    # print('cmd_out:',cmd_out,code,subStr)
                    if code:
                        cmd_out_tmp = cmd_out.replace(subStr,'')
                        if cmd_out_tmp not in ['\r\n', '']:
                            # print(cmd_out_tmp)
                            command_in = cmd_out_tmp.split('\r\n')[0]
                            command_out = '\n'.join(cmd_out_tmp.split('\r\n')[1:])
                            if command_in.startswith('vi') or command_in.startswith('nano'):
                                command_out = ''
                            logger.info({
                                'username': self.username,
                                'fullname': self.fullname,
                                'project': self.project,
                                'region': self.region,
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