import os
import requests
import time

# ดึง Channel Access Token จาก Environment Variable
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

if not CHANNEL_ACCESS_TOKEN:
    raise Exception("กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN เป็น Environment Variable")

# userId หรือ groupId ที่บอทสามารถส่งข้อความได้
TARGET_ID = os.getenv('LINE_TARGET_ID')  # เช่น Uxxxxxxxxxx หรือ Cxxxxxxxxx

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

def get_coingecko_prices(coin_id="bitcoin", days=1, interval="minute"):
    # ดึงข้อมูลราคาย้อนหลัง (ราคาต่อ 1 นาที) จาก CoinGecko
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval={interval}"
    res = requests.get(url)
    res.raise_for_status()
    data = res.json()
    prices = [price[1] for price in data["prices"]]  # [timestamp, price]
    return prices[-15:]  # ดึงล่าสุด 15 จุด (เทียบ Binance 14 แท่ง)

def calculate_rsi(closes):
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
        closes = get_coingecko_prices()
        rsi = calculate_rsi(closes)
        print(f"RSI = {rsi:.2f}")
        send_line_message(TARGET_ID, f"📉 RSI ต่ำกว่า 30 - โอกาสซื้อ BTC (RSI={rsi:.2f})")
        if rsi < 30:
            send_line_message(TARGET_ID, f"📉 RSI ต่ำกว่า 30 - โอกาสซื้อ BTC (RSI={rsi:.2f})")
        elif rsi > 70:
            send_line_message(TARGET_ID, f"📈 RSI สูงกว่า 70 - โอกาสขาย BTC (RSI={rsi:.2f})")
        else:
            print("RSI อยู่ในช่วงปกติ")

    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()        

if __name__ == "__main__":
    main()
