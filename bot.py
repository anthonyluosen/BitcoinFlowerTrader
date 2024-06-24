import requests

def send_telegram_message(bot_token, chat_id, message_text):
    """
    发送消息到 Telegram Bot。
    
    Args:
    - bot_token (str): 您的 Telegram Bot 的 token。
    - chat_id (str): 要发送消息的 chat_id。
    - message_text (str): 要发送的消息文本。
    
    Returns:
    - bool: 消息是否成功发送。
    """
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message_text
    }
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        return True
    else:
        return False
if __name__=='__main__':
    # 使用示例
    bot_token = '7402994402:AAEz6h-p9az4uxLnvSgdNaVGVDv8lEg4sMk'
    chat_id = '6848555062'
    message_text = 'Hello, this is a message from your bot!'

    if send_telegram_message(bot_token, chat_id, message_text):
        print('Message sent successfully!')
    else:
        print('Failed to send message.')
