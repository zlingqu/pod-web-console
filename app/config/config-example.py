auth_user = '_cmdb'
auth_key = '**'
auth_url = 'https://auth.nie.netease.com'
redis_post_user = ['_cc','quzhongling'] # redis的post接口，这些用户才可以调用
default_user = 'nguser' # 普通权限进入pod时用的用户名，进入容器前先检查并创建这个用户
white_users  = { # 可以定义一些用户免登录。格式支持角色组(sa、dev等)、用户名等
    "cc": {
        "group": ['cc.sa'],
        "user": ['']
    },
    "a19": {
        "group": ['a19.sa'],
        "user": ['']
    }
}
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
    kube_config_dict[k]['kube']['users'] = [{"user": {"token": ''},"name": "sa"}]

default_user_allow_command = [
    'ls','cd','cat','head','tail','less','curl','netstat','telnet',
    'nc', 'dig','ping','top','ps', 'grep','pwd','awk','ip','hostname',
    'host','uname','vim','vi','q','q!','x','wq','id','which','echo','pip',
    'source','history','clear','more'
]
# 防止websocket跨域攻击，https://zhuanlan.zhihu.com/p/61044032
origin_domain = [
    'endeavour.nie.netease.com',
    'play-endeavour.nie.netease.com'
]
REDIS = "redis://None@10.217.0.145:6379/1"