import os
import json
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 구글 시트 연동
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
json_creds = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
client = gspread.authorize(creds)

doc = client.open("출판 주간 매출 보고")
raw_sheet = doc.worksheet("RAW_DATA")

# 2. 계정 정보 가져오기
accounts = json.loads(os.environ['MOASIS_ACCOUNTS'])

print(f"총 {len(accounts)}개 계정으로 모아시스 접속을 준비합니다.")
print("구글 시트 연동 및 자동화 기본 설정이 완료되었습니다!")
