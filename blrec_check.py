from datetime import datetime, timedelta
from colorama import Fore, Style, init
import requests
from time import sleep
import traceback
import json
from reprint import output
from requests.exceptions import ConnectionError

init(autoreset=True)
url = ["http://172.24.100.53:2233", "http://172.24.100.53:2234"]
headers = {"x-api-key": "bili2233"}


def dt():
    t = datetime.now()
    return t.strftime("%Y-%m-%d %H:%M:%S") + "："


def is_aliving(idx):
    try:
        r = requests.get(
            url[idx] + "/api/v1/tasks/data",
            params={"select": "recorder_enabled"},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            j = json.loads(r.text)
            n = len(j)
            output_list[idx] = (
                Fore.LIGHTGREEN_EX
                + dt()
                + url[idx]
                + f" status:{r.status_code}, 监控数量:{n}"
                + Style.RESET_ALL
            )
            return n > 10
        else:
            output_list[idx] = (
                Fore.RED
                + dt()
                + url[idx]
                + f" status:{r.status_code}, msg:{r.text}"
                + Style.RESET_ALL
            )
            return False
    except BaseException as e:
        print(Fore.RED + dt() + f"出错：{type(e).__name__},{e}" + Style.RESET_ALL)
        if "No route to" in str(e):
            return True
        return False


def gotify_push(title, content, priority=6):
    """
    推送(pushplus)
    :title: 标题
    :content: 内容
    :url: 跳转地址
    :pic_url：图片地址
    """
    body = {
        "title": title,
        "message": content,
        "priority": priority,
        "extras": {
            "client::display": {"contentType": "text/markdown"},
        },
    }
    gotify_url = "122.51.216.147"
    gotify_token = "A8CtxyiSjO3-fmF"
    push_url = f"http://{gotify_url}/message?token={gotify_token}"
    try:
        response = requests.post(push_url, json=body)
        if response.status_code == 200:
            print(Fore.LIGHTGREEN_EX + dt() + "gotify推送成功" + Style.RESET_ALL)
        else:
            print(
                Fore.RED
                + dt()
                + f"gotify推送失败, code:{response.status_code}, msg:{response.text}"
                + Style.RESET_ALL
            )
    except BaseException as e:
        print(
            Fore.RED
            + dt()
            + f"gotify推送失败, 请求失败:{type(e).__name__},{e}"
            + Style.RESET_ALL
        )


def push_plus_push(title, content):
    """
    推送(pushplus)
    :title: 标题
    :content: 内容
    :url: 跳转地址
    :pic_url：图片地址
    """
    body = {
        "token": "95b0cc604b53407da802545810c9c7da",
        "title": f"{title}",
        "content": f"{content}",
        "template": "markdown",
    }
    push_url = "http://www.pushplus.plus/send/"
    response = requests.post(push_url, data=body)
    try:
        result = json.loads(str(response.content, "utf-8"))
    except json.JSONDecodeError as e:
        print(
            Fore.RED
            + dt()
            + f'解析content出错{e}\ncontent:{str(response.content, "utf-8")}'
            + Style.RESET_ALL
        )
        return
    if result["code"] == 200:
        print(Fore.LIGHTGREEN_EX + dt() + "pushplus推送成功" + Style.RESET_ALL)
    else:
        print(
            Fore.RED
            + dt()
            + f'pushplus推送失败, code:{result["code"]}, msg:{result["msg"]}'
            + Style.RESET_ALL
        )


cnt = 0
n = len(url)
with output(output_type="list", initial_len=n, interval=0) as output_list:
    while 1:
        for i in range(n):
            if not is_aliving(i):
                if url[i].endswith("34"):
                    title = "弹幕监控异常"
                else:
                    title = "录播监控异常"
                cnt += 1
                if cnt % 5 == 0:
                    gotify_push(title, "from tencent")
                if cnt % 10 == 0:
                    push_plus_push(title, "from tencent")
            else:
                cnt = 0
            sleep(30)
