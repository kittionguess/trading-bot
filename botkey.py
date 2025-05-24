import os
import logging
import random
import time
import threading
from datetime import datetime, timedelta
from binance.spot import Spot as Client
from binance.lib.utils import config_logging
import requests
from bs4 import BeautifulSoup

# ตั้งค่า logging
config_logging(logging, logging.INFO)
logger = logging.getLogger()

# ตัวแปร global สำหรับเก็บ Proxy List
proxy_list = []
last_proxy_update = None
proxy_lock = threading.Lock()

# กำหนดค่าจาก Environment Variables
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_TARGET_ID = os.getenv('LINE_TARGET_ID')

# ตรวจสอบค่าที่จำเป็น
if not all([BINANCE_API_KEY, BINANCE_API_SECRET, LINE_CHANNEL_ACCESS_TOKEN, LINE_TARGET_ID]):
    logger.error("กรุณาตั้งค่าตัวแปรสภาพแวดล้อมที่จำเป็น")
    exit(1)

def fetch_proxy_list():
    """ดึงรายการ Proxy จากเว็บไซต์ ProxyNova"""
    global proxy_list, last_proxy_update
    
    try:
        url = "https://www.proxynova.com/proxy-server-list/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        
        # ใช้ Session และเพิ่ม delay
        with requests.Session() as session:
            time.sleep(random.uniform(1, 3))
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 403:
                logger.error("ถูกบล็อกโดย ProxyNova กรุณาลองใหม่ในภายหลัง")
                return []
                
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            new_proxy_list = []
            
            # ดึงข้อมูลจากตาราง
            for row in soup.select('table#tbl_proxy_list tbody tr'):
                try:
                    # ดึง IP จาก script
                    ip_script = row.select_one('td:nth-child(1) script')
                    if ip_script:
                        ip_text = ip_script.text
                        ip_parts = []
                        for part in ip_text.split('document.write(')[1:]:
                            clean_part = part.split(')')[0].strip("' +")
                            if '.' in clean_part or clean_part.isdigit():
                                ip_parts.append(clean_part)
                        if len(ip_parts) >= 4:
                            ip = '.'.join(ip_parts[:4])
                            
                            # ดึง port
                            port_td = row.select_one('td:nth-child(2)')
                            if port_td:
                                port = port_td.get_text().strip()
                                if port.isdigit():
                                    new_proxy_list.append(f"http://{ip}:{port}")
                except Exception as e:
                    logger.debug(f"เกิดข้อผิดพลาดขณะประมวลผลแถว: {e}")
                    continue
        
        # กรอง Proxy ที่ได้
        valid_proxies = [p for p in new_proxy_list if len(p.split(':')) == 3]
        
        with proxy_lock:
            proxy_list = valid_proxies
            last_proxy_update = datetime.now()
        
        logger.info(f"อัปเดต Proxy List สำเร็จ ได้รับ {len(valid_proxies)} ตัว")
        return valid_proxies
        
    except Exception as e:
        logger.error(f"ดึง Proxy List ไม่สำเร็จ: {str(e)}")
        return []

def should_update_proxy_list():
    """ตรวจสอบว่าควรอัปเดต Proxy List หรือไม่ (ทุก 3 ชั่วโมง)"""
    global last_proxy_update
    if last_proxy_update is None:
        return True
    return datetime.now() - last_proxy_update > timedelta(hours=3)

def test_proxy(proxy_url, timeout=5):
    """ทดสอบว่า Proxy ใช้งานได้จริงหรือไม่"""
    try:
        test_url = "http://httpbin.org/ip"
        response = requests.get(test_url, 
                             proxies={'http': proxy_url, 'https': proxy_url},
                             timeout=timeout)
        return response.status_code == 200
    except:
        return False

def get_working_proxy(max_attempts=10):
    """หาตัว Proxy ที่ใช้งานได้จริง"""
    for _ in range(max_attempts):
        proxy = get_random_proxy()
        if proxy and test_proxy(proxy):
            logger.info(f"พบ Proxy ที่ใช้งานได้: {proxy}")
            return proxy
        time.sleep(1)
    return None

def get_random_proxy():
    """เลือก Proxy อย่างสุ่มจากรายการ"""
    global proxy_list
    
    # อัปเดต Proxy List ถ้าครบ 3 ชั่วโมง
    if should_update_proxy_list():
        fetch_proxy_list()
    
    with proxy_lock:
        if proxy_list:
            proxy = random.choice(proxy_list)
            logger.info(f"เลือก Proxy: {proxy}")
            return proxy
        return None

def create_binance_client():
    """สร้าง Binance Client พร้อม Proxy"""
    proxy = get_working_proxy()
    proxies = {
        'http': proxy,
        'https': proxy
    } if proxy else None
    
    return Client(
        BINANCE_API_KEY,
        BINANCE_API_SECRET,
        proxies=proxies
    )

def send_line_message(message):
    """ส่งข้อความผ่าน LINE Notify"""
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        "to": LINE_TARGET_ID,
        "messages": [{"type": "text", "text": message}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"ส่ง LINE เรียบร้อย: {message}")
    except Exception as e:
        logger.error(f"ส่ง LINE ไม่สำเร็จ: {str(e)}")

def get_binance_klines(symbol="BTCUSDT", interval="1m", limit=14, max_retries=3):
    """ดึงข้อมูลราคาจาก Binance พร้อมระบบลองใหม่"""
    for attempt in range(max_retries):
        try:
            client = create_binance_client()
            logger.info(f"กำลังดึงข้อมูล {symbol} {interval} (ครั้งที่ {attempt + 1})...")
            
            klines = client.klines(symbol, interval, limit=limit)
            
            if not klines or len(klines) < 2:
                logger.warning("ได้รับข้อมูลไม่เพียงพอจาก Binance API")
                continue
                
            return klines
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดครั้งที่ {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # Exponential backoff
                logger.info(f"รอ {wait_time} วินาที ก่อนลองอีกครั้ง...")
                time.sleep(wait_time)
    
    logger.error(f"ไม่สามารถดึงข้อมูลหลังจากลอง {max_retries} ครั้ง")
    return None

def calculate_rsi(prices, period=14):
    """คำนวณค่า RSI"""
    if len(prices) < period + 1:
        logger.warning("ข้อมูลไม่เพียงพอสำหรับคำนวณ RSI")
        return 50
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100 if avg_gain != 0 else 50
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)

def main():
    try:
        # ดึง Proxy List ครั้งแรก
        fetch_proxy_list()
        
        while True:
            start_time = datetime.now()
            logger.info(f"เริ่มทำงานที่ {start_time}")
            
            # ดึงข้อมูลจาก Binance
            klines = get_binance_klines()
            
            if not klines:
                send_line_message("⚠️ ไม่สามารถดึงข้อมูลจาก Binance ได้หลังจากลองหลายครั้ง")
            else:
                # แปลงข้อมูลเป็นราคาปิด
                closes = [float(candle[4]) for candle in klines]
                
                # คำนวณ RSI
                rsi = calculate_rsi(closes)
                logger.info(f"RSI คำนวณได้: {rsi}")
                
                # ส่งการแจ้งเตือนตามเงื่อนไข
                current_time = datetime.now().strftime('%H:%M')
                if rsi < 30:
                    message = f"📉 RSI ต่ำกว่า 30 - โอกาสซื้อ BTC\nRSI: {rsi}\nเวลา: {current_time}"
                    send_line_message(message)
                elif rsi > 70:
                    message = f"📈 RSI สูงกว่า 70 - โอกาสขาย BTC\nRSI: {rsi}\nเวลา: {current_time}"
                    send_line_message(message)
                else:
                    logger.info(f"RSI อยู่ในช่วงปกติ: {rsi}")
            
            # คำนวณเวลาที่เหลือจนถึงรอบถัดไป
            next_run = start_time + timedelta(hours=3)
            sleep_time = (next_run - datetime.now()).total_seconds()
            
            if sleep_time > 0:
                logger.info(f"รอจนถึงรอบถัดไปที่ {next_run} (อีก {sleep_time/3600:.2f} ชั่วโมง)")
                time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("หยุดการทำงานโดยผู้ใช้")
    except Exception as e:
        logger.critical(f"เกิดข้อผิดพลาดร้ายแรง: {str(e)}", exc_info=True)
        send_line_message("⚠️ เกิดข้อผิดพลาดในระบบตรวจสอบ RSI")

if __name__ == "__main__":
    main()
