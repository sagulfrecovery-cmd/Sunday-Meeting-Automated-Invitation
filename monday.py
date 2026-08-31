import os, json, smtplib
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# --- CONFIGURATION ---
SHEET_ID = "12MZ5Toba274TUyQV9Zjrixcsl0qNO5mA-ApJv2woQ64"
ABSENCE_THRESHOLD = 4
RETENTION_DAYS = 90

def send_email(to_addresses, subject, body):
    sender_email = os.environ['SENDER_EMAIL']
    app_password = os.environ['APP_PASSWORD']
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(to_addresses) if isinstance(to_addresses, list) else to_addresses
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(sender_email, app_password)
    server.send_message(msg)
    server.quit()

# Connect to Sheets
creds_dict = json.loads(os.environ['GCP_SERVICE_ACCOUNT'])
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
sheet = gspread.authorize(creds).open_by_key(SHEET_ID)

reg_tab = sheet.worksheet("Form Responses 1")
check_tab = sheet.worksheet("Form Responses 2")
reg_data = pd.DataFrame(reg_tab.get_all_records())
check_data = pd.DataFrame(check_tab.get_all_records())

# Identify recent attendees (last 48 hours)
check_data['Timestamp'] = pd.to_datetime(check_data['Timestamp'], errors='coerce')
recent_checks = check_data[check_data['Timestamp'] >= (datetime.now() - timedelta(days=2))]
recent_attendees = recent_checks.iloc[:, 1].str.lower().str.strip().tolist()

new_strikes = []
for index, row in reg_data.iterrows():
    email = str(row.iloc[1]).lower().strip()
    current_strikes = int(row.get('Missed Count', 0)) if pd.notna(row.get('Missed Count')) else 0
    
    if email in recent_attendees:
        current_strikes = 0 
    else:
        current_strikes += 1 
        if 0 < current_strikes < ABSENCE_THRESHOLD:
            warning_body = "مرحباً،\n\nنود لفت انتباهكم إلى أننا لم نسجل حضوركم في اجتماع زمالة الخليج الأخير.\n\nيرجى العلم أنه في حال بلوغ الحد الأقصى للغيابات المتتالية، سيقوم النظام بإزالة بريدكم الإلكتروني تلقائياً من القائمة لإفساح المجال للآخرين.\n\nنحن بالفعل نتعافى!"
            send_email([email], "تنبيه: غياب عن اجتماع زمالة الخليج", warning_body)

    new_strikes.append(current_strikes)
    
# Update Database
reg_tab.update(f"D2:D{len(new_strikes)+1}", [[s] for s in new_strikes])

# Cleanup Old Data
old_rows = check_data[check_data['Timestamp'] < (datetime.now() - timedelta(days=RETENTION_DAYS))]
for row_idx in reversed(old_rows.index):
    check_tab.delete_row(row_idx + 2) 

print("Monday Warnings and Cleanup Completed!")
