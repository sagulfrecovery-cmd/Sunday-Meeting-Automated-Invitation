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

# --- EMAIL FUNCTIONS ---
def create_draft(subject, body, emails, invite_method, is_html=False):
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
        print(f"Draft '{subject}' created successfully for {len(emails)} people.")
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
    
    # ==========================================
    # 1. TODAY'S MEETING LOGIC (CREATE DRAFTS)
    # ==========================================
    today_meeting = meetings_data[meetings_data['Meeting Day'] == today_name]
    if not today_meeting.empty:
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
            raw_abs = row.get('Absences', row.get('الغيابات', 0))
            absences = int(raw_abs) if str(raw_abs).strip() != '' else 0
            if absences < max_abs:
                valid_emails.append(str(row.iloc[1]).strip().lower())
                
        if valid_emails:
            # 💡 التعديل الجديد: الروبوت يحدد نوع القالب بناءً على محتوى الملف وليس اسم اليوم
            worksheet_names = [ws.title for ws in target_db.worksheets()]
            
            if "اجتماع اليوم" in worksheet_names:
                # --- TEXT TEMPLATE LOGIC (القالب الأول) ---
                try:
                    sun_tab = target_db.worksheet("اجتماع اليوم")
                    meeting_topic = sun_tab.acell('F9').value or "موضوع غير محدد"
                    raw_date = sun_tab.acell('D9').value or today_str
                    parts = raw_date.split('-')
                    if len(parts) == 3:
                        display_date = f"{int(parts[2])} / {int(parts[1])} / {parts[0]}"
                    else:
                        display_date = raw_date
                except:
                    meeting_topic = "موضوع غير محدد"
                    display_date = today_str
                    
                meet_dt = baghdad_tz.localize(datetime.strptime(today_str + " 21:00:00", "%Y-%m-%d %H:%M:%S"))
                tzs = [
                    ("Asia/Dubai", "Dubai", "دبي"), ("Asia/Muscat", "Muscat", "مسقط"),
                    ("Asia/Baghdad", "Baghdad", "بغداد"), ("Asia/Riyadh", "Riyadh", "الرياض"),
                    ("Africa/Cairo", "Cairo", "القاهرة"), ("Europe/Berlin", "Berlin", "برلين"),
                    ("Europe/Madrid", "Madrid", "مدريد"), ("Africa/Casablanca", "Casablanca", "الدار البيضاء"),
                    ("Europe/London", "London", "لندن"), ("America/New_York", "New_York", "نيويورك"),
                    ("America/Chicago", "Chicago", "شيكاغو"), ("America/Denver", "Denver", "دنفر"),
                    ("America/Phoenix", "Phoenix", "فينيكس"), ("America/Los_Angeles", "Los_Angeles", "لوس أنجلوس")
                ]
                dyn_time = ""
                for tz_name, en_name, ar_name in tzs:
                    loc_tz = pytz.timezone(tz_name)
                    loc_time = meet_dt.astimezone(loc_tz).strftime("%I:%M%p").upper()
                    if loc_time.startswith('0'): loc_time = loc_time[1:]
                    dyn_time += f"{loc_time} -- {en_name}/{ar_name}\n"
                    
                body = f"👨🏻‍💻👩🏻‍💻 يـرجـى قـــراءة ا لاعـــلان جــيــدا\n\n                   تـــدعـــوكــــم  \n      ༺☆» زمـــالــة الـــخــلـــيـــج »☆༻ \n\n    «☆«☆«☆«☆📖📚📖☆ »☆»☆»☆»\n\n🌅 الـيـوم :- {today_name}\n🗓 الـتـاريـخ :- {display_date}\n\n✍🏼نـوع الاجـتمـاع:- قـــراءه مـــن\n\n  \n🔵🔷🔹📖 {meeting_topic} 🔹🔷🔵\n\n\n🙋🏻‍♀️🙋🏻 تــنــبــيــه هــام :-\nالـحـضـوره فـقـط وحـصـرا لاعـضـاء مـجـمـوعـة زمـالـة الـخـلـيـج الام\n\n༺»مدة الأجـتـمـاع:- 70 دقيقة«༻\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n📟 بداية وقت الاجتماع \n📟 Meeting Start Time\n\nالوقت/Time\n{dyn_time.strip()}\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n1- سيتم نشر رابط الاجتماع على مجموعات زمالة الخليج حصرا قبل «15 دقيقه» من بداية الاجتماع\n2- سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع\n\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-\n\n🔗 رابط تسجيل الدخول للاجتماع (البوابة):\n{PORTAL_LINK}\n\n🔗 رابط استبيان اليوم:\n{form_link}\n\nبـأنـتـظـار حضوركم  !\nنـحــن بـالـفــعـل نـتـعـافـى 🙏🏼"
                
                subject = "اعلان اجتماع الخليج"
                create_draft(subject, body, valid_emails, invite_method, is_html=False)

            elif "Meetings" in worksheet_names:
                # --- HTML TEMPLATE LOGIC (القالب الثاني) ---
                meeting_topic = "موضوع غير محدد"
                try:
                    meet_tab = target_db.worksheet("Meetings")
                    m_data = meet_tab.get_all_values()
                    for row in m_data[1:]:
                        if not row: continue
                        try:
                            # يحاول الروبوت العثور على تاريخ اليوم في الجدول
                            row_date = pd.to_datetime(row[0]).strftime("%Y-%m-%d")
                            if row_date == today_str:
                                meeting_topic = str(row[1])
                                break
                        except:
                            continue
                except:
                    pass

                meet_utc = pytz.utc.localize(datetime.strptime(today_str + " 17:30:00", "%Y-%m-%d %H:%M:%S"))
                cities = [
                    ("Asia/Dubai", "دبي / مسقط"), ("Asia/Riyadh", "الرياض"),
                    ("Asia/Baghdad", "بغداد"), ("Africa/Cairo", "القاهرة"),
                    ("Africa/Casablanca", "الدار البيضاء")
                ]
                time_groups = {}
                for tz_name, c_name in cities:
                    loc_tz = pytz.timezone(tz_name)
                    loc_time = meet_utc.astimezone(loc_tz).strftime("%I:%M %p").replace('PM', 'مساءً').replace('AM', 'صباحًا')
                    if loc_time.startswith('0'): loc_time = loc_time[1:]
                    if loc_time not in time_groups:
                        time_groups[loc_time] = []
                    time_groups[loc_time].append(c_name)
                
                time_html = ""
                for t in sorted(time_groups.keys(), reverse=True):
                    time_html += f"{t} — {' / '.join(time_groups[t])}<br>"

                body_html = f"""
                <div dir="rtl" style="text-align: right; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6;">
                  ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
                  تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع القادم الجديد، وموضوع اجتماع اليوم هو:<br><br>
                  
                  {meeting_topic}<br>
                  {today_name} الموافق {today_str.replace('-', '/')}<br><br>
                  
                  📌 <b>ملاحظة هامة:</b><br>
                  تُغلق الغرفة بعد 20 دقيقة من بدء الاجتماع.<br>
                  كونوا أمناء — شكرًا لتفهّمكم.<br><br>
                  
                   <b>بداية وقت الاجتماع:</b><br>
                  {time_html}<br><br>
                  
                  🔗 <b>للحصول على رابط الدخول للزوم، يرجى تسجيل حضورك عبر البوابة:</b><br>
                  <a href="{PORTAL_LINK}" style="color: #15c; text-decoration: underline;">بوابة تسجيل الحضور</a><br><br>
                  
                  🔗 <b>رابط استبيان اليوم:</b><br>
                  <a href="{form_link}" style="color: #15c; text-decoration: underline;">{form_link}</a><br><br>
                  
                  بـانـتـظـاركـم!<br><br>
                  
                  لقراءة ملف الورشة، يرجى زيارة الموقع أدناه: <br>
                  https://12-steps-guide.blogspot.com/ <br><br>

                  نحن بالفعل نتعافى!<br><br>
                  ملاحظة، في حال الرغبة بحذفكم من قائمة البريد الألكتروني، يرجى الرد على هذا الإيميل وطلب أن يتم حذفكم.
                </div>
                """
                
                subject = f"دعوة لاجتماع زمالة الخليج - {today_str.replace('-', '/')}"
                
                batch_size = 45
                for i in range(0, len(valid_emails), batch_size):
                    batch = valid_emails[i:i+batch_size]
                    draft_subj = subject if len(valid_emails) <= batch_size else f"{subject} (Part {i//batch_size + 1})"
                    create_draft(draft_subj, body_html, batch, invite_method, is_html=True)

    # ==========================================
    # 2. YESTERDAY'S LOGIC (GENTLE NOTICES)
    # ==========================================
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

        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            raw_abs = row.get('Absences', row.get('الغيابات', 0))
            absences = int(raw_abs) if str(raw_abs).strip() != '' else 0
            
            if email not in yesterday_attendees and absences < max_abs:
                send_gentle_notice(email, yesterday_name)

if __name__ == "__main__":
    run_robot()
