import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time as dt_time
import pytz
import time

# --- CONFIGURATION ---
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ==========================================
# ⏰ إعدادات أوقات البوابة
# ==========================================
SUN_OPEN_HOUR, SUN_OPEN_MIN = 20, 45    # 8:45 PM
SUN_CLOSE_HOUR, SUN_CLOSE_MIN = 21, 20  # 9:20 PM

WED_OPEN_HOUR, WED_OPEN_MIN = 20, 15    # 8:15 PM
WED_CLOSE_HOUR, WED_CLOSE_MIN = 20, 50  # 8:50 PM

ROOM_LOCK_MINUTES = 20

# ==========================================
# 🔧 Helper Functions & Caching
# ==========================================

def format_time_arabic(hour, minute):
    period = "مساءً" if hour >= 12 else "صباحاً"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{minute:02d} {period}"

# دالة إعادة المحاولة عند حدوث ضغط لحظي (لمنع خطأ 429)
def safe_execute(action_fn, max_retries=3, delay=1.5):
    for attempt in range(max_retries):
        try:
            return action_fn()
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
                continue
            raise e

@st.cache_resource
def get_google_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "\\n" in creds_dict.get("private_key", ""):
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.Client(auth=creds)

@st.cache_data(ttl=3600)
def get_meetings_data():
    client = get_google_client()
    master_sheet = safe_execute(lambda: client.open_by_key(MASTER_SHEET_ID).sheet1)
    return pd.DataFrame(safe_execute(lambda: master_sheet.get_all_records()))

@st.cache_data(ttl=900)
def get_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
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
    st.error(f"خطأ أثناء جلب البيانات: {e}")
    st.stop()

# 🎯 تحديد يوم الاجتماع (تفاعلي في وضع الاختبار، وتلقائي في الوضع الفعلي)
if is_testing:
    selected_meeting = st.radio(
        "🛠️ اختر الاجتماع الذي تريد اختباره الآن:",
        options=["الأحد", "الأربعاء"],
        horizontal=True
    )
    if st.session_state.get('last_tested_meeting') != selected_meeting:
        st.session_state['last_tested_meeting'] = selected_meeting
        st.session_state['check_in_success'] = False
else:
    if weekday == 6:
        selected_meeting = "الأحد"
    elif weekday == 2:
        selected_meeting = "الأربعاء"
    else:
        selected_meeting = "الأحد"

if selected_meeting not in available_meetings:
    st.error(f"⚠️ عذراً، لم يتم العثور على إعدادات اجتماع يوم **{selected_meeting}** في قاعدة البيانات.")
    st.stop()

st.info(f"📌 الاجتماع المحدد: **{selected_meeting}**")
st.markdown("<br>", unsafe_allow_html=True)
user_email = st.text_input("البريد الإلكتروني المسجل (Registered Email) - حجم الحروف يؤثر على التسجيل حيث يجب مطابقة الحروف الكبيرة والصغيرة التي استخدمتها في التسجيل:").strip().lower()

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
            with st.spinner("جاري التحقق من السجلات وتسجيل الحضور..."):
                try:
                    meeting_info = meetings_data[meetings_data['Meeting Day'] == selected_meeting].iloc[0]
                    target_id = str(meeting_info['Target Sheet ID']).strip()
                    zoom_link = str(meeting_info['Zoom Link']).strip()

                    registered_emails = get_registered_emails(target_id)

                    if user_email in registered_emails:
                        baghdad_time = datetime.now(pytz.timezone("Asia/Baghdad")).strftime("%Y-%m-%d %H:%M:%S")

                        # التسجيل المباشر في Google Sheets
                        client = get_google_client()
                        target_db = safe_execute(lambda: client.open_by_key(target_id))

                        try:
                            attendance_tab = safe_execute(lambda: target_db.worksheet("Attendance"))
                        except Exception:
                            attendance_tab = safe_execute(lambda: target_db.sheet1)

                        safe_execute(lambda: attendance_tab.append_row([baghdad_time, user_email]))

                        st.session_state['check_in_success'] = True
                        st.session_state['zoom_link'] = zoom_link
                        st.session_state['checked_in_email'] = user_email
                        st.session_state['selected_meeting'] = selected_meeting
                        st.rerun()
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
