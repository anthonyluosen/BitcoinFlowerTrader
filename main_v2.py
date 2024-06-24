import os
import threading
import time
import json
import requests
import uuid
from datetime import datetime
import pandas as pd
from okdata import calculate_quantity, calculate_margin, get_price_level, get_swap_info
from bot import send_telegram_message
from REST4 import manage_position
from utils import update_pos
import log
# 使用示例
bot_token = '7402994402:AAEz6h-p9az4uxLnvSgdNaVGVDv8lEg4sMk'
chat_id = '6848555062'

class COPYBot(threading.Thread):
    def __init__(self, account_config, printf,):
        super(COPYBot,self).__init__()
        self.account_config = account_config
        self.printf = printf
        self.unique_name = account_config['unique_name']
        self.my_capital = account_config['my_capital']
        self.trader_capital = account_config['trader_capital']
        self.sleep_interval = account_config['sleep_interval']
        self.min_usdt = float(account_config['min_usdt'])
        self.max_usdt = float(account_config['max_usdt'])
        self.PositionSize = float(self.my_capital) / float(self.trader_capital) # ! 全比例跟单设计的参数
        self.UserInfo = {
            'api_key': account_config['api_key'],
            'secret_key': account_config['secret_key'],
            'passphrase': account_config['passphrase']
        }
        if 'maxlever' in account_config:
            self.max_l = bool(account_config['maxlever'])
        else: self.max_l = False
        self.get_basic()
        self.Last_Pos = {}
        self.This_Pos = {}
        self.Player_Pos = {}
        self.My_Pos = {}
        self.first_time = True
        self.total_buying = 0
        if account_config['trader_market'] in ['bybit']:
            self.session = requests.Session()
        else:
            self.session = None
        self.trader_market = account_config['trader_market'] # "bybit" "okx"

    def run(self):
        send_telegram_message(bot_token, chat_id, f'启动成功, 监控交易员 {self.unique_name}')
        while True:
            try:
                self.GetTraderdetail()
                time.sleep(float(self.sleep_interval))
            except Exception as e:
                if 'Connection' in str(e):
                    self.printf(f'连接欧易失败{datetime.now().time()} - 少量出现无视即可')
                else:
                    self.printf(f'交易员跟单 {self.unique_name} 出错了，快联系开发人员:{e}', exc_info=True)
                    send_telegram_message(bot_token, chat_id, f'交易员跟单 {self.unique_name} 出错了，快联系开发人员:{e}')
                self.first_time = True
    
    def get_copyer_data(self,):
        if self.trader_market=="okx":
            data = self.okxtrade()
        elif self.trader_market=="bybit":
            data = self.bybitrade()
        return data
    
    def GetTraderdetail(self,):
        # 获取数据先
        data = self.get_copyer_data()
        if data is None:
            return
        
        self.Last_Pos = self.This_Pos.copy()
        self.This_Pos = {}
        open_id = []
        net_id = []
        for item in data:
            if self.trader_market=='bybit':
                subPos = float(item['sizeX'])/100000000
                instId = f"{item['symbol'][:-4].upper()}-USDT-SWAP"
                if instId not in self.lot_size:
                    self.printf(f"{instId} 在okx并不能交易.")
                    continue
                lever = int(item['leverageE2'])/100
                mgnMode = "isolated" if item['isIsolated'] else "cross"
                posSide = "long" if item['side']=="Buy" else "short"
                subPosId = item['crossSeq']
                openAvgPx = item['entryPrice']

            elif self.trader_market=='okx':
                subPos = float(item['subPos'])
                instId = item['instId']
                openAvgPx = item['openAvgPx']
                lever = item['lever']  
                mgnMode = item['mgnMode']
                posSide = item['posSide']
                subPosId = item['subPosId']
            # *是否最大杠杆下单
            if self.max_l and (mgnMode != "isolated") and (instId in self.max_lever):
                lever = self.max_lever[instId]
            
            self.This_Pos[subPosId] = {
                'subPos': subPos,
                'instId': instId,
                'openAvgPx': openAvgPx,
                'lever': lever,
                'mgnMode': mgnMode,
                'posSide': posSide,
                'subPosId': subPosId,
            }
            if instId in ["CEL-USDT-SWAP"]:
                continue

            if float(openAvgPx) > 0.00000001:
                if subPosId not in self.Last_Pos and not self.first_time:
                    MyBuyNum = self.custom_round(self.PositionSize * subPos, instId)
                    minquantity = calculate_quantity(instId, self.min_usdt, float(lever), self.lot_size[instId], self.contract_value[instId])
                    print(MyBuyNum,minquantity)
                    MyBuyNum = max(minquantity, MyBuyNum)
                    actual_margin = calculate_margin(MyBuyNum, instId, self.contract_value[instId], lever)
                    self.printf( f"{instId} 下单: {MyBuyNum}份,保证金: {actual_margin} 下单最大: {self.max_usdt}")
                    if actual_margin > self.max_usdt:
                        self.printf("不再下单")
                        continue
                    if self.total_buying + actual_margin > self.min_usdt * 5:
                        self.printf(f"跟单交易总额超出限制，当前合约保证金: {self.total_buying}")
                        continue
                    
                    if (posSide == 'net' and float(subPos) > 0) or (posSide == 'long'):
                        key = f'{instId}_{lever}_long_{mgnMode}'
                        if key in open_id:
                            self.printf(f'{key} 不在重新买入')
                            continue
                        open_id.append(key)
                        msg = f'交易员 {self.unique_name} 以单价{openAvgPx}U {lever}倍【买入开多】{instId} ,{subPos}张 ，我开{MyBuyNum}张'
                        self.printf(msg)
                        self.Player_Pos, self.My_Pos = update_pos(self.Player_Pos, self.My_Pos, instId, lever, mgnMode, subPos, "long", False, MyBuyNum)
                        if key in self.My_Pos:
                            if self.My_Pos[key] > MyBuyNum * 2:
                                self.printf("达到最大的持仓，停止买入")
                                continue
                        threading.Thread(target=manage_position, args=(self.printf, mgnMode, self.UserInfo, instId, "buy", "long", MyBuyNum, lever, mgnMode, self.unique_name, "long", openAvgPx, str(uuid.uuid4()))).start()
                        send_telegram_message(bot_token, chat_id, msg)
                        time.sleep(0.2)
                    if (posSide == 'net' and float(subPos) < 0) or (posSide == 'short'):
                        key = f'{instId}_{lever}_short_{mgnMode}'
                        if key in open_id:
                            self.printf(f'{key} 不在重新买入')
                            continue
                        open_id.append(key)
                        msg = f'交易员 {self.unique_name} 以单价{openAvgPx}U {lever}倍【卖出开空】{instId} ,{subPos}张 ，我开{MyBuyNum}张'
                        self.printf(msg)
                        self.Player_Pos, self.My_Pos = update_pos(self.Player_Pos, self.My_Pos, instId, lever, mgnMode, subPos, "short", False, MyBuyNum)
                        if key in self.My_Pos:
                            if self.My_Pos[key] > MyBuyNum * 2:
                                continue
                        threading.Thread(target=manage_position, args=(self.printf, mgnMode, self.UserInfo, instId, "sell", "short", MyBuyNum, lever, mgnMode, self.unique_name, "short", openAvgPx, str(uuid.uuid4()))).start()
                        send_telegram_message(bot_token, chat_id, msg)
                        time.sleep(0.2)
                    self.total_buying += actual_margin
                    self.printf(self.Player_Pos)  
                    self.printf(self.My_Pos) 
                    
            # 遍历上一次的字典，判断平仓

        for subPosId in (self.Last_Pos if not self.first_time else []):
            # 如果交易ID在这一次的字典中没有，说明是平仓
            if subPosId not in self.This_Pos:
                self.printf("平仓单上次下的单")
                closed_position = self.Last_Pos[subPosId]
                instId = closed_position["instId"]
                subPos = closed_position["subPos"]
                openAvgPx = closed_position["openAvgPx"]
                posSide = closed_position["posSide"]
                lever = closed_position["lever"]
                mgnMode = closed_position['mgnMode']
                # *是否最大杠杆下单
                if self.max_l and (mgnMode != "isolated") and (instId in self.max_lever):
                    lever = self.max_lever[instId]
                    
                MyBuyNum = self.custom_round(self.PositionSize * subPos,instId)
                minquantity = calculate_quantity(instId,self.min_usdt,float(lever),self.lot_size[instId],self.contract_value[instId]) #

                MyBuyNum = max(minquantity,MyBuyNum)
                actual_margin = calculate_margin(MyBuyNum,instId,self.contract_value[instId],lever)
                self.printf(f"{instId} 下单: {MyBuyNum},保证金: {actual_margin}")
                # ! 风控先设置在这里
                # ! to do 加入限价单的设置
                # *检测 有无仓位可平,避免平其他交易员的单
                if (posSide == 'net' and float(subPos) > 0) or (posSide == 'long'):
                    sid = "long"
                if (posSide == 'net' and float(subPos) < 0) or (posSide == 'short'):
                    sid = "short"
                key = f'{instId}_{lever}_{sid}_{mgnMode}'
                if (key in self.My_Pos ) and (self.My_Pos[key]==0):
                    continue
                
                if (posSide == 'net' and float(subPos) > 0) or (posSide == 'long'):
                    
                    msg = f'交易员 {self.unique_name} 以单价{openAvgPx}U {lever}倍【卖出平多】{instId} ,{subPos}张 ，我平{MyBuyNum}张'
                    self.printf(msg)
                    threading.Thread(target=manage_position, args=(self.printf, mgnMode, self.UserInfo, instId, "sell", "long", MyBuyNum, lever, mgnMode, self.unique_name,"short",openAvgPx, str(uuid.uuid4()))).start() # * ping仓
                    time.sleep(0.2)
                    self.Player_Pos,self.My_Pos = update_pos(self.Player_Pos,self.My_Pos,instId,lever,mgnMode,subPos,"long",True,MyBuyNum)
                    send_telegram_message(bot_token, chat_id, msg)
                if (posSide == 'net' and float(subPos) < 0) or (posSide == 'short'):
                    msg = f'交易员 {self.unique_name} 以单价{openAvgPx}U {lever}倍【买入平空】{instId} ,{subPos}张 ，我平{MyBuyNum}张'
                    self.printf(msg)
                    
                    threading.Thread(target=manage_position, args=(self.printf, mgnMode, self.UserInfo, instId, "buy", "short", MyBuyNum, lever, mgnMode, self.unique_name,"long",openAvgPx, str(uuid.uuid4()))).start() # * ping仓
                    time.sleep(0.2)
                    self.Player_Pos,self.My_Pos = update_pos(self.Player_Pos,self.My_Pos,instId,lever,mgnMode,subPos,"short",True,MyBuyNum)
                    send_telegram_message(bot_token, chat_id, msg)
                self.total_buying -= actual_margin
                self.printf(self.Player_Pos)
                self.printf(self.My_Pos)  
        self.first_time = False
    def bybitrade(self,):
        # 定义要添加的cookie
        cookies = {
            'bm_sz': '09AA269C6E57EBDE93C9FC195E06CF29~YAAQ6MzVF27vRA+QAQAAesAnGhgoUdJI2EFaxoBumF2rUQo3qRgF2HmXFe+Ro2PAyS8AqOrWcxWS/77SOoqIWBpNuBWsW78amrsGZfXvYumBwVqz4Rb6yKE8rc5VZGnJoJbFfhTtkoYwfXSfHS4+MWSS2Q34koxlGrclBVkMEigTDShidh9GqNlncvc7aUE/+oa7mEYIdPdwu1Leeuhm4VnREMZ21z9oSFkUtlxf3/XrtI9vxntyNDPmLoCvvox3Q4SqDGVqL61Zs+mV2ZzbvuTv6QFxSFmVH1mfpggLMx467v09mJKIKng1YdcmrW8hOUvLpjYVh6UnOJJJ/rxKFl9yi3YhywDdyLviBGDTIBnkGC04BuK4gqxzPPnO7uQgJn8ALwF179pSv/1n~3354676~3617847'
        }
        current_milliseconds = int(time.time() * 1000)
        url = f"https://api2.bybit.com/fapi/beehive/public/v1/common/order/list-detail?timeStamp={current_milliseconds}&leaderMark={self.unique_name}%3D%3D" #带订单的持仓
        # url = f'https://api2.bybit.com/fapi/beehive/public/v1/common/position/list?timeStamp={current_milliseconds}&leaderMark={self.unique_name}%3D%3D' #全局持仓
        response = self.session.get(url, cookies=cookies) # !目前只有这个可以
        # response = response.get(url,cookies = cookies)
        if response.status_code == 200:
            data = response.json()['result']['data']
            return data
        return 
    def okxtrade(self,):
        url = 'https://www.okx.com/api/v5/copytrading/public-current-subpositions'
        params = {
            'instType': 'SWAP',
            'uniqueCode': f'{self.unique_name}'
        }
        response = requests.get(url=url, params=params)
        if response.status_code == 200:
            data = json.loads(response.text)['data']
            return data
        return 
    
    def get_basic(self,):
        swap_info = get_swap_info()
        data = pd.DataFrame(swap_info['data']).set_index("instId")
        self.minTrade = data['minSz'].to_dict()
        self.lot_size = data['lotSz'].to_dict()
        self.contract_value = data['ctVal'].to_dict()
        self.max_lever = data['lever'].to_dict()

    def custom_round(self,value, name):
        return max(round(value), float(self.minTrade[name]))

def start_trading(account_config, printf):
    trading_bot = TradingBot(account_config, printf)
    trading_bot.start()
    return trading_bot

if __name__ =="__main__":
    # 使用示例
    with open('/root/BBC/copyers/bb.json', 'r') as file:
        config = json.load(file)
    # 遍历每组参数并传递给函数
    for account_name, account_config in config.items():
        
        logPath = r"/root/BBC/copybybit"
        logger = log.Logger(account_config['unique_name'],logPath,remove = True)
        trading_bot = COPYBot(account_config, logger.info)
        trading_bot.start()
        time.sleep(4)
