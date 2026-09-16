import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, time as dt_time
import pytz

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ==========================================
# ⏰ إعدادات أوقات البوابة (يمكنك التعديل هنا)
# النظام يستخدم 24 ساعة (مثلاً 18 تعني 6 مساءً)
# ==========================================

# أوقات يوم الأحد
SUN_OPEN_HOUR, SUN_OPEN_MIN = 18, 0    # 6:00 PM
SUN_CLOSE_HOUR, SUN_CLOSE_MIN = 21, 30 # 9:30 PM

# أوقات يوم الأربعاء
WED_OPEN_HOUR, WED_OPEN_MIN = 18, 0    # 6:00 PM
WED_CLOSE_HOUR, WED_CLOSE_MIN = 22, 0  # 9:00 PM

# مدة إغلاق الغرفة بعد بدء الاجتماع (بالدقائق - تستخدم في رسالة التنبيه)
ROOM_LOCK_MINUTES = 20

# ==========================================

# --- HELPER FUNCTIONS ---
def format_time_arabic(hour, minute):
    """دالة لتحويل الوقت من 24 ساعة إلى 12 ساعة مع صباحاً/مساءً بشكل آلي"""
    period = "مساءً" if hour >= 12 else "صباحاً"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{minute:02d} {period}"

@st.cache_resource
def get_google_client():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    # This magic line forces the security key into the perfect format, preventing MalformedFraming:
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
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

# --- UI SETUP (Page config must be first Streamlit call) ---
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖")

# ==========================================
# ⏰ نظام قفل البوابة حسب الوقت (توقيت بغداد)
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
weekday = now.weekday()  # 6 = الأحد، 2 = الأربعاء
now_time = now.time()

# توليد النصوص آلياً بناءً على الإعدادات أعلاه
sun_open_str = format_time_arabic(SUN_OPEN_HOUR, SUN_OPEN_MIN)
sun_close_str = format_time_arabic(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
wed_open_str = format_time_arabic(WED_OPEN_HOUR, WED_OPEN_MIN)
wed_close_str = format_time_arabic(WED_CLOSE_HOUR, WED_CLOSE_MIN)

is_open = False

# تحويل إعدادات الوقت إلى كائنات datetime.time للمقارنة
sun_open_time = dt_time(SUN_OPEN_HOUR, SUN_OPEN_MIN)
sun_close_time = dt_time(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
wed_open_time = dt_time(WED_OPEN_HOUR, WED_OPEN_MIN)
wed_close_time = dt_time(WED_CLOSE_HOUR, WED_CLOSE_MIN)

if weekday == 6: # الأحد
    if sun_open_time <= now_time <= sun_close_time:
        is_open = True
elif weekday == 2: # الأربعاء
    if wed_open_time <= now_time <= wed_close_time:
        is_open = True

if not is_open:
    st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
    st.warning("⛔ عذراً، تسجيل الحضور مغلق حالياً.")
    # عرض الأوقات ديناميكياً
    st.info(
        f"يُفتح التسجيل فقط في أيام الاجتماعات:\n\n"
        f"- **الأحد:** من الساعة {sun_open_str} حتى {sun_close_str}\n"
        f"- **الأربعاء:** من الساعة {wed_open_str} حتى {wed_close_str}\n"
        f"*(بتوقيت بغداد)*"
    )
    st.stop()  # إيقاف التنفيذ هنا

# ==========================================
# ✅ واجهة التطبيق الرئيسية (تظهر فقط وقت السماح)
# ==========================================
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
st.markdown("---")

# رسالة التنبيه باللون الأحمر، والتي تتأثر برقم الدقائق المحدد في الكود
st.markdown(f"""
<div style="background-color: #ffe6e6; padding: 15px; border-radius: 8px; border: 2px solid red; text-align: center; margin-bottom: 25px;">
    <h3 style="color: #c62828; margin: 0; font-weight: bold; line-height: 1.4;">
        ⚠️ يرجى العلم أن الغرفة ستغلق بعد {ROOM_LOCK_MINUTES} دقيقة من بداية الاجتماع ولن يتم قبول أي شخص بعد هذا الوقت.
    </h3>
</div>
""", unsafe_allow_html=True)

# --- MAIN LOGIC ---
try:
    client = get_google_client()
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    meetings_data = pd.DataFrame(master_sheet.get_all_records())
    available_meetings = meetings_data['Meeting Day'].tolist()
except Exception as e:
    st.error(f"System Error: {e}")
    st.stop()

# Build the Input Form
selected_meeting = st.radio("اختر يوم الاجتماع (Select Meeting Day):", available_meetings, horizontal=True)
user_email = st.text_input("البريد الإلكتروني المسجل (Registered Email):").strip().lower()

# --- عهد التعافي (Recovery Pledge) ---
st.markdown("---")
st.markdown("### 🤝 عهد التعافي")
pledge = st.checkbox("أتعهد بصدق وأمانة أمام نفسي وتجاه زمالتي، أنني أسجل الآن بنية الحضور الفعلي للاجتماع في وقته المحدد.")

# لن يتم تفعيل الزر إلا إذا قام العضو بتأكيد التعهد
if pledge:
    if st.button("تسجيل الحضور وعرض الرابط (Check-In)", use_container_width=True):
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
                        
                        st.success("✅ تم تسجيل حضورك بنجاح! شكراً لأمانتك، تم إرسال الرابط إلى بريدك الإلكتروني.")
                        st.info(f"🔗 **رابط زووم المباشر:**\n\n{zoom_link}")
                    else:
                        st.error("❌ عذراً، هذا البريد غير مسجل في قائمة هذا الاجتماع. يرجى التأكد من البريد أو تقديم طلب انضمام.")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء جلب البيانات: {e}")
else:
    st.info("💡 يرجى وضع علامة (صح) على التعهد أعلاه لتفعيل زر الدخول.")
