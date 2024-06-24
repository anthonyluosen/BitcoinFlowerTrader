import hashlib
import hmac
import time
import requests
import json
# Function to get the third price level
def get_swap_info():
    url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"
    timestamp = str(int(time.time()))
    message = timestamp + 'GET' + '/api/v5/public/instruments?instType=SWAP'
    headers = {'OK-ACCESS-TIMESTAMP': timestamp}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error: {response.status_code}, {response.text}")
    return None

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
    
def get_current_price(inst_id):
    url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return float(data['data'][0]['last'])
    else:
        print(f"Error fetching price: {response.status_code}, {response.text}")
        return None
    
def calculate_quantity(inst_id, order_amount_usdt, leverage,lotsize,contract_value):
    current_price = get_current_price(inst_id)
    if current_price:
        quantity = order_amount_usdt / current_price *float(leverage) / float(contract_value)
        rounded_quantity = round_quantity_to_lot_size(quantity, lotsize)
        return rounded_quantity
    return None 

def round_quantity_to_lot_size(quantity, lot_size):
    
    if lot_size=="0.1":
        round_num = 2
        lot_size = float(lot_size)
    if lot_size=="1":
        round_num = 1
        lot_size = int(lot_size)
    if lot_size=="0.01":
        round_num = 3
        lot_size = float(lot_size)
    rounded_quantity = round(quantity / lot_size) * lot_size
    return round(rounded_quantity,round_num)

def calculate_margin(MyBuyNum,instId,contract_value,lever):
    position_value = MyBuyNum * get_current_price(instId) * float(contract_value)
    actual_margin = position_value / float(lever)
    return actual_margin