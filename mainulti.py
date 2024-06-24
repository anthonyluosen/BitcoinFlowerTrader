import os
import threading

import time
import json
import requests
import uuid

import REST
# import REST2
from REST4 import manage_position
from datetime import datetime
import pandas as pd
from okdata import calculate_quantity,calculate_margin,get_price_level
from utils import *
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bot import send_telegram_message
# 使用示例
bot_token = '7402994402:AAEz6h-p9az4uxLnvSgdNaVGVDv8lEg4sMk'
chat_id = '6848555062'


def get_swap_info():
    # OKX API endpoint for getting futures contracts information
    url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"

    # Create the request headers with API key and other required fields
    timestamp = str(int(time.time()))
    message = timestamp + 'GET' + '/api/v5/public/instruments?instType=SWAP'
    # signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

    headers = {
        # 'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
    }

    # Make the request
    response = requests.get(url, headers=headers)
    # response = session.get(url, headers=headers)

    # Check if the response is successful
    if response.status_code == 200:
        data = response.json()
        return data

    else:
        print(f"Error: {response.status_code}, {response.text}")
    return None
swap_info = get_swap_info()
minTrade = pd.DataFrame(swap_info['data']).set_index("instId")['minSz'].to_dict()
lot_size = pd.DataFrame(swap_info['data']).set_index("instId")['lotSz'].to_dict()
contract_value = pd.DataFrame(swap_info['data']).set_index("instId")['ctVal'].to_dict()

def update_pos(dic_trade,dic_my,instId,lever,mgnMode,subPos,sid,net = False,MyBuyNum = None):
    key = f'{instId}_{lever}_{sid}_{mgnMode}'
    MyBuyNum = float(MyBuyNum)
    if key not in dic_trade:
        dic_trade[key] = 0
        dic_my[key] = 0

    subPos = float(subPos)

    if net:
        dic_trade[key] -= abs(subPos)
        dic_my[key] -= MyBuyNum
    else:
        dic_trade[key] += abs(subPos)
        dic_my[key] += MyBuyNum
    dic_trade[key] = max(0,dic_trade[key])
    dic_my[key] = max(0,dic_my[key])
    return dic_trade,dic_my


def custom_round(value,name):
    return max(round(value), float(minTrade[name]))

def GetTraderdetail(printf, UserInfo, uniqueName, PositionSize ,This_Pos, Last_Pos, first_time,max_usdt,min_usdt,total_buying,Player_Pos,My_Pos):


    # 备份 This_Pos 为上一次获取的仓位
    Last_Pos = This_Pos.copy()

    url = 'https://www.okx.com/api/v5/copytrading/public-current-subpositions'

    # header = {"content-type": "application/json;charset=UTF-8"}
    min_usdt = float(min_usdt) # ! 最小的买入量
    max_usdt = float(max_usdt)
    limit = True # ! 是否限价下单
    
    params = {
        'instType': 'SWAP',
        'uniqueCode': f'{uniqueName}'
    }

    response = requests.get(url=url, params=params)
    # response = session.get(url=url, params=params)

    if response.status_code == 200:

        data = json.loads(response.text)['data']
        # 清空 This_Pos
        This_Pos = {}
        open_id = []
        net_id = []
        for item in data:
            
            My_Pos_ = My_Pos.copy()
            
            subPos = float(item['subPos'])  # 持仓量
            instId = item['instId']  # 交易货币
            instType = item['instType']
            openAvgPx = item['openAvgPx']  # 开仓均价
            lever = item['lever']  # 杠杆倍数
            mgnMode = item['mgnMode']
            posSide = item['posSide']  # 仓位类型
            subPosId = item['subPosId']  # 交易id
            # uTime = item['uTime']  # 时间
            Done = None
            # 将仓位信息添加到 This_Pos 字典
            This_Pos[subPosId] = {
                'subPos': subPos,
                'instId': instId,
                'openAvgPx': openAvgPx,
                'lever': lever,
                'mgnMode': mgnMode,
                'posSide': posSide,
                'subPosId': subPosId,
            }
            if instId in ["CEL-USDT-SWAP"]: # ! 不再购买这个币种 风险太大 todo：加入风险控制模块
                # print(f"不在买入该{instId}")
                continue
            if float(openAvgPx) > 0.00000001:

                # 如果交易ID在上一次的字典中没有，说明是新开仓
                if subPosId not in Last_Pos and not first_time:
                    print("检测到下单------------")
                    print(item)
                    
                    # ! 尝试计算下单下的张数并且计算保证金的大小 
                    # * todo 根据仓位和当前持有的资金取动态分配资金
                    MyBuyNum = custom_round(PositionSize * subPos,instId)
                    minquantity = calculate_quantity(instId,min_usdt,float(lever),lot_size[instId],contract_value[instId]) #
                    MyBuyNum = max(minquantity,MyBuyNum)
                    actual_margin = calculate_margin(MyBuyNum,instId,contract_value[instId],lever)
                    msg1 = f"{instId} 下单：{MyBuyNum}份,保证金：{actual_margin} 下单最大：{max_usdt} "
                    printf(msg1)

                    if actual_margin>max_usdt: # !单次下单的金额
                       printf("不再下单")
                       continue
                    if total_buying+actual_margin>min_usdt*5:  # ! 定义最大的购买
                        printf(f"跟单交易总额超出限制，当前合约保证金：{total_buying}")
                        continue
                    
                    if limit:
                        if (posSide == 'net' and float(subPos) > 0) or (posSide == 'long'):
                            
                            key = f'{instId}_{lever}_long_{mgnMode}'
                            if key in open_id:
                                printf(f'{key} 不在重新买入')
                                continue
                            open_id.append(key)
                            
                            msg = f'交易员 {uniqueName} 以单价{openAvgPx}U {lever}倍【买入开多】{instId} ,{subPos}张 ，我开{MyBuyNum}张'
                            printf(msg)
                            Player_Pos,My_Pos = update_pos(Player_Pos,My_Pos,instId,lever,mgnMode,subPos,"long",False,MyBuyNum)
                            if key in My_Pos:
                                if My_Pos[key]>MyBuyNum*2:
                                    printf("达到最大的持仓，停止买入")
                                    continue
                            # send_telegram_message(bot_token, chat_id, message_text)
                            printf("进入下单程序！！！！！！！！")
                            # threading.Thread(target=send_telegram_message, args=(bot_token, chat_id, msg)).start()
                            threading.Thread(target=manage_position, args=(printf, mgnMode, UserInfo, instId, "buy", "long", MyBuyNum, lever, mgnMode, uniqueName,"long",openAvgPx,str(uuid.uuid4()))).start() # * 建仓
                            send_telegram_message(bot_token, chat_id, msg)
                            time.sleep(0.2)
                        if (posSide == 'net' and float(subPos) < 0) or (posSide == 'short'):
                            
                            key = f'{instId}_{lever}_short_{mgnMode}'
                            if key in open_id:
                                printf(f'{key} 不在重新买入')
                                continue
                            open_id.append(key)
                            
                            msg = f'交易员 {uniqueName} 以单价{openAvgPx}U {lever}倍【卖出开空】{instId} ,{subPos}张 ，我开{MyBuyNum}张'
                            printf(msg)
                            Player_Pos,My_Pos = update_pos(Player_Pos,My_Pos,instId,lever,mgnMode,subPos,"short",False,MyBuyNum)
                            if key in My_Pos:
                                if My_Pos[key]>MyBuyNum*2:
                                    continue
                            # threading.Thread(target=send_telegram_message, args=(bot_token, chat_id, msg)).start() # * 建仓
                            threading.Thread(target=manage_position, args=(printf, mgnMode, UserInfo, instId, "sell", "short", MyBuyNum, lever, mgnMode, uniqueName,"short",openAvgPx,str(uuid.uuid4()))).start() # * 建仓
                            send_telegram_message(bot_token, chat_id, msg)
                            time.sleep(0.2)

 
                    # if Done:
                    total_buying += actual_margin
                    printf(f"当前跟单交易总量 {round(total_buying)} usdt")
                    print(Player_Pos,My_Pos)                        
            else:

                printf(f"币价小于0.00000001，不开单", 'black')
            
            # 遍历上一次的字典，判断平仓
        for subPosId in (Last_Pos if not first_time else []):
            # 如果交易ID在这一次的字典中没有，说明是平仓
            if subPosId not in This_Pos:
                printf("平仓单上次下的单-----------")
                print(Last_Pos[subPosId])
                closed_position = Last_Pos[subPosId]
                instId = closed_position["instId"]
                subPos = closed_position["subPos"]
                openAvgPx = closed_position["openAvgPx"]
                posSide = closed_position["posSide"]
                lever = closed_position["lever"]
                mgnMode = closed_position['mgnMode']

                MyBuyNum = custom_round(PositionSize * subPos,instId)
                minquantity = calculate_quantity(instId,min_usdt,float(lever),lot_size[instId],contract_value[instId]) #

                MyBuyNum = max(minquantity,MyBuyNum)
                actual_margin = calculate_margin(MyBuyNum,instId,contract_value[instId],lever)
                msg1 = f"{instId} 下单：{MyBuyNum},保证金：{actual_margin}"

                printf(msg1)
                Done = None
                # if actual_margin>max_usdt:
                    # print("平仓失败=====")
                    # print(Last_Pos[subPosId])
                    # continue 
                # ! 风控先设置在这里
                # margin_pct = REST.confirm(instId,actual_margin,"isolated")
                # print("占比多少=====",margin_pct)
                
                # ! to do 加入限价单的设置
                if limit:
                    if (posSide == 'net' and float(subPos) > 0) or (posSide == 'long'):
                        key = f'{instId}_{lever}_long_{mgnMode}'
                        msg = f'交易员 {uniqueName} 以单价{openAvgPx}U {lever}倍【卖出平多】{instId} ,{subPos}张 ，我平{MyBuyNum}张'
                        printf(msg)

                        if key in My_Pos:
                            if My_Pos[key]==0:
                                printf("无持仓，停止卖出平单！！")
                                continue
                            # if Player_Pos[key]==0 and My_Pos
                            
                        threading.Thread(target=manage_position, args=(printf, mgnMode, UserInfo, instId, "sell", "long", MyBuyNum, lever, mgnMode, uniqueName,"short",openAvgPx,str(uuid.uuid4()))).start() # * ping仓
                        send_telegram_message(bot_token, chat_id, msg)
                        time.sleep(0.2)
                        Player_Pos,My_Pos = update_pos(Player_Pos,My_Pos,instId,lever,mgnMode,subPos,"long",True,MyBuyNum)

                    if (posSide == 'net' and float(subPos) < 0) or (posSide == 'short'):
                        key = f'{instId}_{lever}_short_{mgnMode}'
                        msg = f'交易员 {uniqueName} 以单价{openAvgPx}U {lever}倍【买入平空】{instId} ,{subPos}张 ，我平{MyBuyNum}张'
                        printf(msg)
                        if key in My_Pos:
                            if My_Pos[key]==0:
                                printf("无持仓，停止卖出平单！！")
                                continue
                        threading.Thread(target=manage_position, args=(printf, mgnMode, UserInfo, instId, "buy", "short", MyBuyNum, lever, mgnMode, uniqueName,"long",openAvgPx,str(uuid.uuid4()))).start() # * ping仓
                        send_telegram_message(bot_token, chat_id, msg)
                        time.sleep(0.2)
                        Player_Pos,My_Pos = update_pos(Player_Pos,My_Pos,instId,lever,mgnMode,subPos,"short",True,MyBuyNum)

                # if Done:
                total_buying -= actual_margin
                print(Player_Pos,My_Pos)                        
    else:

        try:
            printf(f'检测故障(欧易原因)：{json.loads(response.text)["msg"]}')
        except:
            printf(f'检测故障(欧易原因)：{response.text}')

    first_time = False
    return This_Pos, Last_Pos, first_time, max_usdt, min_usdt, total_buying, Player_Pos, My_Pos

def start_trading(printf,account_config):
    
    unique_name = account_config['unique_name']
    my_capital = account_config['my_capital']
    trader_capital = account_config['trader_capital']
    api_key = account_config['api_key']
    secret_key = account_config['secret_key']
    passphrase = account_config['passphrase']
    sleep_interval = account_config['sleep_interval']
    min_usdt = account_config['min_usdt']
    max_usdt = account_config['max_usdt']    

    printf(f'启动成功, 监控交易员 {unique_name} : {unique_name}')

    printf(f'开始监控跟单：设置交易员 {unique_name} 本金：{trader_capital}U, 我的本金：{my_capital}U',)

    PositionSize = float(my_capital)/float(trader_capital)

    UserInfo = {
        'api_key': api_key,
        'secret_key': secret_key,
        'passphrase': passphrase
    }

    # 上一次获取的仓位字典
    Last_Pos = {}
    # 当前获取的仓位字典
    This_Pos = {}
    
    Player_Pos = {} # 根据对方调仓下的单
    My_Pos = {}
    
    # 首次获取的标志
    first_time = True
    total_buying = 0
    # start_button["text"] = "监控中..."
    
    while True:
        try:
            This_Pos, Last_Pos, first_time, max_usdt, min_usdt, total_buying, Player_Pos, My_Pos =\
                GetTraderdetail(printf, UserInfo, unique_name, PositionSize,This_Pos, Last_Pos, first_time,max_usdt,min_usdt,total_buying,Player_Pos,My_Pos)
            time.sleep(float(sleep_interval))
        except Exception as e:
            if 'Connection' in str(e):
                printf(f'连接欧易失败{datetime.now().time()} - 少量出现无视即可')
            else:
                printf(f'出错了，快联系开发人员:{e}')
            first_time = True


if __name__ == '__main__':
    import log
    # 读取 JSON 文件
    with open('/root/copytrade/copyers/config_readytouse.json', 'r') as file:
        config = json.load(file)
    logPath = r"/root/copytrade/logtest"
    # 遍历每组参数并传递给函数
    for account_name, account_config in config.items():
        # time.sleep(1)
        logger = log.Logger(account_config['unique_name'],logPath,remove = True)
        threading.Thread(target=start_trading, args=(logger.info,account_config )).start() # * ping仓
        # start_trading(print,account_config )


