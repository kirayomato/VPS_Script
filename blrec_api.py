from datetime import datetime, timedelta
from colorama import Fore, Style, init
import requests
from time import sleep
import traceback

init(autoreset=True)
url = "http://localhost:2233"
headers = {"x-api-key": "bili2233"}


def dt():
    t = datetime.now()
    return t.strftime("%Y-%m-%d %H:%M:%S") + "："


def is_recording():
    try:
        r = requests.get(
            url + "/api/v1/tasks/data",
            params={"select": "recording"},
            headers=headers,
            timeout=3,
        )
        if r.status_code == 200:
            return r.text != "[]"
        else:
            print(
                Fore.RED
                + dt()
                + f"status:{r.status_code}, msg:{r.text}"
                + Style.RESET_ALL
            )
            return True
    except BaseException as e:
        print(Fore.RED + f"出错【{e}】：{traceback.format_exc()}" + Style.RESET_ALL)
        return True


while 1:
    flag = 1
    t = datetime.now()
    if t.hour < 12:
        t0 = datetime(t.year, t.month, t.day, 12, 55)
    else:
        t0 = datetime(t.year, t.month, t.day, 0, 55) + timedelta(days=1)
    t1 = (t0 - t).total_seconds()
    print(Fore.LIGHTBLUE_EX + dt() + f"Sleep for {t1:.2f} seconds" + Style.RESET_ALL)
    sleep(t1)
    while is_recording():
        if flag:
            print(Fore.YELLOW + dt() + "Wait for Recoding End! " + Style.RESET_ALL)
            flag = 0
        sleep(60)
    sleep(60)
    while 1:
        try:
            r = requests.post(url + "/api/v1/app/restart", headers=headers, timeout=3)
            if r.status_code == 200:
                print(Fore.GREEN + dt() + r.text + Style.RESET_ALL)
                break
            else:
                print(
                    Fore.RED
                    + dt()
                    + f"status:{r.status_code}, msg:{r.text}"
                    + Style.RESET_ALL
                )
        except BaseException as e:
            print(Fore.RED + f"出错【{e}】：{traceback.format_exc()}" + Style.RESET_ALL)
        sleep(60)
