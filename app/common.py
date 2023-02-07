

import app.config as Config

# 判断命令是否在授权列表中
def is_allow_command(cmd):
    if cmd in Config.default_user_allow_command:
        return True
    # 允许了hostname，也允许hostna、hostnam等，兼容table键
    # 允许了ls，也允许bils、binls等，用户输入/bin/ls时，可能多次输入table键，兼容一下
    for c in Config.default_user_allow_command: 
        if c.startswith(cmd) or cmd.endswith(c):
            return True
    return False
