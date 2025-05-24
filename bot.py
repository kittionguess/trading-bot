import os
import requests
import time
from datetime import datetime

# ควรเพิ่ม delay ระหว่าง requests เพื่อป้องกัน rate limit
REQUEST_DELAY = 0.1  # วินาที

# ดึง Channel Access Token จาก Environment Variable
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

if not CHANNEL_ACCESS_TOKEN:
    raise Exception("กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN เป็น Environment Variable")

TARGET_ID = os.getenv('LINE_TARGET_ID')
if not TARGET_ID:
    raise Exception("กรุณาตั้งค่า LINE_TARGET_ID เป็น Environment Variable")

def send_line_message(user_id, message):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    print(f'Status: {response.status_code}, Response: {response.text}')

def get_binance_close_price(symbol="BTCUSDT"):
    time.sleep(REQUEST_DELAY)  # เพิ่ม delay เพื่อป้องกัน rate limit
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=14'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'X-MBX-APIKEY': os.getenv('BINANCE_API_KEY', '')  # ควรใช้ API Key หากต้องการใช้งานหนัก
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        closes = [float(candle[4]) for candle in data]
        return closes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Binance data: {e}")
        return None

def calculate_rsi(closes):
    if not closes or len(closes) < 2:
        return 50  # ค่าเริ่มต้นหากไม่มีข้อมูลพอ
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def main():
    try:
        print(f"Checking at {datetime.now().isoformat()}")
        closes = get_binance_close_price()
        
        if not closes:
            send_line_message(TARGET_ID, "⚠️ ไม่สามารถดึงข้อมูลจาก Binance ได้")
            return
            
        rsi = calculate_rsi(closes)
        print(f"RSI = {rsi:.2f}")
        
        if rsi < 30:
            send_line_message(TARGET_ID, f"📉 RSI ต่ำกว่า 30 - โอกาสซื้อ BTC (RSI={rsi:.2f})")
        elif rsi > 70:
            send_line_message(TARGET_ID, f"📈 RSI สูงกว่า 70 - โอกาสขาย BTC (RSI={rsi:.2f})")
        else:
            print(f"RSI อยู่ในช่วงปกติ: {rsi:.2f}")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        send_line_message(TARGET_ID, "⚠️ เกิดข้อผิดพลาดในระบบตรวจสอบ RSI")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
