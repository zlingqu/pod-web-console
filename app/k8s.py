from kubernetes import client, config
from kubernetes.stream import stream
import logging
import threading
import json
import app.config as Config

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
            '''TERM=xterm-256color; export TERM; [ -x /bin/bash ] && ([ -x /usr/bin/script ] && /usr/bin/script -q -c "su - {0} && /bin/bash" || su - {0} && exec /bin/bash) || su - {0} && exec /bin/sh'''.format(self.project)
            ]
        else:
            command = [
            "/bin/sh",
            "-c",
            '''TERM=xterm-256color; export TERM; (id {0} > /dev/null 2>&1 || useradd -m {0} > /dev/null 2>&1 || adduser -D {0} ) || \
            [ -x /bin/bash ] \
            && ([ -x /usr/bin/script ] && /usr/bin/script -q -c "su - {0} && exec /bin/bash" || su - {0} && exec /bin/bash) \
            && su - {0} && exec /bin/sh \
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

    def __init__(self, ws, container_stream):
        super(k8s_stream_thread, self).__init__()
        self.ws = ws
        self.stream = container_stream

    def run(self):
        while not self.ws.closed:

            if not self.stream.is_open():
                logging.info('container stream closed')
                self.ws.close()

            try:
                if self.stream.peek_stdout():
                    stdout = self.stream.read_stdout(timeout=3)
                    self.ws.send(stdout)

                if self.stream.peek_stderr():
                    stderr = self.stream.read_stderr()
                    self.ws.send(stderr)
            except Exception as err:
                logging.error('container stream err: {}'.format(err))
                self.ws.close()
                break