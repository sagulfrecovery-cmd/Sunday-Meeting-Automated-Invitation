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
ADMIN_EMAILS = "ameermam.sa@gmail.com, keepcomingback.29@gmail.com, sagulf.recovery@gmail.com"

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
yesterday_date_str = (baghdad_now - timedelta(days=1)).strftime("%Y-%m-%d")

days_ar = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
today_name = days_ar[baghdad_now.weekday()]
yesterday_name = days_ar[(baghdad_now.weekday() - 1) % 7]

print(f"🤖 Robot Awake... Today: {today_name} ({today_str}) | Yesterday: {yesterday_name} ({yesterday_date_str})")

# --- HELPER FUNCTIONS ---
def get_safe_absences(row):
    raw_abs = row.get('Absences', row.get('الغيابات', 0))
    try:
        return int(float(raw_abs))
    except (ValueError, TypeError):
        return 0

def send_email(subject, html_body, to_emails):
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
        print(f"📧 Email sent successfully: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email '{subject}': {e}")

def create_draft(subject, body, emails, invite_method, is_html=False, static_to=None):
    if not emails: return
    
    msg = MIMEMultipart('alternative') if is_html else MIMEText(body, 'plain', 'utf-8')
    if is_html: msg.attach(MIMEText(body, 'html', 'utf-8'))
        
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    
    if static_to: msg['To'] = static_to
    
    if invite_method.upper() == 'BCC':
        msg['Bcc'] = ", ".join(emails)
    elif invite_method.upper() == 'CC':
        msg['Cc'] = ", ".join(emails)
    elif invite_method.upper() == 'TO':
        msg['To'] = static_to + ", " + ", ".join(emails) if static_to else ", ".join(emails)
    else:
        msg['Cc'] = ", ".join(emails)
        
    try:
        imap = imaplib.IMAP4_SSL('imap.gmail.com')
        imap.login(SENDER_EMAIL, APP_PASSWORD)
        imap.append('[Gmail]/Drafts', '', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        imap.logout()
        print(f"✅ Draft created '{subject}' for {len(emails)} recipients.")
    except Exception as e:
        print(f"❌ Failed to create draft: {e}")

def send_halt_alert(meeting_name, sheet_id, issue_desc, solution_desc):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    subject = f"🚨 توقف طارئ: خطأ في إعدادات اجتماع ({meeting_name})"
    body = f"""<div dir="rtl" style="font-family: Arial; font-size: 16px; line-height: 1.6; color: #333;">
        <h2 style="color: #c62828;">توقف طارئ (Fail-Fast) 🛑</h2>
        <p>مرحباً،<br>توقف الروبوت عن أداء مهام اجتماع <b>{meeting_name}</b> لحماية البيانات بسبب وجود خطأ في ملف الإكسل.</p>
        <p><b>وصف المشكلة:</b> {issue_desc}</p>
        <p><b>الحل المطلوب:</b> <span style="color: #1565c0; font-weight: bold;">{solution_desc}</span></p>
        <p><b>رابط الملف المباشر للإصلاح:</b><br><a href="{sheet_url}">{sheet_url}</a></p>
        <hr>
        <small style="color: gray;">الروبوت لن يقوم بأي عمل يخص هذا الاجتماع حتى يتم تصحيح الخطأ.</small>
    </div>"""
    send_email(subject, body, ADMIN_EMAILS)
    print(f"🛑 HALT TRIGGERED: {issue_desc}")

def get_dynamic_time_html(utc_time_str):
    try:
        utc_dt = pytz.utc.localize(datetime.strptime(today_str + f" {utc_time_str}:00", "%Y-%m-%d %H:%M:%S"))
        tzs = [
            ("Asia/Dubai", "الإمارات وعُمان (دبي/مسقط)"),
            ("Asia/Riyadh", "السعودية والكويت (مكة/الرياض)"),
            ("Asia/Baghdad", "العراق (بغداد)"),
            ("Asia/Amman", "الشام (عَمَّان/دمشق)"),
            ("Asia/Beirut", "لبنان (بيروت)"),
            ("Africa/Cairo", "مصر (القاهرة)")
        ]
        return "".join([f"{utc_dt.astimezone(pytz.timezone(tz[0])).strftime('%I:%M %p').upper().lstrip('0')} -- {tz[1]}<br>" for tz in tzs])
    except Exception as e:
        return f"Error calculating time: {e}"

# --- MAINTENANCE LOGIC ---
def run_maintenance(meetings_data):
    print("🛠️ Starting Maintenance Routine...")
    unique_targets = meetings_data['Target Sheet ID'].dropna().unique()
    cutoff_date_90 = datetime.now() - timedelta(days=90)
    cutoff_date_120 = datetime.now() - timedelta(days=120)
    
    for target_id in unique_targets:
        target_id_str = str(target_id).strip()
        try:
            target_db = client.open_by_key(target_id_str)
            
            # Strict Registration Check
            try:
                reg_tab = target_db.worksheet("Registration")
            except gspread.exceptions.WorksheetNotFound:
                continue # Silent skip in maintenance, alerts happen in daily operations

            # Strict Attendance Check
            try:
                check_in_tab = target_db.worksheet("Attendance")
            except gspread.exceptions.WorksheetNotFound:
                try:
                    check_in_tab = target_db.worksheet("Check-In Log")
                except gspread.exceptions.WorksheetNotFound:
                    continue # Silent skip to protect data

            check_in_records = check_in_tab.get_all_records()
            ci_rows_to_delete = []
            
            # Clean old attendance logs (>120 days)
            for j, ci_row in enumerate(check_in_records):
                ts = str(ci_row.get('Timestamp', ''))
                if ts:
                    try:
                        if datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") < cutoff_date_120:
                            ci_rows_to_delete.append(j + 2)
                    except: pass
            
            for row_num in sorted(list(set(ci_rows_to_delete)), reverse=True):
                check_in_tab.delete_rows(row_num)
                time.sleep(1.5)

            # Map last seen dates
            last_seen = {}
            for row in check_in_records:
                em = str(row.get('Email', row.get('Email Address', ''))).strip().lower()
                ts = str(row.get('Timestamp', ''))
                if em and ts:
                    try:
                        date_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        if em not in last_seen or date_obj > last_seen[em]:
                            last_seen[em] = date_obj
                    except: pass
            
            # Delete inactive members (>90 days & max absences)
            target_info = meetings_data[meetings_data['Target Sheet ID'] == target_id].iloc[0]
            max_abs = int(target_info.get('Max Absences', 4))
            reg_records = reg_tab.get_all_records()
            rows_to_delete = []
            
            for i, row in enumerate(reg_records):
                em = str(row.get('Email Address', row.get('Email', ''))).strip().lower()
                if not em: continue
                absences = get_safe_absences(row)
                
                if absences >= max_abs:
                    last_active = last_seen.get(em)
                    if not last_active or last_active < cutoff_date_90:
                        rows_to_delete.append(i + 2)
                        
            for row_num in sorted(list(set(rows_to_delete)), reverse=True):
                reg_tab.delete_rows(row_num)
                time.sleep(1.5)
                
        except Exception as e:
            print(f"Maintenance Error on {target_id_str}: {e}")
    print("✨ Maintenance completed.")

# --- MAIN LOGIC ---
def run_robot():
    master_sheet = None
    for attempt in range(5):
        try:
            master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
            break
        except Exception as e:
            if attempt < 4: time.sleep(5 * (attempt + 1))
            else: raise e
                
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    run_maintenance(meetings_data)
    
    html_list = lambda lst: "".join([f"<li>{e}</li>" for e in sorted(lst)]) if lst else "<li>لا يوجد</li>"
    action_taken = False

    # ==========================================
    # 1. INVITATIONS DAY (TODAY)
    # ==========================================
    today_meetings = meetings_data[meetings_data['Meeting Day'] == today_name]
    
    if not today_meetings.empty:
        action_taken = True
        print(f"📅 Today ({today_name}): Invitation tasks found.")
        
        # Wake up Streamlit Portal
        try:
            req = urllib.request.Request(f"{PORTAL_LINK.rstrip('/')}/?wake={int(time.time())}", 
                                         headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req, timeout=15)
        except: pass

        # Loop through all meetings scheduled for today
        for _, meeting_info in today_meetings.iterrows():
            meeting_name_master = str(meeting_info.get('Meeting Name', 'اجتماع غير محدد'))
            target_id = str(meeting_info['Target Sheet ID']).strip()
            max_abs = int(meeting_info['Max Absences'])
            invite_method = str(meeting_info['Invite Method']).strip()
            utc_time_str = str(meeting_info.get('Meeting Time UTC', '17:30')).strip()
            form_link = str(meeting_info.get('Form Link', PORTAL_LINK)).strip() or PORTAL_LINK
            
            try:
                target_db = client.open_by_key(target_id)
            except Exception as e:
                send_halt_alert(meeting_name_master, target_id, "لا يمكن الوصول للملف (قد يكون محذوفاً أو غير مصرح به)", "تأكد من وجود الملف وصلاحيات حساب الخدمة (GCP).")
                continue

            # Strict Check: Registration Sheet
            try:
                reg_df = pd.DataFrame(target_db.worksheet("Registration").get_all_records())
            except gspread.exceptions.WorksheetNotFound:
                send_halt_alert(meeting_name_master, target_id, "لم يتم العثور على شيت (Registration).", "يرجى التأكد من اسم شيت التسجيل وأن يكون مطابقاً حرفياً لـ Registration")
                continue

            valid_emails, warned_emails, suspended_emails = [], [], []
            for _, row in reg_df.iterrows():
                email_addr = str(row.iloc[1]).strip().lower()
                if not email_addr: continue
                absences = get_safe_absences(row)
                if absences >= max_abs: suspended_emails.append(email_addr)
                else:
                    valid_emails.append(email_addr)
                    if absences > 0: warned_emails.append(email_addr)

            if valid_emails:
                dyn_time_html = get_dynamic_time_html(utc_time_str)
                meeting_topic = ""
                display_date = today_str
                
                # --- SUNDAY TEMPLATE STRICT CHECK ---
                if today_name == "الأحد":
                    try:
                        sun_tab = target_db.worksheet("اجتماع اليوم")
                    except gspread.exceptions.WorksheetNotFound:
                        send_halt_alert(meeting_name_master, target_id, "لم يتم العثور على شيت (اجتماع اليوم).", "يرجى تعديل اسم الشيت ليكون مطابقاً حرفياً لـ (اجتماع اليوم) بدون مسافات إضافية.")
                        continue
                        
                    topic_val = sun_tab.acell('F9').value
                    if not topic_val or str(topic_val).strip() == "":
                        send_halt_alert(meeting_name_master, target_id, "الخلية F9 في شيت (اجتماع اليوم) فارغة.", "يرجى إضافة موضوع الاجتماع في الخلية F9.")
                        continue
                    
                    meeting_topic = str(topic_val).strip()
                    raw_date = sun_tab.acell('D9').value or today_str
                    parts = str(raw_date).split('-')
                    display_date = f"{int(parts[2])} / {int(parts[1])} / {parts[0]}" if len(parts) == 3 else raw_date
                    
                    body_html = f"""<div dir="rtl" style="text-align: right; font-family: Arial; font-size: 16px; line-height: 1.6;">
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
                        ༺» مدة الأجـتـمـاع: 70 دقيقة «༻<br>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                        📟 <b>بداية وقت الاجتماع</b><br>
                        <div style="direction: ltr; text-align: right;">{dyn_time_html}</div>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                        سـيــتـم غــلــق الـغـرفــة بـعـد «20 دقيقة» من بدء الاجتماع<br>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                        🔗 <b>رابط تسجيل الدخول للاجتماع (البوابة):</b><br>
                        <a href="{PORTAL_LINK}">{PORTAL_LINK}</a><br><br>
                        بـأنـتـظـار حضوركم !<br>نـحــن بـالـفــعـل نـتـعـافـى 🙏🏼</div>"""

                # --- OTHER DAYS (WEDNESDAY) TEMPLATE STRICT CHECK ---
                else:
                    try:
                        meet_tab = target_db.worksheet("Meetings")
                    except gspread.exceptions.WorksheetNotFound:
                        send_halt_alert(meeting_name_master, target_id, "لم يتم العثور على شيت (Meetings).", "يرجى تعديل اسم الشيت ليكون مطابقاً حرفياً لـ (Meetings) بدون مسافات إضافية.")
                        continue
                    
                    found_topic = False
                    for row in meet_tab.get_all_values()[1:]:
                        if row and len(row) >= 2:
                            try:
                                row_date = pd.to_datetime(row[0]).strftime("%Y-%m-%d")
                                if row_date == today_str:
                                    meeting_topic = str(row[1]).strip()
                                    if meeting_topic: found_topic = True
                                    break
                            except: pass
                            
                    if not found_topic:
                        send_halt_alert(meeting_name_master, target_id, f"لم يتم العثور على موضوع لاجتماع اليوم ({today_str}) في شيت Meetings.", "يرجى إضافة تاريخ اليوم والموضوع المقابل له في جدول Meetings.")
                        continue

                    body_html = f"""<div dir="rtl" style="text-align: right; font-family: Arial; font-size: 16px; line-height: 1.6;">
                        ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
                        تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع اليوم: <b>{meeting_topic}</b><br>
                        {today_name} الموافق {today_str.replace('-', '/')}<br><br>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                        📟 <b>بداية وقت الاجتماع</b><br>
                        <div style="direction: ltr; text-align: right;">{dyn_time_html}</div>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 15px 0;">
                        <b>لحضور الاجتماع، عليك أن تقوم بالخطوتين التاليتين:</b><br><br>
                        🔗 <b>أولًا: التسجيل لأول مرة فقط:</b><br>
                        <a href="{form_link}">{form_link}</a><br><br>
                        🔗 <b>ثانياً: لتسجيل الحضور والحصول على الرابط:</b><br>
                        <a href="{PORTAL_LINK}">بوابة تسجيل الحضور</a><br><br>
                        نحن بالفعل نتعافى!</div>"""

                # Create Drafts in batches of 45
                batch_size = 45
                for i in range(0, len(valid_emails), batch_size):
                    create_draft(f"دعوة زمالة الخليج - {today_str}", body_html, valid_emails[i:i+batch_size], invite_method, is_html=True, static_to="sagulf.recovery@gmail.com")

                # Admin Report for this specific meeting
                admin_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6;">
                    <h3>✅ تم تجهيز مسودات دعوات اجتماع ({meeting_name_master}) بنجاح!</h3>
                    <h4 style="color: #2e7d32;">📩 المستلمون للدعوة ({len(valid_emails)}):</h4><ul>{html_list(valid_emails)}</ul>
                    <h4 style="color: #f57c00;">⚠ أعضاء تحت الإنذار ({len(warned_emails)}):</h4><ul>{html_list(warned_emails)}</ul>
                    <h4 style="color: #c62828;">⛔ أعضاء تجاوزوا حد الغياب ومُعلقين ({len(suspended_emails)}):</h4><ul>{html_list(suspended_emails)}</ul></div>"""
                send_email(f"📊 تقرير دعوات: {meeting_name_master} - {today_str}", admin_body, ADMIN_EMAILS)

    # ==========================================
    # 2. ABSENCE TRACKING (YESTERDAY)
    # ==========================================
    yesterday_meetings = meetings_data[meetings_data['Meeting Day'] == yesterday_name]
    
    if not yesterday_meetings.empty:
        action_taken = True
        print(f"📅 Today: Tracking absences for yesterday ({yesterday_name}).")
        
        # Loop through all meetings from yesterday
        for _, meeting_info in yesterday_meetings.iterrows():
            meeting_name_master = str(meeting_info.get('Meeting Name', 'اجتماع غير محدد'))
            target_id = str(meeting_info['Target Sheet ID']).strip()
            max_abs = int(meeting_info['Max Absences'])
            
            try:
                target_db = client.open_by_key(target_id)
            except Exception: continue
            
            # Strict Registration Check
            try:
                reg_tab = target_db.worksheet("Registration")
                reg_df = pd.DataFrame(reg_tab.get_all_records())
            except gspread.exceptions.WorksheetNotFound:
                send_halt_alert(meeting_name_master, target_id, "شيت التسجيل مفقود أثناء فحص الغيابات.", "مطابقة الاسم مع Registration")
                continue
                
            # Strict Attendance Check for Fail-Fast
            yesterday_attendees = set()
            try:
                check_in_tab = target_db.worksheet("Attendance")
            except gspread.exceptions.WorksheetNotFound:
                try:
                    check_in_tab = target_db.worksheet("Check-In Log")
                except gspread.exceptions.WorksheetNotFound:
                    send_halt_alert(meeting_name_master, target_id, "شيت سجل الحضور (Attendance) مفقود.", "إنشاء الشيت أو تسميته بـ Attendance حرفياً لمنع مسح بيانات الأعضاء.")
                    continue # HALT absence processing!
            
            # If safe, process attendance
            check_in_df = pd.DataFrame(check_in_tab.get_all_records())
            if not check_in_df.empty and 'Timestamp' in check_in_df.columns:
                raw_attendees = check_in_df[check_in_df['Timestamp'].astype(str).str.contains(yesterday_date_str, na=False)]['Email']
                yesterday_attendees = set(raw_attendees.str.lower().str.strip().tolist())

            abs_col_name = 'Absences' if 'Absences' in reg_df.columns else 'الغيابات'
            abs_col_idx = reg_df.columns.get_loc(abs_col_name) + 1

            absent_yesterday, suspended_emails = [], []
            num_rows = len(reg_df)
            
            if num_rows > 0:
                cells_to_update = reg_tab.range(2, abs_col_idx, num_rows + 1, abs_col_idx)
                for index, row in reg_df.iterrows():
                    email_addr = str(row.iloc[1]).strip().lower()
                    if not email_addr: continue
                    
                    current_absences = get_safe_absences(row)
                    new_absences = current_absences
                    
                    if email_addr not in yesterday_attendees:
                        new_absences = current_absences + 1
                        if new_absences < max_abs: absent_yesterday.append(email_addr)
                    elif current_absences > 0:
                        new_absences = 0
                        
                    cells_to_update[index].value = new_absences
                    if new_absences >= max_abs: suspended_emails.append(email_addr)

                reg_tab.update_cells(cells_to_update)

            # Send warnings
            if absent_yesterday:
                notice_subject = "نفتقدك في زمالة الخليج"
                notice_body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماعنا أمس ({yesterday_name})، ونتمنى أن تكون بخير.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك في الاجتماع القادم.\n\nنحن بالفعل نتعافى!"
                for i in range(0, len(absent_yesterday), 45):
                    create_draft(notice_subject, notice_body, absent_yesterday[i:i+45], "BCC", is_html=False)

            # Admin Report for this specific meeting tracking
            admin_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6;">
                <h3>✅ تم فحص الحضور لاجتماع ({meeting_name_master}) وتحديث الشيت!</h3>
                <h4 style="color: #1565c0;">⚠️ أعضاء غابوا أمس وتم تجهيز رسائل لهم ({len(absent_yesterday)}):</h4><ul>{html_list(absent_yesterday)}</ul>
                <h4 style="color: #c62828;">⛔ أعضاء تجاوزوا الحد وأصبحوا مُعلقين ({len(suspended_emails)}):</h4><ul>{html_list(suspended_emails)}</ul></div>"""
            send_email(f"📊 تقرير غيابات: {meeting_name_master} - {yesterday_name}", admin_body, ADMIN_EMAILS)

    # ==========================================
    # 3. HEARTBEAT (IDLE DAYS)
    # ==========================================
    if not action_taken:
        print(f"💤 Idle Day ({today_name}). Sending Heartbeat...")
        heartbeat_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6;">
            <h3>🤖 الروبوت يعمل بنجاح!</h3>
            <p>مرحباً،</p>
            <p>الروبوت مستيقظ ويعمل بشكل طبيعي اليوم <b>{today_name} ({today_str})</b>.</p>
            <p>لا توجد مهام دعوات أو متابعة غيابات مجدولة لهذا اليوم. جميع الأنظمة مستقرة.</p>
            <hr><small style="color: gray;">هذه رسالة تلقائية للتأكد من عمل الأتمتة.</small>
        </div>"""
        send_email(f"🤖 نبضة الروبوت: النظام مستقر ({today_name})", heartbeat_body, ADMIN_EMAILS)

if __name__ == "__main__":
    run_robot()
