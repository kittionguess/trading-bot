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

# ตัวแปร全局สำหรับเก็บ Proxy List
proxy_list = []
last_proxy_update = None
proxy_lock = threading.Lock()

def fetch_proxy_list():
    """ดึงรายการ Proxy จาก ProxyNova แบบทนทานต่อการเปลี่ยนแปลง"""
    global proxy_list, last_proxy_update
    
    try:
        url = "https://www.proxynova.com/proxy-server-list/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
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
        valid_proxies = []
        for proxy in new_proxy_list:
            parts = proxy.split(':')
            if len(parts) == 3 and parts[2].isdigit():
                valid_proxies.append(proxy)
        
        with proxy_lock:
            proxy_list = valid_proxies
            last_proxy_update = datetime.now()
        
        logger.info(f"อัปเดต Proxy List สำเร็จ ได้รับ {len(valid_proxies)} ตัว")
        return valid_proxies
        
    except Exception as e:
        logger.error(f"ดึง Proxy List ไม่สำเร็จ: {str(e)}")
        return []

# ... ส่วนที่เหลือของฟังก์ชันเหมือนเดิม ...

if __name__ == "__main__":
    # ทดสอบการดึง Proxy
    proxies = fetch_proxy_list()
    print(f"Proxy ที่ดึงมาได้: {proxies[:5]}... (ทั้งหมด {len(proxies)} ตัว)")
