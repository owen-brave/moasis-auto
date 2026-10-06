import os
import json
import time
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_korean_proxy():
    """공용 한국 프록시 IP 추출 시도"""
    try:
        res = requests.get("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=3000&country=KR", timeout=5)
        if res.status_code == 200 and res.text.strip():
            proxies = res.text.strip().splitlines()
            if proxies:
                return proxies[0]
    except Exception as e:
        print(f"프록시 추출 참고: {e}")
    return None

def main():
    print("Google Sheets 연결 중...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    json_creds = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)

    doc = client.open("출판 주간 매출 보고")
    raw_sheet = doc.worksheet("RAW_DATA")

    accounts = json.loads(os.environ['MOASIS_ACCOUNTS'])
    print(f"총 {len(accounts)}개 계정 수집을 시작합니다.")

    # 날짜 계산 (월요일 ~ 금요일)
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    friday = monday + datetime.timedelta(days=4)
    
    y1, m1, d1 = monday.strftime('%Y'), monday.strftime('%m'), monday.strftime('%d')
    y2, m2, d2 = friday.strftime('%Y'), friday.strftime('%m'), friday.strftime('%d')
    print(f"수집 기간: {y1}-{m1}-{d1} ~ {y2}-{m2}-{d2}")

    # 브라우저 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.page_load_strategy = 'none'  # 타임아웃 방지를 위한 비동기 로딩

    # 한국 프록시 IP 설정 시도
    kr_proxy = get_korean_proxy()
    if kr_proxy:
        print(f"한국 프록시 IP 사용: {kr_proxy}")
        chrome_options.add_argument(f'--proxy-server=http://{kr_proxy}')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.set_page_load_timeout(60)
    wait = WebDriverWait(driver, 15)
    LOGIN_URL = "https://pub.bookman.kr"
    
    all_collected_data = []

    for idx, acc in enumerate(accounts, 1):
        user_id = acc.get('id', '')
        user_pw = acc.get('pw', '')

        if not user_id or not user_pw:
            continue

        print(f"[{idx}/{len(accounts)}] 계정({user_id}) 접속 시도 중...")

        try:
            # 1. 로그인 페이지 접속
            try:
                driver.get(LOGIN_URL)
            except Exception:
                pass  # page_load_strategy='none' 상태이므로 타임아웃 무시 후 바로 진행
            time.sleep(5)

            id_input = wait.until(EC.presence_of_element_located((By.NAME, "megagong1")))
            pw_input = driver.find_element(By.NAME, "password")
            id_input.clear()
            id_input.send_keys(user_id)
            pw_input.clear()
            pw_input.send_keys(user_pw)

            login_btn = driver.find_element(By.XPATH, "//img[contains(@src, 'btn_login') or contains(@alt, '로그인')]")
            login_btn.click()
            time.sleep(4)

            # 2. MENU 버튼 클릭
            try:
                menu_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'MENU')]")))
                menu_btn.click()
                time.sleep(2)
            except Exception:
                pass

            # 3. '기간별 매출현황' 메뉴 클릭
            try:
                sales_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '기간별 매출현황')]")))
                sales_menu.click()
                time.sleep(3)
            except Exception as e:
                print(f"[{user_id}] 메뉴 클릭 실패: {e}")
                continue

            # 4. iFrame 전환
            if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
                driver.switch_to.frame(0)

            # 5. 날짜 입력
            try:
                date_inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
                if len(date_inputs) >= 6:
                    date_inputs[0].clear(); date_inputs[0].send_keys(y1)
                    date_inputs[1].clear(); date_inputs[1].send_keys(m1)
                    date_inputs[2].clear(); date_inputs[2].send_keys(d1)
                    date_inputs[3].clear(); date_inputs[3].send_keys(y2)
                    date_inputs[4].clear(); date_inputs[4].send_keys(m2)
                    date_inputs[5].clear(); date_inputs[5].send_keys(d2)
            except Exception as e:
                print(f"[{user_id}] 날짜 입력 경고: {e}")

            # 6. '조회' 클릭
            try:
                search_btn = driver.find_element(By.XPATH, "//*[contains(text(), '조회') or contains(@src, 'btn_search')]")
                search_btn.click()
                time.sleep(4)
            except Exception as e:
                print(f"[{user_id}] 조회 버튼 클릭 실패: {e}")

            # 7. 다중 페이지 데이터 수집
            account_data_count = 0
            page_num = 1

            while True:
                rows = driver.find_elements(By.XPATH, "//table//tr")
                for r in rows:
                    cols = [c.text.strip() for c in r.find_elements(By.XPATH, "./td|./th")]
                    if len(cols) >= 5 and cols[0].isdigit():
                        row_data = [user_id] + cols
                        all_collected_data.append(row_data)
                        account_data_count += 1

                try:
                    next_btns = driver.find_elements(By.XPATH, "//*[contains(text(), '다음페이지') or contains(text(), '▶')]")
                    clickable_next = None
                    for btn in next_btns:
                        if btn.is_displayed() and btn.is_enabled():
                            clickable_next = btn
                            break
                    
                    if clickable_next:
                        clickable_next.click()
                        page_num += 1
                        time.sleep(3)
                    else:
                        break
                except Exception:
                    break

            print(f"[{user_id}] 총 {page_num}개 페이지에서 데이터 {account_data_count}건 수집 완료")
            driver.switch_to.default_content()

        except Exception as e:
            print(f"[{user_id}] 계정 처리 중 오류: {e}")
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            continue

    driver.quit()

    # 8. 구글 시트 반영
    if all_collected_data:
        raw_sheet.append_rows(all_collected_data)
        print(f"총 {len(all_collected_data)}건의 데이터가 RAW_DATA 시트에 성공적으로 추가되었습니다!")
    else:
        print("조회된 매출 데이터가 없습니다.")

if __name__ == "__main__":
    main()
