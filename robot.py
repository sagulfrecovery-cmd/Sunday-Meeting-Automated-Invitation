import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import smtplib
import imaplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PORTAL_LINK = "https://sagulf-recovery-meeting-registration-and-check-in-2026.streamlit.app/"

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
baghdad_tz = pytz.timezone("Asia/Baghdad")
baghdad_now = utc_now.astimezone(baghdad_tz)
today_str = baghdad_now.strftime("%Y-%m-%d")

days_ar = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
today_name = days_ar[baghdad_now.weekday()]
yesterday_name = days_ar[(baghdad_now.weekday() - 1) % 7]
yesterday_date_str = (baghdad_now - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"🤖 استيقظ الروبوت... اليوم: {today_name} | الأمس: {yesterday_name}")

# --- HELPER FUNCTIONS ---
def get_safe_absences(row):
    """دالة مضادة للأخطاء لقراءة الغيابات حتى لو كانت الخلية فارغة"""
    raw_abs = row.get('Absences', row.get('الغيابات', 0))
    try:
        return int(float(raw_abs))
    except (ValueError, TypeError):
        return 0

def create_draft(subject, body, emails, invite_method, is_html=False):
    if not emails: return
    
    if is_html:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(body, 'html', 'utf-8'))
    else:
        msg = MIMEText(body, 'plain', 'utf-8')
        
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    
    if invite_method.upper() == 'BCC':
        msg['Bcc'] = ", ".join(emails)
    else:
        msg['Cc'] = ", ".join(emails)
        
    try:
        imap = imaplib.IMAP4_SSL('imap.gmail.com')
        imap.login(SENDER_EMAIL, APP_PASSWORD)
        imap.append('[Gmail]/Drafts', '', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        imap.logout()
        print(f"✅ تم إنشاء مسودة '{subject}' بنجاح لـ {len(emails)} شخص.")
    except Exception as e:
        print(f"❌ فشل في إنشاء المسودة: {e}")

# --- MAIN LOGIC ---
def run_robot():
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    
    # ==========================================
    # 1. TODAY'S MEETING LOGIC (CREATE DRAFTS)
    # ==========================================
    today_meeting = meetings_data[meetings_data['Meeting Day'] == today_name]
    if not today_meeting.empty:
        print(f"📅 تم العثور على اجتماع اليوم ({today_name}). جاري التحضير...")
        meeting_info = today_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        invite_method = str(meeting_info['Invite Method']).strip()
        form_link = str(meeting_info.get('Form Link', PORTAL_LINK)).strip()
        if not form_link: form_link = PORTAL_LINK
        
        target_db = client.open_by_key(target_id)
        reg_tab = target_db.worksheet("Registration")
        reg_df = pd.DataFrame(reg_tab.get_all_records())
        
        valid_emails = []
        for index, row in reg_df.iterrows():
            absences = get_safe_absences(row)
            if absences < max_abs:
                valid_emails.append(str(row.iloc[1]).strip().lower())
                
        if valid_emails:
            worksheet_names = [ws.title for ws in target_db.worksheets()]
            
            if "اجتماع اليوم" in worksheet_names:
                print("📝 استخدام القالب النصي (اجتماع اليوم)...")
                try:
                    sun_tab = target_db.worksheet("اجتماع اليوم")
                    meeting_topic = sun_tab.acell('F9').value or "موضوع غير محدد"
                    raw_date = sun_tab.acell('D9').value or today_str
                    parts = raw_date.split('-')
                    display_date = f"{int(parts[2])} / {int(parts[1])} / {parts[0]}" if len(parts) == 3 else raw_date
                except:
                    meeting_topic = "موضوع غير محدد"
                    display_date = today_str
                    
                meet_dt = baghdad_tz.localize(datetime.strptime(today_str + " 21:00:00", "%Y-%m-%d %H:%M:%S"))
                tzs = [("Asia/Dubai", "Dubai", "دبي"), ("Asia/Baghdad", "Baghdad", "بغداد"), ("Africa/Cairo", "Cairo", "القاهرة"), ("Europe/London", "London", "لندن"), ("America/New_York", "New_York", "نيويورك")]
                dyn_time = ""
                for tz_name, en_name, ar_name in tzs:
                    loc_time = meet_dt.astimezone(pytz.timezone(tz_name)).strftime("%I:%M%p").upper().lstrip('0')
                    dyn_time += f"{loc_time} -- {en_name}/{ar_name}\n"
                    
                # -- التعديل الجديد لقالب يوم الأحد --
                body = f"👨🏻‍💻👩🏻‍💻 يـرجـى قـــراءة ا لاعـــلان جــيــدا\n\n                   تـــدعـــوكــــم  \n      ༺☆» زمـــالــة الـــخــلـــيـــج »☆༻ \n\n    «☆«☆«☆«☆📖📚📖☆ »☆»☆»☆»\n\n🌅 الـيـوم :- {today_name}\n🗓 الـتـاريـخ :- {display_date}\n\n✍🏼نـوع الاجـتمـاع:- قـــراءه مـــن\n\n  \n🔵🔷🔹📖 {meeting_topic} 🔹🔷🔵\n\n\n🙋🏻‍♀️🙋🏻 تــنــبــيــه هــام :-\nالـحـضـوره فـقـط وحـصـرا لاعـضـاء مـجـمـوعـة زمـالـة الـخـلـيـج الام\n\n༺»مدة الأجـتـمـاع:- 70 دقيقة«༻\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n📟 بداية وقت الاجتماع \n📟 Meeting Start Time\n\nالوقت/Time\n{dyn_time.strip()}\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n1- سيتم نشر رابط الاجتماع على مجموعات زمالة الخليج حصرا قبل «15 دقيقه» من بداية الاجتماع\n2- سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n🔗 رابط تسجيل الدخول للاجتماع (البوابة):\n{PORTAL_LINK}\n\nبـأنـتـظـار حضوركم  !\nنـحــن بـالـفــعـل نـتـعـافـى 🙏🏼"
                
                create_draft("اعلان اجتماع الخليج", body, valid_emails, invite_method, is_html=False)

            elif "Meetings" in worksheet_names:
                print("🎨 استخدام قالب HTML (Meetings)...")
                meeting_topic = "موضوع غير محدد"
                try:
                    meet_tab = target_db.worksheet("Meetings")
                    for row in meet_tab.get_all_values()[1:]:
                        if row and pd.to_datetime(row[0]).strftime("%Y-%m-%d") == today_str:
                            meeting_topic = str(row[1])
                            break
                except:
                    pass

                # -- التعديل الجديد لقالب يوم الأربعاء --
                body_html = f"""<div dir="rtl" style="text-align: right; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6;">
                  ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
                  تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع اليوم: <b>{meeting_topic}</b><br>
                  {today_name} الموافق {today_str.replace('-', '/')}<br><br>
                  
                  <b>لحضور الاجتماع، عليك أن تقوم بالخطوتين التاليتين:</b><br><br>
                  
                  🔗 <b>أولًا: التسجيل لأول مرة فقط حتى يتم عمل حساب لك في زمالة الخليج، لو سجلت سابقا فلا داعي للتسجيل مرة أخرى :</b><br>
                  <a href="{form_link}" style="color: #15c; text-decoration: underline;">{form_link}</a><br><br>
                  
                  🔗 <b>بعد عمل الحساب، تستطيع الدخول إلى هنا واختيار الاجتماع الذي سجلت فيه وادخال إيميلك الذي استخدمته في التسجيل للوصول إلى رابط الاجتماع:</b><br>
                  <a href="{PORTAL_LINK}" style="color: #15c; text-decoration: underline;">بوابة تسجيل الحضور</a><br><br>
                  
                  نحن بالفعل نتعافى!</div>"""
                
                batch_size = 45
                for i in range(0, len(valid_emails), batch_size):
                    create_draft(f"دعوة زمالة الخليج - {today_str}", body_html, valid_emails[i:i+batch_size], invite_method, is_html=True)
        else:
            print("⚠️ لا يوجد أشخاص مؤهلين لاستلام الدعوة.")
    else:
        print(f"💤 لا يوجد اجتماع مبرمج لليوم ({today_name}).")

    # ==========================================
    # 2. YESTERDAY'S LOGIC (GENTLE NOTICES AS DRAFTS)
    # ==========================================
    yesterday_meeting = meetings_data[meetings_data['Meeting Day'] == yesterday_name]
    if not yesterday_meeting.empty:
        print(f"📅 تم العثور على اجتماع يوم الأمس ({yesterday_name}). جاري فحص الغيابات...")
        meeting_info = yesterday_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        
        target_db = client.open_by_key(target_id)
        reg_df = pd.DataFrame(target_db.worksheet("Registration").get_all_records())
        
        try:
            check_in_df = pd.DataFrame(target_db.worksheet("Check-In Log").get_all_records())
            yesterday_attendees = check_in_df[check_in_df['Timestamp'].astype(str).str.contains(yesterday_date_str, na=False)]['Email'].str.lower().str.strip().tolist()
        except:
            yesterday_attendees = []

        absent_emails = []
        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            absences = get_safe_absences(row)
            
            if email not in yesterday_attendees and absences < max_abs:
                absent_emails.append(email)

        if absent_emails:
            print(f"⚠️ تم رصد {len(absent_emails)} غياب. جاري إنشاء مسودة التنبيه (BCC)...")
            notice_subject = "نفتقدك في زمالة الخليج"
            notice_body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماع يوم {yesterday_name}، ونتمنى أن تكون بخير.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك قريباً.\n\nنحن بالفعل نتعافى!"
            
            batch_size = 45
            for i in range(0, len(absent_emails), batch_size):
                create_draft(notice_subject, notice_body, absent_emails[i:i+batch_size], "BCC", is_html=False)
        else:
            print("✅ لا توجد غيابات تستحق التنبيه (الجميع حضر أو وصلوا للحد الأقصى).")
    else:
        print(f"💤 لم يكن هناك اجتماع مبرمج بالأمس ({yesterday_name}).")

if __name__ == "__main__":
    run_robot()
