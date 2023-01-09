from kubernetes import client, config
from kubernetes.stream import stream
import logging
import threading
import json

class k8s_client(object):
    def __init__(self, region):
        import app.config as Config
        if not Config.kube_config_dict.get(str(region),''): # region输入错误
            return None
        config.load_kube_config_from_dict(config_dict=Config.kube_config_dict.get(str(region),''))
        self.client_core_v1 = client.CoreV1Api()

    def get_ns(self):
        ret = self.client_core_v1.list_namespace()
        result = [ ns.metadata.name for ns in ret.items ]
        return result

    def terminal_start(self, namespace, pod, container, cols, rows):
        command = [
            "/bin/sh",
            "-c",
            'TERM=xterm-256color; export TERM; [ -x /bin/bash ] '
            '&& ([ -x /usr/bin/script ] '
            '&& /usr/bin/script -q -c "/bin/bash" /dev/null || exec /bin/bash) '
            '|| exec /bin/sh']

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
                    stdout = self.stream.read_stdout()
                    self.ws.send(stdout)

                if self.stream.peek_stderr():
                    stderr = self.stream.read_stderr()
                    self.ws.send(stderr)
            except Exception as err:
                logging.error('container stream err: {}'.format(err))
                self.ws.close()
                break