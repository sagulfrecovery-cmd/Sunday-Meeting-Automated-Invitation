import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, time as dt_time
import pytz
import requests

# --- مكتبات إضافية لآلية إعادة المحاولة ---
from google.auth.transport.requests import AuthorizedSession
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ==========================================
# ⏰ إعدادات أوقات البوابة (يمكنك التعديل هنا)
# ==========================================

# أوقات يوم الأحد
SUN_OPEN_HOUR, SUN_OPEN_MIN = 20, 45    # 8:45 PM
SUN_CLOSE_HOUR, SUN_CLOSE_MIN = 21, 20  # 9:20 PM

# أوقات يوم الأربعاء
WED_OPEN_HOUR, WED_OPEN_MIN = 0, 01    # 8:15 PM
WED_CLOSE_HOUR, WED_CLOSE_MIN = 20, 50  # 10:50 PM

# مدة إغلاق الغرفة بعد بدء الاجتماع (بالدقائق)
ROOM_LOCK_MINUTES = 20

# ==========================================
# 🔧 Helper Functions & Caching
# ==========================================

def format_time_arabic(hour, minute):
    period = "مساءً" if hour >= 12 else "صباحاً"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{minute:02d} {period}"

@st.cache_resource
def get_google_client():
    # التعامل الآمن مع الأسرار سواء كانت نصية أو كائن مفسر مسبقاً
    secret_data = st.secrets["gcp_service_account"]
    if isinstance(secret_data, str):
        creds_dict = json.loads(secret_data)
    else:
        # تحويل AttrDict أو الـ dict إلى dict عادي لتجنب مشاكل التعديل
        creds_dict = dict(secret_data)
        
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    
    # آلية إعادة المحاولة عند حدوث خطأ 429 (Quota Exceeded)
    session = AuthorizedSession(creds)
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    return gspread.Client(auth=creds, session=session)

@st.cache_data(ttl=3600)
def get_meetings_data():
    client = get_google_client()
    master_sheet = client.open_by_key(MASTER_SHEET_ID).sheet1
    return pd.DataFrame(master_sheet.get_all_records())

@st.cache_data(ttl=900)
def get_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = client.open_by_key(target_sheet_id)
    reg_tab = target_db.worksheet("Registration")
    reg_df = pd.DataFrame(reg_tab.get_all_records())
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

# ==========================================
# 🖥️ UI SETUP
# ==========================================
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖")

# ==========================================
# ⏰ نظام قفل البوابة حسب الوقت (توقيت بغداد)
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
weekday = now.weekday()  # 6 = الأحد، 2 = الأربعاء
now_time = now.time()

is_testing = st.secrets.get("test_mode", False)
is_open = False

if is_testing:
    is_open = True
else:
    sun_open_time = dt_time(SUN_OPEN_HOUR, SUN_OPEN_MIN)
    sun_close_time = dt_time(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
    wed_open_time = dt_time(WED_OPEN_HOUR, WED_OPEN_MIN)
    wed_close_time = dt_time(WED_CLOSE_HOUR, WED_CLOSE_MIN)

    if weekday == 6: 
        if sun_open_time <= now_time <= sun_close_time:
            is_open = True
    elif weekday == 2: 
        if wed_open_time <= now_time <= wed_close_time:
            is_open = True

if not is_open:
    sun_open_str = format_time_arabic(SUN_OPEN_HOUR, SUN_OPEN_MIN)
    sun_close_str = format_time_arabic(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
    wed_open_str = format_time_arabic(WED_OPEN_HOUR, WED_OPEN_MIN)
    wed_close_str = format_time_arabic(WED_CLOSE_HOUR, WED_CLOSE_MIN)

    st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
    st.warning("⛔ عذراً، تسجيل الحضور مغلق حالياً. التسجيل يفتح قبل 15 دقيقة من بدء الاجتماع")
    st.info(
        f"يُفتح التسجيل فقط في أيام الاجتماعات:\n\n"
        f"- **الأحد:** من الساعة {sun_open_str} حتى {sun_close_str}\n"
        f"- **الأربعاء:** من الساعة {wed_open_str} حتى {wed_close_str}\n"
        f"*(بتوقيت بغداد)*"
    )
    st.stop()

# ==========================================
# ✅ واجهة التطبيق الرئيسية
# ==========================================
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
if is_testing:
    st.warning("🛠️ **تنبيه:** البوابة تعمل حالياً في وضع الاختبار (Test Mode).")
st.markdown("---")

st.markdown(f"""
<div style="background-color: #ffe6e6; padding: 15px; border-radius: 8px; border: 2px solid red; text-align: center; margin-bottom: 25px;">
    <h3 style="color: #c62828; margin: 0; font-weight: bold; line-height: 1.4;">
        ⚠ يرجى العلم أن الغرفة ستغلق بعد {ROOM_LOCK_MINUTES} دقيقة من بداية الاجتماع ولن يتم قبول أي شخص بعد هذا الوقت.
    </h3>
</div>
""", unsafe_allow_html=True)

# --- MAIN LOGIC ---
try:
    meetings_data = get_meetings_data()
    available_meetings = [str(x).strip() for x in meetings_data['Meeting Day'].tolist()]
except Exception as e:
    st.error(f"System Error: {e}")
    st.stop()

# التحديد التلقائي لليوم
if weekday == 6 or (is_testing and weekday not in [6, 2]):
    selected_meeting = "الأحد"
elif weekday == 2:
    selected_meeting = "الأربعاء"
else:
    selected_meeting = "الأحد"

if selected_meeting not in available_meetings:
    st.error(f"⚠️ عذراً، لم يتم العثور على إعدادات اجتماع يوم **{selected_meeting}** في قاعدة البيانات.")
    st.stop()

st.info(f"📌 اجتماع اليوم: **{selected_meeting}**")
st.markdown("<br>", unsafe_allow_html=True)
user_email = st.text_input("البريد الإلكتروني المسجل (Registered Email):").strip().lower()

# --- عهد التعافي ---
st.markdown("---")
st.markdown("### 🤝 عهد التعافي")
pledge = st.checkbox("أتعهد بصدق وأمانة أمام نفسي وتجاه زمالتي، أنني أسجل الآن بنية الحضور الفعلي للاجتماع في وقته المحدد.")

# ==========================================
# 🎯 عملية تسجيل الحضور
# ==========================================
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
                    
                    registered_emails = get_registered_emails(target_id)

                    if user_email in registered_emails:
                        # تجهيز البيانات للإرسال
                        baghdad_time = datetime.now(pytz.timezone("Asia/Baghdad")).strftime("%Y-%m-%d %H:%M:%S")
                        script_url = "https://script.google.com/macros/s/AKfycby4pH_ELy-H57Zan-xF34GCdbXVXRI8xEIRctbsM5EsZ5EFPPgbgY6Oxk1ZKZwV6JhbbQ/exec"

                        payload = {
                            "target_id": target_id,
                            "timestamp": baghdad_time,
                            "email": user_email
                        }

                        # إرسال البيانات لسكربت جوجل بدلاً من الكتابة المباشرة
                        response = requests.post(script_url, data=payload)

                        if response.text == "Success":
                            # حفظ البيانات في session_state لعرضها بعد إعادة التحميل
                            st.session_state['check_in_success'] = True
                            st.session_state['zoom_link'] = zoom_link
                            st.session_state['checked_in_email'] = user_email
                            st.session_state['selected_meeting'] = selected_meeting
                            
                            st.rerun()
                        else:
                            st.error(f"حدث خطأ أثناء حفظ البيانات: {response.text}")
                            
                    else:
                        st.error(f"❌ عذراً، بريدك الإلكتروني غير مسجل في قائمة {selected_meeting}. يرجى التأكد من البريد أو تقديم طلب انضمام.")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء تسجيل الحضور: {e}")
else:
    st.info("💡 يرجى وضع علامة (صح) على التعهد أعلاه لتفعيل زر الدخول.")

# ==========================================
# ✅ عرض النتيجة بعد التسجيل الناجح
# ==========================================
if st.session_state.get('check_in_success', False):
    st.markdown("---")
    st.success("✅ تم تسجيل حضورك بنجاح! شكراً لأمانتك.")
    
    zoom_link = st.session_state['zoom_link']
    checked_in_email = st.session_state['checked_in_email']
    meeting_day = st.session_state['selected_meeting']
    
    st.markdown("### 🔗 رابط زووم المباشر")
    st.markdown("**اضغط على أيقونة النسخ في الزاوية العلوية للصندوق لنسخ الرابط:**")
    st.code(zoom_link, language=None)
    
    st.caption(f"تم التسجيل بالبريد: {checked_in_email} | الاجتماع: {meeting_day}")
