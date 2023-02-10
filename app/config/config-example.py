
auth_user = '_cmdb'
auth_key = '***'
default_user = 'nguser' # 普通权限进入pod时用的用户名，进入容器前先检查并创建这个用户
kube_config_dict = {
    "3214": {
        "certificate-authority-data": "***",
        "server": "https://7.***:10285",
        "project": 'cc',
    },
    "3226": {
        "certificate-authority-data": "**",
        "server": "https://10.***:10285",
        "project": 'a19',
    },
    "3407": {
        "certificate-authority-data": "***",
        "server": "https://10.**:10285",
        "project": 'opd',
    }
}


for k,v in kube_config_dict.items(): #补全kube-config内容，其中token在调用时生成
    kube_config_dict[k]['kube'] = {}
    kube_config_dict[k]['kube']["apiVersion"] = "v1"
    kube_config_dict[k]['kube']["kind"] = 'Config'
    kube_config_dict[k]['kube']["current-context"] = "context1"
    kube_config_dict[k]['kube']["clusters"] = [{
                                                'name': k,
                                                "cluster": {
                                                    "certificate-authority-data": kube_config_dict[k]['certificate-authority-data'],
                                                    "server": kube_config_dict[k]['server']
                                                }
                                            }]
    kube_config_dict[k]['kube']['contexts']= [{
                                                "context": {
                                                    "cluster": k,
                                                    "user": "sa"
                                                },
                                                "name": "context1"
                                            }]
    kube_config_dict[k]['kube']['users'] = [{
                                                "user": {
                                                    "token": ''
                                                },
                                                "name": "sa"
                                            }]



default_user_allow_command = [
    'ls',
    'cd',
    'cat',
    'head',
    'tail',
    'less',
    'curl',
    'netstat',
    'telnet',
    'nc',
    'dig',
    'ping',
    'top',
    'ps', 
    'grep',
    'pwd',
    'awk',
    'ip',
    'hostname',
    'host',
    'uname',
    'vim',
    'vi',
    'q',
    'q!',
    'x',
    'wq',
    'id',
    'which',
    'echo',
    'pip',
    'source',
    'history'
]

REDIS = "redis://127.0.0.1:6379/1"