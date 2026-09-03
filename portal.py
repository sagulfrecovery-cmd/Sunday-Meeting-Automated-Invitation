import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# --- HELPER FUNCTIONS ---
@st.cache_resource
def get_google_client():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def send_zoom_email(recipient_email, meeting_day, zoom_link):
    sender = st.secrets["sender_email"]
    password = st.secrets["app_password"]
    
    body = f"مرحباً،\n\nشكراً لتسجيل حضورك في اجتماع يوم {meeting_day}.\nرابط الدخول المباشر إلى غرفة زووم:\n{zoom_link}\n\nنحن بالفعل نتعافى!"
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f"رابط الدخول لاجتماع زمالة الخليج - {meeting_day}"
    msg['From'] = sender
    msg['To'] = recipient_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
    except Exception:
        pass 

# --- UI SETUP ---
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖")
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- MAIN LOGIC ---
try:
    client = get_google_client()
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    available_meetings = meetings_data['Meeting Day'].tolist()
except Exception as e:
    st.error("جاري تحديث النظام، يرجى المحاولة لاحقاً.")
    st.stop()

# Build the Input Form
selected_meeting = st.selectbox("اختر يوم الاجتماع (Select Meeting Day):", available_meetings)
user_email = st.text_input("البريد الإلكتروني المسجل (Registered Email):").strip().lower()

if st.button("تسجيل الحضور وعرض الرابط (Check-In)"):
    if not user_email:
        st.warning("يرجى إدخال البريد الإلكتروني.")
    else:
        with st.spinner("جاري التحقق من السجلات..."):
            try:
                meeting_info = meetings_data[meetings_data['Meeting Day'] == selected_meeting].iloc[0]
                target_id = str(meeting_info['Target Sheet ID']).strip()
                zoom_link = str(meeting_info['Zoom Link']).strip()
                
                target_db = client.open_by_key(target_id)
                reg_tab = target_db.worksheet("Registration")
                reg_df = pd.DataFrame(reg_tab.get_all_records())
                
                registered_emails = reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

                if user_email in registered_emails:
                    try:
                        check_in_tab = target_db.worksheet("Check-In Log")
                    except gspread.exceptions.WorksheetNotFound:
                        check_in_tab = target_db.add_worksheet(title="Check-In Log", rows="1000", cols="2")
                        check_in_tab.append_row(["Timestamp", "Email"])
                    
                    baghdad_time = datetime.now(pytz.timezone("Asia/Baghdad")).strftime("%Y-%m-%d %H:%M:%S")
                    check_in_tab.append_row([baghdad_time, user_email])
                    
                    send_zoom_email(user_email, selected_meeting, zoom_link)
                    
                    st.success("✅ تم تسجيل الحضور بنجاح! تم إرسال الرابط إلى بريدك الإلكتروني.")
                    st.info(f"🔗 **رابط زووم المباشر:**\n\n{zoom_link}")
                else:
                    st.error("❌ عذراً، هذا البريد غير مسجل في قائمة هذا الاجتماع. يرجى التأكد من البريد أو تقديم طلب انضمام.")
            except Exception as e:
                st.error("حدث خطأ أثناء جلب البيانات. تأكد من إعدادات ملف Google Sheet.")
