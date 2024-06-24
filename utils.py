import json
import os
import configparser

def update_pos(dic_trade, dic_my, instId, lever, mgnMode, subPos, sid, net=False, MyBuyNum=None):
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
    dic_trade[key] = max(0, dic_trade[key])
    dic_my[key] = max(0, dic_my[key])
    return dic_trade, dic_my

def joinpath(*path):
    return os.path.realpath(os.path.join(*path))


def save_config(unique_name, my_capital, trader_capital, api_key, secret_key, passphrase, sleep_interval, Openbrowser):
    config = configparser.ConfigParser()
    config['Settings'] = {
        'UniqueName': unique_name,
        'MyCapital': my_capital,
        'TraderCapital': trader_capital,
        'ApiKey': api_key,
        'SecretKey': secret_key,
        'Passphrase': passphrase,
        'SleepInterval': sleep_interval,
        'Openbrowser': Openbrowser,
    }

    with open('config.ini', 'w') as configfile:
        config.write(configfile)

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    print(config['Settings'])
    if 'Settings' in config:
        settings = config['Settings']
        return (
            settings.get('UniqueName', ''),
            settings.get('MyCapital', ''),
            settings.get('TraderCapital', ''),
            settings.get('ApiKey', ''),
            settings.get('SecretKey', ''),
            settings.get('Passphrase', ''),
            settings.get('SleepInterval', ''),
            settings.get('Openbrowser', ''),
        )
    else:
        return '', '', '', '', '', '', ''



# Function to save data to a JSON file with mode
def save_to_json(data, file_path, mode='w'):
    if mode == 'a' and os.path.exists(file_path):
        # Load existing data
        with open(file_path, 'r') as file:
            existing_data = json.load(file)
        
        # Ensure existing data is a list
        if not isinstance(existing_data, list):
            existing_data = [existing_data]
        
        # Append new data
        if isinstance(data, list):
            existing_data.extend(data)
        else:
            existing_data.append(data)
        
        # Save combined data back to file
        with open(file_path, 'w') as file:
            json.dump(existing_data, file, indent=4)
    else:
        # Save data to file (overwrite or new file)
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    
    # print(f"Data saved to {file_path} with mode '{mode}'")

# Function to load data from a JSON file
def load_from_json(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return None

    with open(file_path, 'r') as file:
        data = json.load(file)
    # print(f"Data loaded from {file_path}")
    return data

# Example usage
if __name__ == "__main__":
    # Example data to save
    example_data_1 = {
        "name": "John Doe",
        "age": 30,
        "city": "New York",
        "is_student": False,
        "courses": ["Math", "Science", "History"]
    }

    example_data_2 = {
        "name": "Jane Doe",
        "age": 28,
        "city": "San Francisco",
        "is_student": True,
        "courses": ["Literature", "Art", "Philosophy"]
    }
    
    # File path
    file_path = 'data.json'
    
    # Save the data to JSON with overwrite mode
    save_to_json(example_data_1, file_path, mode='w')
    
    # Save the data to JSON with append mode
    save_to_json(example_data_2, file_path, mode='a')
    
    # Load the data from JSON
    loaded_data = load_from_json(file_path)
    print(loaded_data)
