auth_user = '_cmdb'
auth_key = '***'
default_user = 'nguser' # 普通权限进入pod时用的用户名，进入容器前先检查并创建这个用户


kube_config_dict = {
    "2104": {
        "kube": {
            "clusters": [
                {
                    "cluster": {
                        "certificate-authority-data": "**",
                        "server": "https://10.**:10285"
                    }
                }
            ],
        },
        "project": 'cc',
    },
    "3213":{
            "kube": {
                "clusters": [
                    {
                        "cluster": {
                            "certificate-authority-data": "****",
                            "server": "https://7.*:10285"
                        }
                    }
                ]
            },
            "project": 'cc',
    },
}


default_user_allow_command = [
    'ls',
    'cd',
    'cat',
    'head',
    'tail',
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
    'id'
]


for k,v in kube_config_dict.items(): # 补全kube-config内容，token在调用时补充
    kube_config_dict[k]['kube']["apiVersion"] = "v1"
    kube_config_dict[k]['kube']["kind"] = 'Config'
    kube_config_dict[k]['kube']["current-context"] = "context1"
    kube_config_dict[k]['kube']["clusters"][0]['name'] = k
    kube_config_dict[k]['kube']['contexts']= [{
                                                    "context": {
                                                        "cluster": k,
                                                        "user": "sa"
                                                    },
                                                    "name": "context1"
                                                    }]
    kube_config_dict[k]['kube']['contexts'][0]['name'] = "context1"
    kube_config_dict[k]['kube']['users'] = [{
                                                        "user": {
                                                            "token": ''
                                                        },
                                                        "name": "sa"
                                                    }]



REDIS = "redis://127.0.0.1:6379/1"
