from urllib.parse import urlencode 
from flask import request
import requests

def redirect_url(root_url, next_url):
    # Step 1
    # 1. 第一步进行关联（associate）操作

    associate_data = {
        'openid.mode' : 'associate',
        'openid.assoc_type' : 'HMAC-SHA256', # OpenID消息签名算法
        'openid.session_type' : 'no-encryption',
    }
    
    associate_data = urlencode(associate_data).encode('utf-8')
    # print(associate_data)
    assoc_dict = {}
    assoc_resp = requests.post(url='https://login.netease.com/openid/', params=associate_data).text

    # OpenID Server会以行为单位，分别换回如下内容：
    # assoc_handle:{HMAC-SHA256}{5279ff11}{w6nbEA==}
    # expires_in:86400
    # mac_key:g5PWpAb+pbwuTTGDt+95tWKRxN5RAhxDjpqHGwZ2OWw=
    # assoc_type:HMAC-SHA256
    # 这些值需要存储在session或者其它地方，当用户跳转回后，需要使用这些数据校验签名
    for line in assoc_resp.split('\n'):
        if line:
            k, v = line.split(":")
            assoc_dict[k] = v
    
    # Step 2
    # 构造重定向URL，发起请求认证
    # 已经associate完成，构造checkid_setup的内容（请求认证）

    if request.args: #如果带了参数，则将追加到next_url中
        next_arg = {}
        for key in request.args:
            next_arg[key] = request.args.get(key)
        next_url = next_url + '?' + urlencode(next_arg)

    redirect_data = {
        'openid.ns' : 'http://specs.openid.net/auth/2.0', # 固定字符串
        'openid.mode' : 'checkid_setup', # 固定字符串
        'openid.assoc_handle' : assoc_dict['assoc_handle'], # 第一步获取的assoc_handle值
        'openid.return_to' : root_url + 'terminal/login_callback?' + urlencode({'next': next_url}), # 当用户在OpenID Server登录成功后，你希望它跳转回来的地址
        'openid.claimed_id' : 'http://specs.openid.net/auth/2.0/identifier_select', # 固定字符串
        'openid.identity' : 'http://specs.openid.net/auth/2.0/identifier_select', # 固定字符串
        'openid.realm' : root_url, # 应用站点的URL地址，通常这个URL要能覆盖 openid.return_to 设定的URL。如 openid.realm 为：http://demo.163.com/login/，那么 openid.return_to 一定需要以 http://demo.163.com/login/ 开始。
        'openid.ns.sreg' : 'http://openid.net/extensions/sreg/1.1', # 固定字符串
        'openid.sreg.required' : "nickname,email,fullname", # 三个可以全部要求获取，或者只要求一个
    }
    redirect_data = urlencode(redirect_data)


    #实际应用中，需要交由浏览器进行Redirect的URL，用户在这里完成交互认证
    return "https://login.netease.com/openid/?" + redirect_data, assoc_dict['mac_key']