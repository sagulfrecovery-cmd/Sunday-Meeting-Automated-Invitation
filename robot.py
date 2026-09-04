import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import smtplib
import imaplib
import email
import re
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

def send_admin_report(subject, html_body, to_emails):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_emails
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"📧 تم إرسال تقرير الإدارة بنجاح.")
    except Exception as e:
        print(f"❌ فشل في إرسال تقرير الإدارة: {e}")

# --- MAINTENANCE LOGIC (BOUNCES & 90-DAY RETENTION) ---
def run_maintenance(meetings_data):
    print("🛠️ بدء عملية الصيانة الدورية (فحص المرتجعات والاحتفاظ بالبيانات)...")
    bounced_emails = set()
    try:
        imap = imaplib.IMAP4_SSL('imap.gmail.com')
        imap.login(SENDER_EMAIL, APP_PASSWORD)
        imap.select('INBOX')
        typ, data = imap.search(None, '(SUBJECT "Undelivered Mail Returned to Sender")')
        for num in data[0].split():
            typ, msg_data = imap.fetch(num, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors='ignore')
                                match = re.search(r'<([^>]+)>', body)
                                if match:
                                    bounced_emails.add(match.group(1).lower())
        imap.logout()
        if bounced_emails: print(f"⚠️ تم رصد {len(bounced_emails)} إيميل مرتد (وهمي). سيتم حذفها.")
    except Exception as e:
        print(f"❌ خطأ في فحص الإيميلات المرتدة: {e}")

    unique_targets = meetings_data['Target Sheet ID'].dropna().unique()
    ninety_days_ago = datetime.now() - timedelta(days=90)
    
    for target_id in unique_targets:
        try:
            target_db = client.open_by_key(str(target_id).strip())
            reg_tab = target_db.worksheet("Registration")
            reg_records = reg_tab.get_all_records()
            
            try:
                check_in_tab = target_db.worksheet("Check-In Log")
                check_in_records = check_in_tab.get_all_records()
            except:
                check_in_records = []
                
            last_seen = {}
            for row in check_in_records:
                em = str(row.get('Email', '')).strip().lower()
                ts = str(row.get('Timestamp', ''))
                if em and ts:
                    try:
                        date_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        if em not in last_seen or date_obj > last_seen[em]:
                            last_seen[em] = date_obj
                    except:
                        pass
            
            target_info = meetings_data[meetings_data['Target Sheet ID'] == target_id].iloc[0]
            max_abs = int(target_info.get('Max Absences', 4))
            
            rows_to_delete = []
            for i, row in enumerate(reg_records):
                em = str(row.get('Email', '')).strip().lower()
                if not em: continue
                absences = get_safe_absences(row)
                
                # 1. حذف الإيميلات المرتدة (Bounces)
                if em in bounced_emails:
                    rows_to_delete.append(i + 2)
                    continue
                    
                # 2. حذف الحسابات الميتة (أكثر من 90 يوم مع وصول الحد الأقصى)
                if absences >= max_abs:
                    last_active = last_seen.get(em)
                    if not last_active or last_active < ninety_days_ago:
                        rows_to_delete.append(i + 2)
                        
            # تنفيذ الحذف من الأسفل للأعلى
            for row_num in sorted(list(set(rows_to_delete)), reverse=True):
                reg_tab.delete_rows(row_num)
                time.sleep(1.5) # لتجنب حظر جوجل API
                
            if rows_to_delete:
                print(f"🧹 تم تنظيف {len(rows_to_delete)} سجل في الملف (مرتدة أو قديمة).")
                
        except Exception as e:
            pass
    print("✨ تمت عملية الصيانة بنجاح.")

# --- MAIN LOGIC ---
def run_robot():
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    
    # تنفيذ الصيانة والتنظيف قبل قراءة البيانات للإرسال
    run_maintenance(meetings_data)
    
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
        removed_emails = []
        warned_emails = []
        
        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            if not email: continue
            
            absences = get_safe_absences(row)
            if absences >= max_abs:
                removed_emails.append(email)
            else:
                valid_emails.append(email)
                if absences > 0:
                    warned_emails.append(email)
                
        if valid_emails:
            worksheet_names = [ws.title for ws in target_db.worksheets()]
            
            if "اجتماع اليوم" in worksheet_names:
                print("📝 استخدام القالب الجديد HTML (اجتماع الأحد)...")
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
                dyn_time_html = ""
                for tz_name, en_name, ar_name in tzs:
                    loc_time = meet_dt.astimezone(pytz.timezone(tz_name)).strftime("%I:%M %p").upper().lstrip('0')
                    dyn_time_html += f"{loc_time} -- {en_name}/{ar_name}<br>"
                    
                # القالب الجديد لاجتماع الأحد بصيغة HTML الأنيقة
                body_html_sun = f"""
                <div dir="rtl" style="text-align: right; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6;">
                    👨🏻‍💻👩🏻‍💻 <b>يـرجـى قـــراءة ا لاعـــلان جــيــدا</b><br><br>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;تـــدعـــوكــــم<br>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;༺☆» <b>زمـــالــة الـــخــلـــيـــج</b> »☆༻<br><br>
                    &nbsp;&nbsp;&nbsp;&nbsp;«☆«☆«☆«☆📖📚📖☆ »☆»☆»☆»<br><br>
                    🌅 <b>الـيـوم:</b> {today_name}<br>
                    🗓 <b>الـتـاريـخ:</b> {display_date}<br><br>
                    ✍🏼 <b>نـوع الاجـتمـاع:</b> قـــراءه مـــن<br><br>
                    🔵🔷🔹📖 <b>{meeting_topic}</b> 🔹🔷🔵<br><br><br>
                    🙋🏻‍♀️🙋🏻 <b>تــنــبــيــه هــام:</b><br>
                    الـحـضـوره فـقـط وحـصـرا لاعـضـاء مـجـمـوعـة زمـالـة الـخـلـيـج الام<br><br>
                    ༺» مدة الأجـتـمـاع: 70 دقيقة «༻<br><br>
                    <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                    📟 <b>بداية وقت الاجتماع</b><br>
                    📟 <b>Meeting Start Time</b><br><br>
                    الوقت/Time<br>
                    <div style="direction: ltr; text-align: right;">
                    {dyn_time_html}
                    </div>
                    <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                    سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع<br>
                    <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                    🔗 <b>رابط تسجيل الدخول للاجتماع (البوابة):</b><br>
                    <a href="{PORTAL_LINK}" style="color: #15c; text-decoration: underline;">بوابة تسجيل الحضور</a><br><br>
                    بـأنـتـظـار حضوركم !<br>
                    نـحــن بـالـفــعـل نـتـعـافـى 🙏🏼
                </div>
                """
                # استخدمنا is_html=True 
                create_draft("اعلان اجتماع الخليج", body_html_sun, valid_emails, invite_method, is_html=True)

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
            
            # --- 📨 تقرير الإدارة 1: دعوة الاجتماع ---
            admin_subject_1 = f"📊 تقرير إنشاء مسودات دعوات زمالة الخليج - {today_str}"
            admin_emails_1 = "ameermam.sa@gmail.com, keepcomingback.29@gmail.com, sagulf.recovery@gmail.com"
            
            html_list = lambda lst: "".join([f"<li>{e}</li>" for e in sorted(lst)]) if lst else "<li>لا يوجد</li>"
            
            admin_body_1 = f"""
            <div dir="rtl" style="font-family: Arial, sans-serif; font-size: 15px; line-height: 1.6;">
                <h3>✅ تم تجهيز مسودات الدعوات بنجاح!</h3>
                <p>تم إعداد المسودات في حساب الإيميل، يرجى مراجعتها وإرسالها.</p>
                <hr>
                <h4 style="color: #2e7d32;">📩 قائمة المستلمين المعتمدين للدعوة ({len(valid_emails)} شخص):</h4>
                <ul>{html_list(valid_emails)}</ul>
                
                <h4 style="color: #f57c00;">⚠️ أشخاص عليهم إنذارات (غياب 1 إلى {max_abs - 1}) ({len(warned_emails)} شخص):</h4>
                <ul>{html_list(warned_emails)}</ul>
                
                <h4 style="color: #c62828;">🚫 أشخاص تم حذفهم واستبعادهم (تجاوزوا الحد الأقصى) ({len(removed_emails)} شخص):</h4>
                <ul>{html_list(removed_emails)}</ul>
            </div>
            """
            send_admin_report(admin_subject_1, admin_body_1, admin_emails_1)

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
        removed_emails_yest = []
        warned_emails_yest = []
        
        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            if not email: continue
            
            absences = get_safe_absences(row)
            if absences >= max_abs:
                removed_emails_yest.append(email)
            else:
                if absences > 0:
                    warned_emails_yest.append(email)
                if email not in yesterday_attendees:
                    absent_emails.append(email)

        if absent_emails:
            print(f"⚠️ تم رصد {len(absent_emails)} غياب. جاري إنشاء مسودة التنبيه (BCC)...")
            notice_subject = "نفتقدك في زمالة الخليج"
            notice_body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماع يوم {yesterday_name}، ونتمنى أن تكون بخير.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك قريباً.\n\nنحن بالفعل نتعافى!"
            
            batch_size = 45
            for i in range(0, len(absent_emails), batch_size):
                create_draft(notice_subject, notice_body, absent_emails[i:i+batch_size], "BCC", is_html=False)
            
            # --- 📨 تقرير الإدارة 2: تنبيه الغيابات ---
            admin_subject_2 = f"📊 تقرير مسودات تنبيه الغياب لاجتماع {yesterday_name}"
            admin_emails_2 = "sagulf.recovery@gmail.com"
            
            html_list = lambda lst: "".join([f"<li>{e}</li>" for e in sorted(lst)]) if lst else "<li>لا يوجد</li>"
            
            admin_body_2 = f"""
            <div dir="rtl" style="font-family: Arial, sans-serif; font-size: 15px; line-height: 1.6;">
                <h3>⚠️ تم تجهيز مسودات التنبيه للمتغيبين بنجاح!</h3>
                <p>تم إعداد مسودة مخفية (BCC) في حساب الإيميل، يرجى مراجعتها وإرسالها.</p>
                <hr>
                <h4 style="color: #1565c0;">📩 قائمة المتغيبين الموجه لهم التنبيه ({len(absent_emails)} شخص):</h4>
                <ul>{html_list(absent_emails)}</ul>
                
                <h4 style="color: #f57c00;">⚠️ إجمالي الأعضاء المنذرين في النظام (غياب 1 إلى {max_abs - 1}) ({len(warned_emails_yest)} شخص):</h4>
                <ul>{html_list(warned_emails_yest)}</ul>
                
                <h4 style="color: #c62828;">🚫 أشخاص محذوفون لا يتم إرسال التنبيه لهم (تجاوزوا الحد الأقصى) ({len(removed_emails_yest)} شخص):</h4>
                <ul>{html_list(removed_emails_yest)}</ul>
            </div>
            """
            send_admin_report(admin_subject_2, admin_body_2, admin_emails_2)

        else:
            print("✅ لا توجد غيابات تستحق التنبيه.")

if __name__ == "__main__":
    run_robot()
