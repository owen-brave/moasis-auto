import os
import json
import time
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def main():
    # 1. Google Sheets API 연동
    print("Google Sheets 연결 중...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    json_creds = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)

    doc = client.open("출판 주간 매출 보고")
    raw_sheet = doc.worksheet("RAW_DATA")

    # 2. 모아시스 계정 정보 로드
    accounts = json.loads(os.environ['MOASIS_ACCOUNTS'])
    print(f"총 {len(accounts)}개 계정 수집을 시작합니다.")

    # 3. 날짜 계산 (월요일 ~ 금요일)
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    friday = monday + datetime.timedelta(days=4)
    
    date_from = monday.strftime('%Y-%m-%d')
    date_to = friday.strftime('%Y-%m-%d')
    print(f"수집 대상 기간: {date_from} ~ {date_to}")

    # 4. 가상 브라우저(Headless Chrome) 설정
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    LOGIN_URL = "https://pub.bookman.kr"
    all_collected_data = []

    try:
        for idx, acc in enumerate(accounts, 1):
            user_id = acc.get('id', '')
            user_pw = acc.get('pw', '')

            if not user_id or not user_pw or user_id.startswith("첫번째"):
                print(f"[{idx}] 계정 정보가 올바르게 입력되지 않아 스킵합니다.")
                continue

            print(f"[{idx}/{len(accounts)}] {user_id} 계정 접속 중...")
            driver.get(LOGIN_URL)
            time.sleep(2)

            # 로그인 정보 입력
            id_input = driver.find_element(By.NAME, "megagong1")
            pw_input = driver.find_element(By.NAME, "password")
            
            id_input.clear()
            id_input.send_keys(user_id)
            pw_input.clear()
            pw_input.send_keys(user_pw)

            # 로그인 버튼 클릭
            login_btn = driver.find_element(By.XPATH, "//img[contains(@src, 'btn_login') or contains(@alt, '로그인')]")
            login_btn.click()
            time.sleep(3)

            print(f"[{user_id}] 로그인 완료 및 출고 데이터 조회 시작...")

    except Exception as e:
        print(f"작업 중 오류 발생: {e}")
    finally:
        driver.quit()

    if all_collected_data:
        raw_sheet.append_rows(all_collected_data)
        print(f"성공적으로 {len(all_collected_data)}건의 데이터를 RAW_DATA 시트에 복붙했습니다.")
    else:
        print("수집 완료 테스트 단계입니다.")

if __name__ == "__main__":
    main()
