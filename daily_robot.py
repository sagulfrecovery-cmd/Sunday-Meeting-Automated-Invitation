import os, json, smtplib, pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY
PORTAL_URL = "https://sunday-meeting-automated-invitation-6bx73b56auheijtfynqvyo.streamlit.app/" # The link to your new portal

# 1. SETUP & AUTHENTICATION
creds_dict = json.loads(os.environ['GCP_SERVICE_ACCOUNT'])
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)

baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
yesterday = now - timedelta(days=1)

# Arabic Day Mapping
day_map = {0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
today_ar = day_map[now.weekday()]
yesterday_ar = day_map[yesterday.weekday()]

# Load Master Control Center
master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
master_data = pd.DataFrame(master_sheet.get_all_records())

def send_email(to_list, bcc_list, subject, body):
    sender = os.environ['SENDER_EMAIL']
    password = os.environ['APP_PASSWORD']
    msg = MIMEText(body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    
    if to_list: msg['To'] = ", ".join(to_list) if isinstance(to_list, list) else to_list
    
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(sender, password)
    # Send allows explicit BCC envelope routing
    server.send_message(msg, from_addr=sender, to_addrs=(to_list + bcc_list))
    server.quit()

# ==========================================
# 2. PROCESS YESTERDAY'S ABSENCES
# ==========================================
yesterday_meeting = master_data[master_data['Meeting Day'] == yesterday_ar]

if not yesterday_meeting.empty:
    print(f"Processing absences for yesterday's meeting: {yesterday_ar}")
    info = yesterday_meeting.iloc[0]
    db = client.open_by_key(str(info['Target Sheet ID']).strip())
    max_absences = int(info['Max Absences'])
    
    reg_tab = db.worksheet("Registration")
    reg_data = pd.DataFrame(reg_tab.get_all_records())
    
    try:
        check_tab = db.worksheet("Check-In Log")
        check_data = pd.DataFrame(check_tab.get_all_records())
        check_data['Timestamp'] = pd.to_datetime(check_data['Timestamp'], errors='coerce')
        recent_checks = check_data[check_data['Timestamp'] >= (datetime.now() - timedelta(days=2))]
        attended_emails = recent_checks.iloc[:, 1].str.lower().str.strip().tolist()
    except:
        attended_emails = [] # If no check-ins exist yet

    new_strikes = []
    warned_emails = []
    
    for index, row in reg_data.iterrows():
        email = str(row.iloc[1]).lower().strip()
        current_strikes = int(row.get('Missed Count', 0)) if pd.notna(row.get('Missed Count')) else 0
        
        if email in attended_emails:
            current_strikes = 0 
        else:
            current_strikes += 1 
            if 0 < current_strikes < max_absences:
                warned_emails.append(email)

        new_strikes.append(current_strikes)
        
    # Update Strikes in Sheet
    if 'Missed Count' not in reg_data.columns:
        reg_tab.update_cell(1, 4, 'Missed Count') # Ensure column header exists
    reg_tab.update(f"D2:D{len(new_strikes)+1}", [[s] for s in new_strikes])
    
    # Send BCC Warnings
    if warned_emails:
        warning_body = f"""<div dir="rtl" style="text-align: right; font-family: Arial;">
        مرحباً،<br><br>نود لفت انتباهكم إلى أننا لم نسجل حضوركم في اجتماع يوم {yesterday_ar} الأخير.<br><br>
        يرجى العلم أنه في حال بلوغ الحد الأقصى للغيابات المتتالية ({max_absences} غيابات)، سيقوم النظام بإزالة بريدكم الإلكتروني تلقائياً لإفساح المجال للآخرين.<br><br>
        شكرًا لكم!</div>"""
        # Sent entirely via BCC (to_list is empty)
        send_email(to_list=[], bcc_list=warned_emails, subject=f"تنبيه: غياب عن اجتماع {yesterday_ar}", body=warning_body)

# ==========================================
# 3. SEND TODAY'S INVITES
# ==========================================
today_meeting = master_data[master_data['Meeting Day'] == today_ar]

if not today_meeting.empty:
    print(f"Sending invites for today's meeting: {today_ar}")
    info = today_meeting.iloc[0]
    db = client.open_by_key(str(info['Target Sheet ID']).strip())
    max_absences = int(info['Max Absences'])
    invite_method = str(info.get('Invite Method', 'BCC')).strip().upper()
    utc_time_str = str(info['Meeting Time (UTC)']).strip()
    
    # --- SMART FETCH LOGIC ---
    topic, date_str = "موضوع غير محدد", "تاريخ غير محدد"
    try:
        # Try Wednesday Calendar Logic
        ws = db.worksheet("Meetings")
        m_data = pd.DataFrame(ws.get_all_records())
        m_data['Date'] = pd.to_datetime(m_data.iloc[:, 0], errors='coerce')
        future_meetings = m_data[m_data['Date'] >= pd.Timestamp(now.date())]
        if not future_meetings.empty:
            next_m = future_meetings.iloc[0]
            date_str = next_m['Date'].strftime("%Y/%m/%d")
            topic = next_m.iloc[1]
    except gspread.exceptions.WorksheetNotFound:
        # Fallback to Sunday Dashboard Logic
        ws = db.worksheet("اجتماع اليوم")
        date_str = ws.acell("D9").value
        topic = ws.acell("F9").value

    # Calculate Timezones
    meeting_utc = datetime.strptime(utc_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    meeting_utc = pytz.utc.localize(meeting_utc)
    
    cities = [
        {"tz": "Asia/Dubai", "ar": "دبي/مسقط"}, {"tz": "Asia/Riyadh", "ar": "الرياض"},
        {"tz": "Asia/Baghdad", "ar": "بغداد"}, {"tz": "Africa/Cairo", "ar": "القاهرة"},
        {"tz": "Africa/Casablanca", "ar": "الدار البيضاء"}, {"tz": "Europe/Berlin", "ar": "برلين"},
        {"tz": "Europe/London", "ar": "لندن"}, {"tz": "America/New_York", "ar": "نيويورك"},
        {"tz": "America/Chicago", "ar": "شيكاغو"}, {"tz": "America/Denver", "ar": "دنفر"},
        {"tz": "America/Los_Angeles", "ar": "لوس أنجلوس"}
    ]
    
    time_html = ""
    for city in cities:
        local_time = meeting_utc.astimezone(pytz.timezone(city['tz']))
        time_str = local_time.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
        time_html += f"<b>{city['ar']}:</b> {time_str}<br>"

    # Fetch Active Users
    reg_tab = db.worksheet("Registration")
    reg_data = pd.DataFrame(reg_tab.get_all_records())
    if 'Missed Count' not in reg_data.columns: reg_data['Missed Count'] = 0
    active_emails = reg_data[reg_data['Missed Count'] < max_absences].iloc[:, 1].dropna().tolist()

    if active_emails:
        invite_body = f"""<div dir="rtl" style="text-align: right; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6;">
        ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
        تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع اليوم، وموضوع الاجتماع هو:<br><br>
        <b>{topic}</b><br>
        الموافق {date_str}<br><br>
        <b>بداية وقت الاجتماع:</b><br>{time_html}<br>
        📌 <b>ملاحظة هامة:</b> تُغلق الغرفة بعد 20 دقيقة من بدء الاجتماع.<br><br>
        🔗 <b>للحصول على رابط الدخول للزوم، يرجى تسجيل حضورك عبر البوابة:</b><br>
        <a href="{PORTAL_URL}" style="color: #15c; text-decoration: underline;">اضغط هنا للدخول إلى بوابة زمالة الخليج</a><br><br>
        بـانـتـظـاركـم!<br>نحن بالفعل نتعافى!
        </div>"""
        
        if invite_method == "CC":
            send_email(to_list=active_emails, bcc_list=[], subject=f"دعوة لاجتماع زمالة الخليج - {date_str}", body=invite_body)
        else:
            send_email(to_list=[], bcc_list=active_emails, subject=f"دعوة لاجتماع زمالة الخليج - {date_str}", body=invite_body)
