# 查看命中进程	
pgrep -af '[.]vscode-server'
# 正常结束	
pkill -f '[.]vscode-server'
# 强制结束	
pkill -9 -f '[.]vscode-server'