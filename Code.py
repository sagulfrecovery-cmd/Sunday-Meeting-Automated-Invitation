import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import smtplib
from email.mime.text import MIMEText
import json

# ==========================================
# 1. PAGE CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="Fellowship Admin Portal", layout="wide")

st.title("⚙️ Gulf Fellowship - Admin Dashboard")
st.markdown("Manage your Sunday meeting invites and Monday attendance warnings dynamically.")

# ==========================================
# 2. DYNAMIC ADMIN SETTINGS (SIDEBAR)
# ==========================================
st.sidebar.header("🔗 Form Links")
check_in_link = st.sidebar.text_input("Check-In Form Link", value="https://docs.google.com/forms/d/e/1FAIpQLSdmR68FNIuninImccaVODpR8QWNeec5VAHyv7AN3nrMSYlmqg/viewform?usp=sharing&ouid=117963799738843870003")
registration_link = st.sidebar.text_input("Registration Form Link", value="https://docs.google.com/forms/d/e/1FAIpQLSdswI0lkVllYOB7bD-VuYiTnxtiuO-MM3e22iDU5MD9PhT-pQ/viewform?usp=sharing&ouid=117963799738843870003")

st.sidebar.markdown("---")
st.sidebar.header("🛠️ Dynamic Settings")
absence_threshold = st.sidebar.number_input("Absence Removal Threshold (Strikes)", min_value=1, value=4)
retention_days = st.sidebar.number_input("Check-In Retention (Days)", min_value=7, value=90)

st.sidebar.markdown("---")
st.sidebar.header("📧 Email Server Setup")
sender_email = st.sidebar.text_input("Sender Gmail Address")
app_password = st.sidebar.text_input("App Password", type="password")

# Google Sheets Configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = 12MZ5Toba274TUyQV9Zjrixcsl0qNO5mA-ApJv2woQ64 # Make sure to put your real Sheet ID here again!

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
@st.cache_resource
def connect_to_sheets():
    # THIS IS THE FIX: We load the string as JSON first
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def send_email(to_addresses, subject, body):
    if not sender_email or not app_password:
        st.error("Please enter your Gmail Address and App Password in the sidebar.")
        return False
    
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ", ".join(to_addresses) if isinstance(to_addresses, list) else to_addresses

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False

def get_dynamic_timezones(raw_date):
    baghdad_tz = pytz.timezone("Asia/Baghdad")
    meeting_dt_unaware = datetime.strptime(f"{raw_date} 21:00:00", "%Y-%m-%d %H:%M:%S")
    meeting_moment = baghdad_tz.localize(meeting_dt_unaware)

    time_zones = [
        {"tz": "Asia/Dubai", "en": "Dubai", "ar": "دبي"},
        {"tz": "Asia/Muscat", "en": "Muscat", "ar": "مسقط"},
        {"tz": "Asia/Baghdad", "en": "Baghdad", "ar": "بغداد"},
        {"tz": "Asia/Riyadh", "en": "Riyadh", "ar": "الرياض"},
        {"tz": "Africa/Cairo", "en": "Cairo", "ar": "القاهرة"},
        {"tz": "Europe/Berlin", "en": "Berlin", "ar": "برلين"},
        {"tz": "Europe/Madrid", "en": "Madrid", "ar": "مدريد"},
        {"tz": "Africa/Casablanca", "en": "Casablanca", "ar": "الدار البيضاء"},
        {"tz": "Europe/London", "en": "London", "ar": "لندن"},
        {"tz": "America/New_York", "en": "New_York", "ar": "نيويورك"},
        {"tz": "America/Chicago", "en": "Chicago", "ar": "شيكاغو"},
        {"tz": "America/Denver", "en": "Denver", "ar": "دنفر"},
        {"tz": "America/Phoenix", "en": "Phoenix", "ar": "فينيكس"},
        {"tz": "America/Los_Angeles", "en": "Los_Angeles", "ar": "لوس أنجلوس"}
    ]

    time_list_str = ""
    for tz_info in time_zones:
        local_tz = pytz.timezone(tz_info["tz"])
        local_time = meeting_moment.astimezone(local_tz)
        time_str = local_time.strftime("%I:%M%p").upper()
        time_list_str += f"{time_str} -- {tz_info['en']}/{tz_info['ar']}\n"
    
    return time_list_str.strip()

# ==========================================
# 4. SUNDAY PROTOCOL (MEETING INVITES)
# ==========================================
st.subheader("📅 Sunday Protocol: Generate Invites")
if st.button("Generate & Send Sunday Invites"):
    with st.spinner("Connecting to database and calculating timezones..."):
        sheet = connect_to_sheets()
        
        meeting_tab = sheet.worksheet("اجتماع اليوم")
        raw_date = meeting_tab.acell("D9").value
        meeting_subject = meeting_tab.acell("F9").value
        
        d_parts = raw_date.split("-")
        display_date = f"{int(d_parts[2])} / {int(d_parts[1])} / {d_parts[0]}" if len(d_parts) == 3 else raw_date
        
        reg_tab = sheet.worksheet("Form Responses 1")
        reg_data = pd.DataFrame(reg_tab.get_all_records())
        
        if 'Missed Count' not in reg_data.columns:
            reg_data['Missed Count'] = 0
            
        active_users = reg_data[reg_data['Missed Count'] < absence_threshold]
        active_emails = active_users.iloc[:, 1].dropna().tolist() 

        dynamic_times = get_dynamic_timezones(raw_date)
        
        message_body = f"""👨🏻‍💻👩🏻‍💻 يـرجـى قـــراءة ا لاعـــلان جــيــدا

                   تـــدعـــوكــــم  
        ༺☆» زمـــالــة الـــخــلـــيـــج »☆༻ 

    «☆«☆«☆«☆📖📚📖☆ »☆»☆»☆»

🌅 الـيـوم :- الا حـــــــــد
🗓 الـتـاريـخ :- {display_date}

✍🏼نـوع الاجـتمـاع:- قـــراءه مـــن

  
🔵🔷🔹📖 {meeting_subject} 🔹🔷🔵


🙋🏻‍♀️🙋🏻 تــنــبــيــه هــام :-
الـحـضـوره فـقـط وحـصـرا لاعـضـاء مـجـمـوعـة زمـالـة الـخـلـيـج الام

༺»مدة الأجـتـمـاع:- 70 دقيقة«༻

-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

📟 بداية وقت الاجتماع 
📟 Meeting Start Time

الوقت/Time
{dynamic_times}

-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع

-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

🔗 لتسجيل الحضور للحصول على رابط الاجتماع (Check-In):
{check_in_link}

📝 للتسجيل في القائمة البريدية (Registration):
{registration_link}

-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

بـأنـتـظـار حضوركم  !
نـحــن بـالـفــعـل نـتـعـافـى 🙏🏼"""

        if send_email(active_emails, "اعلان اجتماع الخليج", message_body):
            st.success(f"✅ Successfully sent invites to {len(active_emails)} active members!")
            st.code(message_body)

# ==========================================
# 5. MONDAY PROTOCOL (WARNINGS & CLEANUP)
# ==========================================
st.markdown("---")
st.subheader("🚨 Monday Protocol: Process Absences")
if st.button("Process Absences & Send Warnings"):
    with st.spinner("Analyzing attendance data..."):
        sheet = connect_to_sheets()
        
        reg_tab = sheet.worksheet("Form Responses 1")
        check_tab = sheet.worksheet("Form Responses 2")
        
        reg_data = pd.DataFrame(reg_tab.get_all_records())
        check_data = pd.DataFrame(check_tab.get_all_records())
        
        recent_cutoff = datetime.now() - timedelta(days=2)
        check_data['Timestamp'] = pd.to_datetime(check_data['Timestamp'], errors='coerce')
        recent_checks = check_data[check_data['Timestamp'] >= recent_cutoff]
        recent_attendees = recent_checks.iloc[:, 1].str.lower().str.strip().tolist()

        warnings_sent = 0
        new_strikes = []
        
        for index, row in reg_data.iterrows():
            email = str(row.iloc[1]).lower().strip()
            current_strikes = int(row.get('Missed Count', 0)) if pd.notna(row.get('Missed Count')) else 0
            
            if email in recent_attendees:
                current_strikes = 0 
            else:
                current_strikes += 1 
                
                if 0 < current_strikes < absence_threshold:
                    warning_body = "مرحباً،\n\nنود لفت انتباهكم إلى أننا لم نسجل حضوركم في اجتماع زمالة الخليج الأخير.\n\nيرجى العلم أنه في حال بلوغ الحد الأقصى للغيابات المتتالية، سيقوم النظام بإزالة بريدكم الإلكتروني تلقائياً من القائمة لإفساح المجال للآخرين.\n\nنحن بالفعل نتعافى!"
                    send_email([email], "تنبيه: غياب عن اجتماع زمالة الخليج", warning_body)
                    warnings_sent += 1

            new_strikes.append(current_strikes)
            
        reg_tab.update(f"D2:D{len(new_strikes)+1}", [[s] for s in new_strikes])
        
        retention_cutoff = datetime.now() - timedelta(days=retention_days)
        old_rows = check_data[check_data['Timestamp'] < retention_cutoff]
        for row_idx in reversed(old_rows.index):
            check_tab.delete_row(row_idx + 2) 
            
        st.success(f"✅ Process complete! Sent {warnings_sent} warnings and updated the strike counts.")
