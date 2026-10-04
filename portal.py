import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time as dt_time
import pytz
import time

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ==========================================
# ⏰ إعدادات أوقات البوابة (توقيت بغداد)
# ==========================================
# الأحد: يفتح 8:45 م | يقفل التسجيل الجديد 9:20 م | ينتهي الاجتماع (إعادة الدخول) 10:30 م
SUN_OPEN_HOUR, SUN_OPEN_MIN = 20, 45
SUN_CLOSE_HOUR, SUN_CLOSE_MIN = 21, 20
SUN_END_HOUR, SUN_END_MIN = 22, 30

# الأربعاء: يفتح 8:15 م | يقفل التسجيل الجديد 8:50 م | ينتهي الاجتماع (إعادة الدخول) 10:15 م
WED_OPEN_HOUR, WED_OPEN_MIN = 20, 15
WED_CLOSE_HOUR, WED_CLOSE_MIN = 20, 50
WED_END_HOUR, WED_END_MIN = 22, 15

ROOM_LOCK_MINUTES = 20

# ==========================================
# 🛡️ إعدادات واجهة المستخدم (حماية الرابط وتصميم الزر)
# ==========================================
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖")

st.markdown("""
<style>
    /* 1. حماية ضد النسخ: منع تحديد النصوص في كامل الصفحة */
    body, [data-testid="stAppViewContainer"] {
        -webkit-touch-callout: none !important;
        -webkit-user-select: none !important;
        user-select: none !important;
    }
    /* السماح بالكتابة فقط في حقول الإدخال */
    input, textarea {
        -webkit-touch-callout: default !important;
        -webkit-user-select: auto !important;
        user-select: auto !important;
    }
    
    /* 2. تصميم الزر الأخضر العريض */
    .stLinkButton {
        display: flex;
        justify-content: center;
    }
    .stLinkButton a {
        background-color: #28a745 !important; /* لون أخضر */
        color: white !important;
        font-size: 20px !important;
        font-weight: bold !important;
        padding: 15px 25px !important;
        border-radius: 8px !important;
        text-align: center !important;
        text-decoration: none !important;
        width: 100% !important; /* عرض كامل */
        display: block !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    .stLinkButton a:hover {
        background-color: #218838 !important; /* أخضر أغمق عند التمرير */
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔧 Helper Functions & Caching
# ==========================================

def format_time_arabic(hour, minute):
    period = "مساءً" if hour >= 12 else "صباحاً"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{minute:02d} {period}"

# دالة إعادة المحاولة لحماية API من الضغط (429)
def safe_execute(action_fn, max_retries=3, delay=2.0):
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

# دالة قراءة الحضور اليومي مع كاش يتحدث كل 60 ثانية لحماية الـ API من الانهيار
@st.cache_data(ttl=60)
def get_todays_attendees(target_sheet_id, today_date_str):
    try:
        client = get_google_client()
        target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
        try:
            attendance_tab = safe_execute(lambda: target_db.worksheet("Attendance"))
        except Exception:
            attendance_tab = safe_execute(lambda: target_db.sheet1)
        
        # قراءة كل السجلات
        records = safe_execute(lambda: attendance_tab.get_all_values())
        
        attended_emails = set()
        if records and len(records) > 1:
            for row in records[1:]:
                if len(row) >= 2:
                    row_time = str(row[0]).strip()
                    row_email = str(row[1]).strip().lower()
                    # التأكد من أن الحضور تم اليوم
                    if row_time.startswith(today_date_str):
                        attended_emails.add(row_email)
        return attended_emails
    except Exception:
        return set()

# الكاش السريع לקائمة المسجلين (يقلل الضغط)
@st.cache_data(ttl=600) 
def get_cached_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
    # تنظيف وتوحيد حالة الأحرف
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

# الدالة اللحظية (Bypass Cache) - تُستخدم فقط كخط دفاع أخير للإدخال المتأخر
def get_live_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
    # تنظيف وتوحيد حالة الأحرف
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

# ==========================================
# ⏰ تحديد حالة البوابة حسب توقيت بغداد
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
today_date_str = now.strftime("%Y-%m-%d")
weekday = now.weekday()  # 6 = الأحد، 2 = الأربعاء
now_time = now.time()

is_testing = st.secrets.get("test_mode", False)
gate_status = "CLOSED"  # CLOSED | OPEN_NEW | REJOIN_ONLY

if is_testing:
    gate_status = "OPEN_NEW"
else:
    if weekday == 6:
        open_t = dt_time(SUN_OPEN_HOUR, SUN_OPEN_MIN)
        close_t = dt_time(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
        end_t = dt_time(SUN_END_HOUR, SUN_END_MIN)
        if open_t <= now_time <= close_t:
            gate_status = "OPEN_NEW"
        elif close_t < now_time <= end_t:
            gate_status = "REJOIN_ONLY"
    elif weekday == 2:
        open_t = dt_time(WED_OPEN_HOUR, WED_OPEN_MIN)
        close_t = dt_time(WED_CLOSE_HOUR, WED_CLOSE_MIN)
        end_t = dt_time(WED_END_HOUR, WED_END_MIN)
        if open_t <= now_time <= close_t:
            gate_status = "OPEN_NEW"
        elif close_t < now_time <= end_t:
            gate_status = "REJOIN_ONLY"

# إغلاق تام خارج الأوقات
if gate_status == "CLOSED":
    sun_open_str = format_time_arabic(SUN_OPEN_HOUR, SUN_OPEN_MIN)
    sun_close_str = format_time_arabic(SUN_CLOSE_HOUR, SUN_CLOSE_MIN)
    wed_open_str = format_time_arabic(WED_OPEN_HOUR, WED_OPEN_MIN)
    wed_close_str = format_time_arabic(WED_CLOSE_HOUR, WED_CLOSE_MIN)

    st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
    st.warning("⛔ عذراً، تسجيل الحضور مغلق حالياً.")
    st.info(
        f"يُفتح تسجيل الدخول فقط في أوقات الاجتماعات:\n\n"
        f"- **الأحد:** من الساعة {sun_open_str} حتى {sun_close_str}\n"
        f"- **الأربعاء:** من الساعة {wed_open_str} حتى {wed_close_str}\n"
        f"*(بتوقيت بغداد)*"
    )
    st.stop()

# ==========================================
# 🖥️ واجهة البوابة المفتوحة
# ==========================================
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)
if is_testing:
    st.warning("🛠️ **تنبيه:** البوابة تعمل حالياً في وضع الاختبار.")
st.markdown("---")

if gate_status == "REJOIN_ONLY":
    st.warning("⏳ **تنبيه:** انتهت فترة التسجيل للمرة الأولى. البوابة مفتوحة فقط لإعادة دخول من سجّل حضوره مسبقاً اليوم.")
else:
    st.markdown(f"""
    <div style="background-color: #ffe6e6; padding: 15px; border-radius: 8px; border: 2px solid red; text-align: center; margin-bottom: 25px;">
        <h3 style="color: #c62828; margin: 0; font-weight: bold; line-height: 1.4;">
            ⚠ يرجى العلم أن الغرفة ستغلق بعد {ROOM_LOCK_MINUTES} دقيقة من بداية الاجتماع.
        </h3>
    </div>
    """, unsafe_allow_html=True)

# جلب بيانات الاجتماع
try:
    meetings_data = get_meetings_data()
    available_meetings = [str(x).strip() for x in meetings_data['Meeting Day'].tolist()]
except Exception as e:
    st.error(f"خطأ أثناء جلب البيانات: {e}")
    st.stop()

selected_meeting = "الأحد" if weekday == 6 else "الأربعاء"
if is_testing:
    selected_meeting = st.radio("اختر الاجتماع (وضع الاختبار):", options=["الأحد", "الأربعاء"], horizontal=True)

if selected_meeting not in available_meetings:
    st.error(f"⚠️ لم يتم العثور على إعدادات اجتماع **{selected_meeting}**.")
    st.stop()

st.info(f"📌 الاجتماع المحدد: **{selected_meeting}**")

# إدخال البريد الإلكتروني مع تنظيف وتوحيد حالة الأحرف
user_email = st.text_input("أدخل البريد الإلكتروني المسجل:").strip().lower()

# تهيئة قائمة "الحاضرين اليوم" في ذاكرة السيرفر المشتركة (In-memory Storage)
if 'today_attendees' not in st.session_state:
    st.session_state['today_attendees'] = set()

# عهد التعافي
if gate_status == "OPEN_NEW":
    st.markdown("---")
    st.markdown("### 🤝 عهد التعافي")
    pledge = st.checkbox("أتعهد بصدق وأمانة أمام نفسي وتجاه زمالتي، أنني أسجل الآن بنية الحضور الفعلي للاجتماع في وقته المحدد.")
    btn_text = "تسجيل الحضور والدخول"
else:
    pledge = True
    btn_text = "التحقق والعودة للاجتماع (Re-join)"

# ==========================================
# 🎯 منطق التسجيل (مع التحقق المزدوج)
# ==========================================
if pledge:
    if st.button(btn_text, use_container_width=True):
        if not user_email:
            st.warning("يرجى إدخال البريد الإلكتروني.")
        else:
            with st.spinner("جاري التحقق..."):
                try:
                    meeting_info = meetings_data[meetings_data['Meeting Day'] == selected_meeting].iloc[0]
                    target_id = str(meeting_info['Target Sheet ID']).strip()
                    zoom_link = str(meeting_info['Zoom Link']).strip()

                    # حالة 1: إعادة الدخول (Re-join) بعد انتهاء فترة التسجيل
                    if gate_status == "REJOIN_ONLY":
                        is_verified = False
                        
                        # الخطوة أ: فحص ذاكرة الجلسة الحالية (إذا لم يغلق المتصفح)
                        if user_email in st.session_state.get('today_attendees', set()):
                            is_verified = True
                        else:
                            # الخطوة ب: العضو أغلق المتصفح وعاد! نقرأ شيت الحضور من الكاش الآمن
                            todays_attendees = get_todays_attendees(target_id, today_date_str)
                            if user_email in todays_attendees:
                                is_verified = True

                        if is_verified:
                            st.session_state['check_in_success'] = True
                            st.session_state['zoom_link'] = zoom_link
                            st.session_state['is_rejoin'] = True
                            st.session_state['today_attendees'].add(user_email) # تحديث الجلسة
                            st.rerun()
                        else:
                            st.error("❌ عذراً، لم نجد تسجيل حضور لك اليوم قبل إغلاق البوابة.")

                    # حالة 2: تسجيل جديد (الفترة المفتوحة)
                    else:
                        is_registered = False
                        
                        # 1. التحقق السريع (الكاش) لتخفيف الضغط
                        cached_emails = get_cached_registered_emails(target_id)
                        if user_email in cached_emails:
                            is_registered = True
                        else:
                            # 2. التحقق المزدوج (Bypass Cache) للحالات المتأخرة
                            live_emails = get_live_registered_emails(target_id)
                            if user_email in live_emails:
                                is_registered = True
                                get_cached_registered_emails.clear() # تحديث الكاش

                        if is_registered:
                            st.session_state['today_attendees'].add(user_email)
                            
                            baghdad_time = datetime.now(baghdad_tz).strftime("%Y-%m-%d %H:%M:%S")
                            client = get_google_client()
                            target_db = safe_execute(lambda: client.open_by_key(target_id))
                            try:
                                attendance_tab = safe_execute(lambda: target_db.worksheet("Attendance"))
                            except Exception:
                                attendance_tab = safe_execute(lambda: target_db.sheet1)
                            
                            safe_execute(lambda: attendance_tab.append_row([baghdad_time, user_email]))
                            
                            # مسح كاش الحضور ليتمكن من العودة لو انقطع اتصاله فورا
                            get_todays_attendees.clear()

                            st.session_state['check_in_success'] = True
                            st.session_state['zoom_link'] = zoom_link
                            st.session_state['is_rejoin'] = False
                            st.rerun()
                        else:
                            st.error(f"❌ عذراً، بريدك الإلكتروني غير مسجل في قائمة {selected_meeting}.")

                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
else:
    st.info("💡 يرجى وضع علامة (صح) على التعهد لتفعيل زر الدخول.")

# ==========================================
# 🟢 زر الدخول المباشر الأخضر
# ==========================================
if st.session_state.get('check_in_success', False):
    st.markdown("---")
    if st.session_state.get('is_rejoin', False):
        st.success("✅ مرحباً بعودتك! تم التحقق من تسجيلك المسبق.")
    else:
        st.success("✅ تم تسجيل حضورك بنجاح!")

    zoom_link = st.session_state['zoom_link']
    
    # الزر الأخضر العريض - استخدمنا CSS المضاف أعلى الملف لجعله أخضراً وعريضاً
    st.link_button("🚀 الدخول المباشر للاجتماع", zoom_link, use_container_width=True)
