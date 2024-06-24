import requests
import json
import os
import time
from datetime import datetime
import base64
import hmac
import hashlib
from requests.adapters import HTTPAdapter, Retry
import certifi
from REST import 撤销订单, 多空, 设置杠杆倍数, save_to_json
import threading
current_directory = os.path.dirname(os.path.realpath(__file__))

def get_price_level(symbol,n = 0):
    try:
        url = f"https://www.okx.com/api/v5/market/books?instId={symbol}&sz=5"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        data = json.loads(response.text)['data'][0]
        
        long_price = data['bids'][n][0]  # Third bid price
        short_price = data['asks'][n][0]  # Third ask price
        
        return long_price, short_price
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None, None
def choose_price(instId,n = 1,price_type = None):
    if price_type is None:
        raise "error"
    long_price, short_price = get_price_level(instId, n=n)
    if price_type =='short':
        return short_price
    return long_price
def check_current_price_valid(current_price,baseline,price_type,PositionSide = None):
    # ! 
    if price_type =='short' and PositionSide=="short": #做空
        if float(baseline)/float(current_price) -1 > 0.002:
            return False
    elif price_type =='long' and PositionSide=="long":
        if float(current_price)/float(baseline) -1 > 0.002:
            return False
    return True
    
class OKXClient:
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = 'https://www.okx.com'

    def _get_headers(self, method, request_path, body=''):
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        message = timestamp + method + request_path + body
        signature = base64.b64encode(hmac.new(self.secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest())

        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature.decode('utf-8'),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    def query_order_status(self, instId, ordId):
        method = 'GET'
        request_path = f'/api/v5/trade/order?instId={instId}&ordId={ordId}'
        headers = self._get_headers(method, request_path)
        response = requests.get(self.base_url + request_path, headers=headers, )
        # response = self.session.get(self.base_url + request_path, headers=headers, verify=certifi.where())
        if response.status_code == 200:
            data = response.json()
            return data['data'][0]['state'], data
        else:
            print(f'查询订单状态失败，原因:{response.text}')
            return None

    def place_order(self, body):
        method = 'POST'
        request_path = '/api/v5/trade/order'
        headers = self._get_headers(method, request_path, json.dumps(body))
        response = requests.post(self.base_url + request_path, headers=headers, data = json.dumps(body))

        # response = self.session.post(self.base_url + request_path, headers=headers, json=body, verify=certifi.where())
        if response.status_code == 200:
            data = response.json()
            if data['data'][0]['sMsg'] == 'Order placed':
                return data['data'][0]['ordId'], data
            else:
                print(f'委托失败, 原因：{data["data"][0]["sMsg"]}')
                return None, data
        else:
            print(f'委托错误，原因:{response.text}')
            return None, None
    def set_leverage(self, instId, lever, mgnMode, posSide=None):
        method = 'POST'
        request_path = '/api/v5/account/set-leverage'
        body = {
            "instId": instId,
            "lever": lever,
            'mgnMode': mgnMode
        }
        if mgnMode == "isolated" and posSide:
            body["posSide"] = posSide

        headers = self._get_headers(method, request_path, json.dumps(body))
        url = self.base_url + request_path
        
        response = requests.post(url, headers=headers, data=json.dumps(body))
        # print(response.text)
        if response.status_code == 200:
            msg = json.loads(response.text)['msg']
            if msg == "":
                data = json.loads(response.text)['data'][0]
                # print(data)
                # print('设置杠杆倍数成功')
                # print(f'产品ID：{data["instId"]}')
                # print(f'持仓方向：{data["posSide"]}')
                # print(f'杠杆倍数：{data["lever"]}')
                return 1
            else:
                print(f'设置杠杆倍数失败，原因:{response.text}','red')
                return 0
        else:
            print(f'设置杠杆倍数失败，原因:{response.text}','red')
            return 0

def check_order_status(client, printf, body, instId, ordId, initial_timeout=5, final_timeout=15,price_type = None,price_baseline = None):
    # ! todo:需要将当前价格和当时他购买的价格做区分，当前涨幅价格过高时取消该订单
    start_time = datetime.now()
    while True:
        elapsed_time = (datetime.now() - start_time).seconds

        if elapsed_time > final_timeout:
            printf(f'订单 {ordId} 在 {final_timeout} 秒内未成交，撤销挂单并重新挂单为市价单。', "black")
            撤销订单(client.api_key, client.secret_key, client.passphrase, instId, ordId)
            body["ordType"] = "market"
            px = choose_price(instId,n = 1,price_type = price_type)
            # ! 加入当前价格和买入对比价格的对比
            if check_current_price_valid(px,price_baseline,price_type,PositionSide = body['posSide']):
                place_and_monitor_order(client, printf, body, instId, price_type,price_baseline)
                break
            else:
                break

        if elapsed_time > initial_timeout:
            printf(f'订单 {ordId} 在 {initial_timeout} 秒内未成交，撤销挂单并重新挂单。', "black")
            撤销订单(client.api_key, client.secret_key, client.passphrase, instId, ordId)
        
            # 重新获取第一档价格
            px = choose_price(instId,n = 1,price_type = price_type)
            
            body["px"] = px
            # ! 加入当前价格和买入对比价格的对比
            if check_current_price_valid(px,price_baseline,price_type,PositionSide = body['posSide']):
                place_and_monitor_order(client, printf, body, instId, price_type,price_baseline)
                break

        state, data = client.query_order_status(instId, ordId)
        if state == 'filled':
            printf(f'订单 {ordId} 已成交。', "black")

            save_to_json(data['data'][0], os.path.join(current_directory,"history", f"{body['uniquename']}_filled.json"), mode='a')
            save_to_json(body, os.path.join(current_directory, "history",f"{body['uniquename']}.json"), mode='a')
            break
        elif state is None:
            break
        time.sleep(initial_timeout)

def place_and_monitor_order(client, printf, body, instId,price_type,initprice):
    
    ordId, data = client.place_order(body)
    if ordId:
        printf(f'{body["mode"]}{多空(body["posSide"])}委托成功, 订单id：{ordId} ' + datetime.now().strftime('%m/%d %H:%M:%S'), 'blue')
        check_order_status(client, printf, body, instId, ordId, 5, 15,price_type,initprice)

def manage_position(printf, mode, UserInfo, instId, side, posSide, sz='1', lever='5', tdMode='cross', unique_name="None", price_type=None,initprice = None):
    
    client = OKXClient(UserInfo['api_key'], UserInfo['secret_key'], UserInfo['passphrase'])
    if initprice is None:
        price = choose_price(instId,n = 1,price_type = price_type)
    else:
        price = initprice
    # if mode == '平' or 设置杠杆倍数(printf, UserInfo, instId, lever, tdMode, posSide):
    if mode == '平' or client.set_leverage(instId, lever, tdMode, posSide):

        body = {
            "instId": instId,
            "tdMode": tdMode,
            "ccy": "USDT",
            "reduceOnly": True,
            "side": side,
            "posSide": posSide,
            "ordType": "limit" if price else "market",
            "sz": sz,
            "px": price if price else None,
            "uniquename": unique_name,
            "lever": lever,
            "mode": mode
        }
        place_and_monitor_order(client, printf, body, instId,price_type,initprice)
    else:
        printf(f'开单设置杠杆倍数失败', 'Purple')

def main():

    UserInfo = {
    'api_key': "90970ada-339b-4440-bc88-3f2ee45cea38",
    'secret_key': "1F5D056ACFD9D2F6655CFC15BE2E0412",
    'passphrase': "boyGOOD?1"
}
    
    item ={'ccy': 'USDT', 'instId': 'PEPE-USDT-SWAP', 'instType': 'SWAP', 'lever': '10', 'margin': '16.314', 'markPx': '0.000016301', 'mgnMode': 'isolated', 'openAvgPx': '0.000016314', 'openTime': '1716724685525', 'posSide': 'short', 'subPos': '1', 'subPosId': '714930380709900288', 'uniqueCode': '2DF58532A9E97F53', 'upl': '0.13', 'uplRatio': '0.007968615912713'}
    subPos = float(item['subPos'])  # 持仓量
    instId = item['instId']  # 交易货币
    instType = item['instType']
    openAvgPx = item['openAvgPx']  # 开仓均价
    lever = item['lever']  # 杠杆倍数
    mgnMode = item['mgnMode']
    posSide = item['posSide']  # 仓位类型
    
    subPosId = item['subPosId']  # 交易id
    side = "buy"
    sz = 0.1
    tdMode= 'cross'
    unique_name = "测试"
    
    # manage_position(print, mgnMode, UserInfo, instId, "sell", posSide, sz, lever, tdMode, unique_name,"short") # * 建仓
    # manage_position(print, mgnMode, UserInfo, instId, "buy", posSide, sz, lever, tdMode, unique_name,"long") # * 平仓
    threading.Thread(target=manage_position, args=(print, mgnMode, UserInfo, instId, "sell", posSide, sz, lever, tdMode, unique_name,"short")).start() # * 建仓
    # threading.Thread(target=manage_position, args=(print, mgnMode, UserInfo, instId, "buy", posSide, sz, lever, tdMode, unique_name,"long")).start()

# 运行主函数
if __name__ == "__main__":
    main()


