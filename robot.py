import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import smtplib
import imaplib
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import pytz

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# --- SECRETS ---
GCP_SA = os.environ.get("GCP_SERVICE_ACCOUNT")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

# --- AUTHENTICATION ---
creds_dict = json.loads(GCP_SA)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

# --- TIME & DAYS LOGIC ---
utc_now = datetime.now(pytz.utc)
days_ar = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}

today_name = days_ar[utc_now.weekday()]
yesterday_name = days_ar[(utc_now.weekday() - 1) % 7]
yesterday_date_str = (utc_now - timedelta(days=1)).astimezone(pytz.timezone("Asia/Baghdad")).strftime("%Y-%m-%d")

# --- EMAIL FUNCTIONS ---
def create_draft(subject, body, emails, invite_method):
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    
    # Set BCC or CC based on Master Sheet
    if invite_method.upper() == 'BCC':
        msg['Bcc'] = ", ".join(emails)
    else:
        msg['Cc'] = ", ".join(emails)
        
    try:
        imap = imaplib.IMAP4_SSL('imap.gmail.com')
        imap.login(SENDER_EMAIL, APP_PASSWORD)
        # Upload to Drafts folder
        imap.append('[Gmail]/Drafts', '', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        imap.logout()
        print(f"Draft created successfully for {len(emails)} people.")
    except Exception as e:
        print(f"Failed to create draft: {e}")

def send_gentle_notice(email_address, meeting_day):
    subject = "نفتقدك في زمالة الخليج"
    body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماع يوم {meeting_day}، ونتمنى أن تكون بخير وبأفضل حال.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك في الاجتماع القادم.\n\nنحن بالفعل نتعافى!"
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = email_address

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Gentle notice sent to {email_address}")
    except Exception as e:
        print(f"Failed to send notice to {email_address}: {e}")

# --- MAIN LOGIC ---
def run_robot():
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    
    # 1. Today's Logic: Create Invitation Draft
    today_meeting = meetings_data[meetings_data['Meeting Day'] == today_name]
    if not today_meeting.empty:
        meeting_info = today_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        invite_method = str(meeting_info['Invite Method']).strip()
        
        target_db = client.open_by_key(target_id)
        reg_tab = target_db.worksheet("Registration")
        reg_df = pd.DataFrame(reg_tab.get_all_records())
        
        valid_emails = []
        for index, row in reg_df.iterrows():
            raw_abs = row.get('Absences', row.get('الغيابات', 0))
            absences = int(raw_abs) if str(raw_abs).strip() != '' else 0
            
            if absences < max_abs:
                valid_emails.append(str(row.iloc[1]).strip().lower())
        
        if valid_emails:
            subject = f"دعوة اجتماع زمالة الخليج - {today_name}"
            body = f"مرحباً بكم،\n\nتجدون أدناه تفاصيل اجتماع اليوم.\n\nرابط زووم: {meeting_info['Zoom Link']}\n\nنحن بالفعل نتعافى!"
            create_draft(subject, body, valid_emails, invite_method)

    # 2. Yesterday's Logic: Send Gentle Notices
    yesterday_meeting = meetings_data[meetings_data['Meeting Day'] == yesterday_name]
    if not yesterday_meeting.empty:
        meeting_info = yesterday_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        
        target_db = client.open_by_key(target_id)
        reg_tab = target_db.worksheet("Registration")
        reg_df = pd.DataFrame(reg_tab.get_all_records())
        
        try:
            check_in_tab = target_db.worksheet("Check-In Log")
            check_in_df = pd.DataFrame(check_in_tab.get_all_records())
            yesterday_attendees = check_in_df[check_in_df['Timestamp'].astype(str).str.contains(yesterday_date_str, na=False)]['Email'].str.lower().str.strip().tolist()
        except gspread.exceptions.WorksheetNotFound:
            yesterday_attendees = []

        # Compare registered users with attendees
        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            raw_abs = row.get('Absences', row.get('الغيابات', 0))
            absences = int(raw_abs) if str(raw_abs).strip() != '' else 0
            
            if email not in yesterday_attendees and absences < max_abs:
                send_gentle_notice(email, yesterday_name)

if __name__ == "__main__":
    run_robot()
