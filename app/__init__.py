"""
应用包入口。

说明：
- 该项目以“常驻进程 + APScheduler 定时”的方式运行；
- Linux 上通常通过 systemd/Docker 仅做保活，不使用系统层面 cron。
"""


