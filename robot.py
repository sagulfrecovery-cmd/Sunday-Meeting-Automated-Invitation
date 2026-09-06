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
import urllib.request
import urllib.error

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
last_week_date_str = (baghdad_now - timedelta(days=7)).strftime("%Y-%m-%d")

days_ar = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
today_name = days_ar[baghdad_now.weekday()]

print(f"🤖 استيقظ الروبوت... اليوم: {today_name} | تاريخ الأسبوع الماضي: {last_week_date_str}")

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

# --- MAINTENANCE LOGIC (BOUNCES, 90-DAY RETENTION & 120-DAY CHECK-IN CLEANUP) ---
def run_maintenance(meetings_data):
    print("🛠️ بدء عملية الصيانة الدورية (المرتجعات، الاحتفاظ بالبيانات، وتنظيف سجلات الحضور)...")
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
    
    cutoff_date_90 = datetime.now() - timedelta(days=90)
    cutoff_date_120 = datetime.now() - timedelta(days=120)
    
    for target_id in unique_targets:
        try:
            target_db = client.open_by_key(str(target_id).strip())
            reg_tab = target_db.worksheet("Registration")
            reg_records = reg_tab.get_all_records()
            
            try:
                check_in_tab = target_db.worksheet("Check-In Log")
                check_in_records = check_in_tab.get_all_records()
                
                # --- 🟢 تنظيف سجلات الحضور (Check-In Log) الأقدم من 120 يوماً ---
                ci_rows_to_delete = []
                for j, ci_row in enumerate(check_in_records):
                    ts = str(ci_row.get('Timestamp', ''))
                    if ts:
                        try:
                            date_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                            if date_obj < cutoff_date_120:
                                ci_rows_to_delete.append(j + 2)
                        except:
                            pass
                
                for row_num in sorted(list(set(ci_rows_to_delete)), reverse=True):
                    check_in_tab.delete_rows(row_num)
                    time.sleep(1.5)
                
                if ci_rows_to_delete:
                    print(f"🧹 تم مسح {len(ci_rows_to_delete)} سجل حضور قديم (تجاوز 120 يوماً).")
                # -------------------------------------------------------------
                
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
                
                if em in bounced_emails:
                    rows_to_delete.append(i + 2)
                    continue
                    
                if absences >= max_abs:
                    last_active = last_seen.get(em)
                    if not last_active or last_active < cutoff_date_90:
                        rows_to_delete.append(i + 2)
                        
            for row_num in sorted(list(set(rows_to_delete)), reverse=True):
                reg_tab.delete_rows(row_num)
                time.sleep(1.5)
                
            if rows_to_delete:
                print(f"🧹 تم تنظيف {len(rows_to_delete)} سجل من التسجيل (مرتدة أو متوقفة لـ 90 يوماً).")
                
        except Exception as e:
            pass
    print("✨ تمت عملية الصيانة بنجاح.")

# --- MAIN LOGIC ---
def run_robot():
    master_sheet = None
    for attempt in range(5):
        try:
            master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
            break
        except Exception as e:
            if attempt < 4:
                wait_time = 5 * (attempt + 1)
                print(f"⚠️ سيرفرات جوجل مشغولة. إعادة المحاولة بعد {wait_time} ثوانٍ...")
                time.sleep(wait_time)
            else:
                raise e
                
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    run_maintenance(meetings_data)
    
    # ==========================================
    # 1. INTEGRATED LOGIC: CHECK LAST WEEK -> UPDATE EXCEL -> SEND TODAY'S INVITES
    # ==========================================
    today_meeting = meetings_data[meetings_data['Meeting Day'] == today_name]
    if not today_meeting.empty:
        print(f"📅 تم العثور على اجتماع اليوم ({today_name}). جاري التحضير وفحص حضور الأسبوع الماضي...")
        
        print("🌐 جاري إرسال نبضة لإيقاظ البوابة...")
        for attempt in range(3):
            try:
                req = urllib.request.Request(PORTAL_LINK, headers={'User-Agent': 'Mozilla/5.0'})
                urllib.request.urlopen(req, timeout=10)
                print("✅ تم إيقاظ البوابة بنجاح!")
                break
            except urllib.error.HTTPError as e:
                print(f"✅ البوابة مستيقظة وتتجاوب (رمز الاستجابة: {e.code})!")
                break
            except Exception as e:
                if attempt < 2: time.sleep(5)
                else:
                    print("❌ فشل إيقاظ البوابة، جاري إرسال تنبيه للإدارة...")
                    alert_subject = "🚨 تنبيه عاجل: فشل إيقاظ بوابة زمالة الخليج"
                    alert_emails = "ameermam.sa@gmail.com, keepcomingback.29@gmail.com"
                    alert_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6; text-align: right;">
                        <h3 style="color: #c62828;">⚠️ تعذر الوصول إلى بوابة تسجيل الحضور</h3>
                        <p>تفاصيل الخطأ: <span style="direction: ltr; display: inline-block;">{e}</span></p>
                        <br>🔗 <a href="{PORTAL_LINK}">زيارة البوابة يدوياً</a></div>"""
                    send_admin_report(alert_subject, alert_body, alert_emails)
        
        meeting_info = today_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        invite_method = str(meeting_info['Invite Method']).strip()
        form_link = str(meeting_info.get('Form Link', PORTAL_LINK)).strip()
        if not form_link: form_link = PORTAL_LINK
        
        target_db = client.open_by_key(target_id)
        reg_tab = target_db.worksheet("Registration")
        reg_df = pd.DataFrame(reg_tab.get_all_records())
        
        try:
            check_in_tab = target_db.worksheet("Check-In Log")
            check_in_df = pd.DataFrame(check_in_tab.get_all_records())
            last_week_attendees = check_in_df[check_in_df['Timestamp'].astype(str).str.contains(last_week_date_str, na=False)]['Email'].str.lower().str.strip().tolist()
        except:
            last_week_attendees = []

        abs_col_name = 'Absences' if 'Absences' in reg_df.columns else 'الغيابات'
        abs_col_idx = reg_df.columns.get_loc(abs_col_name) + 1

        valid_emails = []
        removed_emails = []
        warned_emails = []
        absent_last_week = []
        
        # 🟢 الخطوة أ: تحديث الغيابات في الإكسل بناءً على حضور الأسبوع الماضي
        for index, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            if not email: continue
            
            current_absences = get_safe_absences(row)
            new_absences = current_absences
            
            if email not in last_week_attendees:
                new_absences = current_absences + 1
                reg_tab.update_cell(index + 2, abs_col_idx, new_absences)
                time.sleep(1)
                if new_absences < max_abs:
                    absent_last_week.append(email)
            elif current_absences > 0:
                new_absences = 0
                reg_tab.update_cell(index + 2, abs_col_idx, 0)
                time.sleep(1)
            
            # 🟢 الخطوة ب: فرز الأعضاء بناءً على الأرقام المحدثة لتجهيز دعوات اليوم
            if new_absences >= max_abs:
                removed_emails.append(email)
            else:
                valid_emails.append(email)
                if new_absences > 0:
                    warned_emails.append(email)

        # 🟢 الخطوة ج: إرسال الإيميلات
        if absent_last_week:
            print(f"⚠️ تجهيز التنبيه لـ {len(absent_last_week)} شخص غابوا الأسبوع الماضي...")
            notice_subject = "نفتقدك في زمالة الخليج"
            notice_body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماعنا الأخير، ونتمنى أن تكون بخير.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك في اجتماع اليوم.\n\nنحن بالفعل نتعافى!"
            batch_size = 45
            for i in range(0, len(absent_last_week), batch_size):
                create_draft(notice_subject, notice_body, absent_last_week[i:i+batch_size], "BCC", is_html=False)

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
                dyn_time_html = "".join([f"{meet_dt.astimezone(pytz.timezone(tz[0])).strftime('%I:%M %p').upper().lstrip('0')} -- {tz[1]}/{tz[2]}<br>" for tz in tzs])
                
                body_html_sun = f"""<div dir="rtl" style="text-align: right; font-family: Arial; font-size: 16px; line-height: 1.6;">
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
                    <div style="direction: ltr; text-align: right;">{dyn_time_html}</div>
                    <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                    سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع<br>
                    <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                    🔗 <b>رابط تسجيل الدخول للاجتماع (البوابة) - في حال عدم عمل الموقع يرجى اعادة تحميل الصفحة:</b><br>
                    <a href="{PORTAL_LINK}" style="color: #15c; text-decoration: underline;">بوابة تسجيل الحضور</a><br><br>
                    بـأنـتـظـار حضوركم !<br>نـحــن بـالـفــعـل نـتـعـافـى 🙏🏼</div>"""
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
                except: pass

                body_html = f"""<div dir="rtl" style="text-align: right; font-family: Arial; font-size: 16px; line-height: 1.6;">
                  ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
                  تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع اليوم: <b>{meeting_topic}</b><br>
                  {today_name} الموافق {today_str.replace('-', '/')}<br><br>
                  <b>لحضور الاجتماع، عليك أن تقوم بالخطوتين التاليتين:</b><br><br>
                  🔗 <b>أولًا: التسجيل لأول مرة فقط:</b><br>
                  <a href="{form_link}">{form_link}</a><br><br>
                  🔗 <b>ثانياً: لتسجيل الحضور والحصول على الرابط - في حال عدم عمل الموقع، يرجى إعادة تحميل الصفحة:</b><br>
                  <a href="{PORTAL_LINK}">بوابة تسجيل الحضور</a><br><br>
                  نحن بالفعل نتعافى!</div>"""
                batch_size = 45
                for i in range(0, len(valid_emails), batch_size):
                    create_draft(f"دعوة زمالة الخليج - {today_str}", body_html, valid_emails[i:i+batch_size], invite_method, is_html=True)

        # 3. إرسال تقرير الإدارة الشامل
        admin_subject = f"📊 تقرير زمالة الخليج الشامل لاجتماع اليوم - {today_str}"
        admin_emails = "ameermam.sa@gmail.com, keepcomingback.29@gmail.com, sagulf.recovery@gmail.com"
        html_list = lambda lst: "".join([f"<li>{e}</li>" for e in sorted(lst)]) if lst else "<li>لا يوجد</li>"
        
        admin_body = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; font-size: 15px; line-height: 1.6;">
            <h3>✅ تم الانتهاء من جميع المهام وتجهيز مسودات الإيميلات بنجاح!</h3>
            <p>قام الروبوت بفحص حضور الأسبوع الماضي (تاريخ: {last_week_date_str})، وقام بتحديث الغيابات في الإكسل، وبناءً عليها أعد الدعوات لاجتماع اليوم.</p>
            <hr>
            <h4 style="color: #2e7d32;">📩 قائمة المستلمين للدعوة اليوم ({len(valid_emails)} شخص):</h4>
            <ul>{html_list(valid_emails)}</ul>
            
            <h4 style="color: #1565c0;">⚠️ أشخاص غابوا الأسبوع الماضي وتم إرسال مسودة تنبيه لهم ({len(absent_last_week)} شخص):</h4>
            <ul>{html_list(absent_last_week)}</ul>
            
            <h4 style="color: #f57c00;">⚠️ إجمالي الأعضاء المنذرين في النظام (غياب 1 إلى {max_abs - 1}) ({len(warned_emails)} شخص):</h4>
            <ul>{html_list(warned_emails)}</ul>
            
            <h4 style="color: #c62828;">🚫 أشخاص تجاوزوا الحد الأقصى وتم حذفهم ({len(removed_emails)} شخص):</h4>
            <ul>{html_list(removed_emails)}</ul>
        </div>
        """
        send_admin_report(admin_subject, admin_body, admin_emails)

if __name__ == "__main__":
    run_robot()
