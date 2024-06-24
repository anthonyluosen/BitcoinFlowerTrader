import threading
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime
from utils import load_from_json

# unique_name = "5F7BE2B35311D3EF"
# url = 'https://www.okx.com/api/v5/copytrading/public-current-subpositions'
# params = {
#     'instType': 'SWAP',
#     'uniqueCode': f'{unique_name}'
# }
# response = requests.get(url=url, params=params)
# if response.status_code == 200:
#     data = json.loads(response.text)['data']
# print(data)
###############
# data = load_from_json("/root/copybybit/history/3b2qR0hOZux1S5oM9AuN2g_filled.json")
# if type(data)==dict:
#     pnl = data["pnl"]
# else:
#     pnl = sum(float(order["pnl"]) for order in data if "pnl" in order)
# print(pnl)


#######################################测试主程序####################################
# from main_v2 import COPYBot
# import log
# account_config =  {
#     "unique_name": "dbyqM0ao0cKOwNKUb%2BAQGQ",
#     "my_capital": 15,
#     "trader_capital": 21111,
#     "api_key": "90970ada-339b-4440-bc88-3f2ee45cea38",
#     "secret_key": "1F5D056ACFD9D2F6655CFC15BE2E0412",
#     "passphrase": "boyGOOD?1",
#     "sleep_interval": 1,
#     "min_usdt": 1.3,
#     "max_usdt": 2,
#     "total_buying" :3,
#     "trader_market":'bybit'
# }
# logPath = r"/root/copytrade/log"
# logger = log.Logger(account_config['unique_name'],logPath,remove = True)

# trading_bot = COPYBot(account_config, logger.info)
# data = trading_bot.bybitrade()
# print(data)
# trading_bot.start()
# 测试程序
import threading
import time

def fixed_program():
    print("Fixed program is running...")
    # 这里写你希望在程序停止后执行的逻辑
    time.sleep(5)
    print("Fixed program finished.")

def main():
    t = threading.Thread(target=fixed_program)
    t.start()

    # 在主程序中继续执行其他逻辑
    print("Main program is running...")
    time.sleep(3)
    print("Main program finished.")

    # 等待线程结束
    t.join()

if __name__ == "__main__":
    main()
