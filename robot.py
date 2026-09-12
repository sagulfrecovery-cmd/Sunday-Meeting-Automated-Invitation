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
yesterday_date_str = (baghdad_now - timedelta(days=1)).strftime("%Y-%m-%d")

days_ar = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
today_name = days_ar[baghdad_now.weekday()]
yesterday_name = days_ar[(baghdad_now.weekday() - 1) % 7]

print(f"🤖 استيقظ الروبوت... اليوم: {today_name} ({today_str}) | الأمس: {yesterday_name} ({yesterday_date_str})")

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

# --- MAINTENANCE LOGIC ---
def run_maintenance(meetings_data):
    print("🛠️ بدء عملية الصيانة الدورية...")
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
        if bounced_emails: print(f"⚠️ تم رصد {len(bounced_emails)} إيميل مرتد. سيتم حذفها.")
    except Exception as e:
        pass

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
                
                ci_rows_to_delete = []
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
                    except: pass
            
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
                time.sleep(5 * (attempt + 1))
            else:
                raise e
                
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    run_maintenance(meetings_data)
    
    html_list = lambda lst: "".join([f"<li>{e}</li>" for e in sorted(lst)]) if lst else "<li>لا يوجد</li>"
    admin_emails = "ameermam.sa@gmail.com, keepcomingback.29@gmail.com, sagulf.recovery@gmail.com"

    # ==========================================
    # 1. أيام الدعوات (الأحد والأربعاء)
    # ==========================================
    today_meeting = meetings_data[meetings_data['Meeting Day'] == today_name]
    if not today_meeting.empty:
        print(f"📅 اليوم ({today_name}): يوم مخصص لإرسال دعوات الاجتماع.")
        
        print("🌐 جاري إرسال نبضة قوية لإيقاظ البوابة...")
        for attempt in range(3):
            try:
                # إضافة طابع زمني للرابط لتجاوز الذاكرة المخبأة (Cache-Busting)
                no_cache_url = f"{PORTAL_LINK.rstrip('/')}/?wake={int(time.time())}"
                
                # استخدام User-Agent يحاكي متصفح حقيقي
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                
                req = urllib.request.Request(no_cache_url, headers=headers)
                urllib.request.urlopen(req, timeout=15)
                
                print("✅ تم إيقاظ البوابة بنجاح (متجاوزاً الكاش)!")
                break
            except urllib.error.HTTPError as e:
                print(f"✅ البوابة مستيقظة (رمز الاستجابة: {e.code})!")
                break
            except Exception as e:
                if attempt < 2: time.sleep(5)
                else:
                    send_admin_report("🚨 تنبيه عاجل: فشل إيقاظ البوابة", f'<div dir="rtl">تعذر الوصول للبوابة. الخطأ: {e}</div>', admin_emails)
        
        meeting_info = today_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        invite_method = str(meeting_info['Invite Method']).strip()
        form_link = str(meeting_info.get('Form Link', PORTAL_LINK)).strip() or PORTAL_LINK
        
        target_db = client.open_by_key(target_id)
        reg_df = pd.DataFrame(target_db.worksheet("Registration").get_all_records())
        
        valid_emails = []
        warned_emails = []
        removed_emails = []
        
        # قراءة البيانات فقط بدون تعديل غيابات
        for _, row in reg_df.iterrows():
            email = str(row.iloc[1]).strip().lower()
            if not email: continue
            absences = get_safe_absences(row)
            if absences >= max_abs: removed_emails.append(email)
            else:
                valid_emails.append(email)
                if absences > 0: warned_emails.append(email)

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
                    🔗 <b>رابط تسجيل الدخول للاجتماع (البوابة):</b><br>
                    <a href="{PORTAL_LINK}">{PORTAL_LINK}</a><br><br>
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

                body_html = f"""<div dir="rtl" style="text-align: right; font-family: Arial; font-size: 16px; line-height: 1.8;">
                  ༺ يرجى قراءة الإعلان جيدًا ༻<br><br>
                  تدعوكم ༺ زمالة الخليج ༻ إلى اجتماع اليوم: <b>{meeting_topic}</b><br>
                  {today_name} الموافق {today_str.replace('-', '/')}<br><br>

                  📝 <b>خطوات حضور اجتماع "زمالة الخليج" ليوم الاربعاء:</b><br><br>

                  <b>الخطوة الأولى: التسجيل في الزمالة (تُنفذ لمرة واحدة فقط)</b><br>
                  إذا كنت عضواً جديداً ولم يسبق لك الانضمام، يجب عليك أولاً ملء استمارة التسجيل الأساسية.<br>
                  • (هذه الخطوة تُفعل لمرة واحدة فقط في بداية انضمامك للمجموعة لإنشاء ملفك).<br>
                  🔗 <a href="{form_link}">{form_link}</a><br><br>

                  <b>الخطوة الثانية: إثبات الحضور واستلام الرابط (تُنفذ في كل اجتماع)</b><br>
                  في يوم الاجتماع (الأربعاء)، وكي تتمكن من الدخول للقاعة، يرجى اتباع الآتي:<br>
                  • الدخول إلى بوابة تسجيل الحضور الإلكترونية.<br>
                  • إدخال بريدك الإلكتروني (الإيميل) الذي سجلت به مسبقاً.<br>
                  • بمجرد ضغطك على زر تسجيل الحضور، سيظهر لك فوراً رابط قاعة الاجتماع لتدخل مباشرة.<br>
                  🔗 <a href="{PORTAL_LINK}">بوابة تسجيل الحضور</a><br><br>

                  🚨 <b>تنبيهات إدارية وتقنية هامة</b><br>
                  • ⏱️ <b>إغلاق القاعة:</b> يُغلق باب الدخول للاجتماع تماماً بعد مرور 20 دقيقة من وقت البدء الرسمي. يرجى الحرص على الدخول مبكراً.<br>
                  • ⏳ <b>مدة الاجتماع:</b> يستمر الاجتماع لمدة 70 دقيقة.<br>
                  • 🔄 <b>حلول تقنية:</b> إذا قمت بفتح "بوابة تسجيل الحضور" وواجهت أي بطء أو لم يفتح الموقع، كل ما عليك فعله هو إغلاق الصفحة وإعادة فتحها، أو عمل تحديث (Refresh) للصفحة.<br>
                  • 📊 <b>احتساب الحضور:</b> النظام الآلي يعتمد كلياً على تسجيلك في "البوابة" (الخطوة الثانية) لإثبات حضورك. بمجرد تسجيلك، سيقوم النظام تلقائياً بمسح أي غيابات سابقة لك.<br>
                  • 🛡 <b>سياسة الغياب:</b> نحن نتفهم ظروف الجميع، ولكن للحفاظ على فعالية ومساحة المجموعة، يقوم النظام آلياً بإلغاء تسجيل أي عضو يتجاوز الحد الأقصى المسموح به من الغيابات المتتالية لترك المجال لمن هم بحاجة حقيقية للتواجد.<br><br>

                  نحن بالفعل نتعافى!</div>"""
                batch_size = 45
                for i in range(0, len(valid_emails), batch_size):
                    create_draft(f"دعوة زمالة الخليج - {today_str}", body_html, valid_emails[i:i+batch_size], invite_method, is_html=True)

        admin_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6;">
            <h3>✅ تم تجهيز مسودات الدعوات بنجاح لاجتماع اليوم ({today_name})!</h3>
            <h4 style="color: #2e7d32;">📩 المستلمون للدعوة ({len(valid_emails)}):</h4><ul>{html_list(valid_emails)}</ul>
            <h4 style="color: #f57c00;">⚠️ أعضاء تحت الإنذار ({len(warned_emails)}):</h4><ul>{html_list(warned_emails)}</ul>
            <h4 style="color: #c62828;">🚫 أعضاء متجاوزين الحد ({len(removed_emails)}):</h4><ul>{html_list(removed_emails)}</ul></div>"""
        send_admin_report(f"📊 تقرير دعوات زمالة الخليج - {today_str}", admin_body, admin_emails)

    # ==========================================
    # 2. أيام المتابعة والغيابات (الاثنين والخميس)
    # ==========================================
    yesterday_meeting = meetings_data[meetings_data['Meeting Day'] == yesterday_name]
    if not yesterday_meeting.empty:
        print(f"📅 اليوم مخصص لمتابعة غيابات اجتماع الأمس ({yesterday_name}).")
        meeting_info = yesterday_meeting.iloc[0]
        target_id = str(meeting_info['Target Sheet ID']).strip()
        max_abs = int(meeting_info['Max Absences'])
        
        target_db = client.open_by_key(target_id)
        reg_tab = target_db.worksheet("Registration")
        reg_df = pd.DataFrame(reg_tab.get_all_records())
        
        try:
            check_in_tab = target_db.worksheet("Check-In Log")
            check_in_df = pd.DataFrame(check_in_tab.get_all_records())
            # تصفية الإيميلات المكررة لحضور البارحة
            raw_attendees = check_in_df[check_in_df['Timestamp'].astype(str).str.contains(yesterday_date_str, na=False)]['Email']
            yesterday_attendees = set(raw_attendees.str.lower().str.strip().tolist())
        except:
            yesterday_attendees = set()

        abs_col_name = 'Absences' if 'Absences' in reg_df.columns else 'الغيابات'
        abs_col_idx = reg_df.columns.get_loc(abs_col_name) + 1

        absent_yesterday = []
        removed_emails = []
        
        print("🔄 جاري تحليل وتحديث الغيابات (بالنظام السريع)...")
        num_rows = len(reg_df)
        if num_rows > 0:
            cells_to_update = reg_tab.range(2, abs_col_idx, num_rows + 1, abs_col_idx)
            
            for index, row in reg_df.iterrows():
                email = str(row.iloc[1]).strip().lower()
                if not email: continue
                
                current_absences = get_safe_absences(row)
                new_absences = current_absences
                
                if email not in yesterday_attendees:
                    new_absences = current_absences + 1
                    if new_absences < max_abs: absent_yesterday.append(email)
                elif current_absences > 0:
                    new_absences = 0
                
                cells_to_update[index].value = new_absences
                if new_absences >= max_abs: removed_emails.append(email)

            reg_tab.update_cells(cells_to_update)
            print("✅ تم تحديث الغيابات في الإكسل بنجاح!")

        if absent_yesterday:
            print(f"⚠️ تجهيز التنبيه لـ {len(absent_yesterday)} شخص غابوا أمس...")
            notice_subject = "نفتقدك في زمالة الخليج"
            notice_body = f"مرحباً،\n\nلاحظنا عدم حضورك لاجتماعنا أمس ({yesterday_name})، ونتمنى أن تكون بخير.\nنفتقد تواجدك معنا، ونتطلع لرؤيتك في الاجتماع القادم.\n\nنحن بالفعل نتعافى!"
            batch_size = 45
            for i in range(0, len(absent_yesterday), batch_size):
                create_draft(notice_subject, notice_body, absent_yesterday[i:i+batch_size], "BCC", is_html=False)

        admin_body = f"""<div dir="rtl" style="font-family: Arial; font-size: 15px; line-height: 1.6;">
            <h3>✅ تم فحص الحضور وتحديث ملف الإكسل لاجتماع الأمس ({yesterday_name})!</h3>
            <h4 style="color: #1565c0;">⚠️ تم تجهيز إيميلات تنبيه لمن غاب أمس ({len(absent_yesterday)}):</h4><ul>{html_list(absent_yesterday)}</ul>
            <h4 style="color: #c62828;">🚫 أعضاء متجاوزين الحد وتم شطبهم ({len(removed_emails)}):</h4><ul>{html_list(removed_emails)}</ul></div>"""
        send_admin_report(f"📊 تقرير المتابعة وتحديث الغيابات - {yesterday_name}", admin_body, admin_emails)

if __name__ == "__main__":
    run_robot()
