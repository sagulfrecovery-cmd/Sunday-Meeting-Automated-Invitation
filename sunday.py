import os, json, smtplib, pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from email.mime.text import MIMEText

# --- CONFIGURATION (EDIT THESE IF NEEDED) ---
SHEET_ID = "12MZ5Toba274TUyQV9Zjrixcsl0qNO5mA-ApJv2woQ64"
ABSENCE_THRESHOLD = 4
CHECK_IN_LINK = "https://docs.google.com/forms/d/e/1FAIpQLSdmR68FNIuninImccaVODpR8QWNeec5VAHyv7AN3nrMSYlmqg/viewform?usp=sharing&ouid=117963799738843870003"
REGISTRATION_LINK = "https://docs.google.com/forms/d/e/1FAIpQLSdswI0lkVllYOB7bD-VuYiTnxtiuO-MM3e22iDU5MD9PhT-pQ/viewform?usp=sharing&ouid=117963799738843870003"

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

# Connect to Google Sheets
creds_dict = json.loads(os.environ['GCP_SERVICE_ACCOUNT'])
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
sheet = gspread.authorize(creds).open_by_key(SHEET_ID)

# Pull Meeting Info
meeting_tab = sheet.worksheet("اجتماع اليوم")
raw_date = meeting_tab.acell("D9").value
meeting_subject = meeting_tab.acell("F9").value
d_parts = raw_date.split("-")
display_date = f"{int(d_parts[2])} / {int(d_parts[1])} / {d_parts[0]}" if len(d_parts) == 3 else raw_date

# Get Active Emails
reg_tab = sheet.worksheet("Form Responses 1")
reg_data = pd.DataFrame(reg_tab.get_all_records())
if 'Missed Count' not in reg_data.columns: reg_data['Missed Count'] = 0
active_emails = reg_data[reg_data['Missed Count'] < ABSENCE_THRESHOLD].iloc[:, 1].dropna().tolist()

# Timezones
baghdad_tz = pytz.timezone("Asia/Baghdad")
meeting_moment = baghdad_tz.localize(datetime.strptime(f"{raw_date} 21:00:00", "%Y-%m-%d %H:%M:%S"))
time_zones = [
    {"tz": "Asia/Dubai", "en": "Dubai", "ar": "دبي"}, {"tz": "Asia/Muscat", "en": "Muscat", "ar": "مسقط"},
    {"tz": "Asia/Baghdad", "en": "Baghdad", "ar": "بغداد"}, {"tz": "Asia/Riyadh", "en": "Riyadh", "ar": "الرياض"},
    {"tz": "Africa/Cairo", "en": "Cairo", "ar": "القاهرة"}, {"tz": "Europe/Berlin", "en": "Berlin", "ar": "برلين"},
    {"tz": "Europe/Madrid", "en": "Madrid", "ar": "مدريد"}, {"tz": "Africa/Casablanca", "en": "Casablanca", "ar": "الدار البيضاء"},
    {"tz": "Europe/London", "en": "London", "ar": "لندن"}, {"tz": "America/New_York", "en": "New_York", "ar": "نيويورك"},
    {"tz": "America/Chicago", "en": "Chicago", "ar": "شيكاغو"}, {"tz": "America/Denver", "en": "Denver", "ar": "دنفر"},
    {"tz": "America/Phoenix", "en": "Phoenix", "ar": "فينيكس"}, {"tz": "America/Los_Angeles", "en": "Los_Angeles", "ar": "لوس أنجلوس"}
]
dynamic_times = "\n".join([f"{meeting_moment.astimezone(pytz.timezone(tz['tz'])).strftime('%I:%M%p').upper()} -- {tz['en']}/{tz['ar']}" for tz in time_zones])

# Body and Send
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
{CHECK_IN_LINK}

📝 للتسجيل في القائمة البريدية (Registration):
{REGISTRATION_LINK}
-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_
بـأنـتـظـار حضوركم  !
نـحــن بـالـفــعـل نـتـعـافـى 🙏🏼"""

send_email(active_emails, "اعلان اجتماع الخليج", message_body)
print("Sunday Invites Sent Successfully!")
