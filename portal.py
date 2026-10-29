import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time as dt_time, timedelta
import pytz
import time
import json

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
MASTER_SHEET_ID = "1faXF9pNeKu5PrP7d-cwcQrBUd965tGZF3rWtO9s5eLY"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# رابط التسجيل الخاص بيوم الأربعاء
WEDNESDAY_REGISTRATION_URL = "https://docs.google.com/forms/d/e/1FAIpQLSftm8fJ-knqjrIiZCyYtHcSXgbIgN2hGP8xPU3WJJ1jSnwWhQ/viewform?usp=header"

# ==========================================
# ⏰ إعدادات أوقات البوابة (توقيت بغداد)
# ==========================================
SUN_OPEN_HOUR, SUN_OPEN_MIN = 20, 45
SUN_CLOSE_HOUR, SUN_CLOSE_MIN = 21, 20
SUN_END_HOUR, SUN_END_MIN = 22, 30

WED_OPEN_HOUR, WED_OPEN_MIN = 20, 15
WED_CLOSE_HOUR, WED_CLOSE_MIN = 20, 50
WED_END_HOUR, WED_END_MIN = 22, 15

ROOM_LOCK_MINUTES = 20

# المدن المرجعية المعتمدة في البوابة
REFERENCE_CITIES = [
    {"name": "بغداد", "tz": "Asia/Baghdad", "flag": "🇮🇶"},
    {"name": "الرياض", "tz": "Asia/Riyadh", "flag": "🇸🇦"},
    {"name": "دبي", "tz": "Asia/Dubai", "flag": "🇦🇪"},
    {"name": "القاهرة", "tz": "Africa/Cairo", "flag": "🇪🇬"},
]

# ترجمة أشهر المدن العربية والعالمية لعرض التوقيت المحلي للمستخدم بشكل واضح
ARABIC_CITY_NAMES = {
    "Asia/Baghdad": "بغداد (العراق)",
    "Asia/Riyadh": "الرياض (السعودية)",
    "Asia/Dubai": "دبي (الإمارات)",
    "Africa/Cairo": "القاهرة (مصر)",
    "Asia/Kuwait": "الكويت",
    "Asia/Qatar": "الدوحة (قطر)",
    "Asia/Bahrain": "المنامة (البحرين)",
    "Asia/Muscat": "مسقط (عُمان)",
    "Asia/Amman": "عمّان (الأردن)",
    "Asia/Beirut": "بيروت (لبنان)",
    "Asia/Damascus": "دمشق (سوريا)",
    "Asia/Gaza": "غزة (فلسطين)",
    "Asia/Hebron": "الخليل (فلسطين)",
    "Asia/Jerusalem": "القدس",
    "Asia/Aden": "عدن (اليمن)",
    "Africa/Khartoum": "الخرطوم (السودان)",
    "Africa/Tripoli": "طرابلس (ليبيا)",
    "Africa/Tunis": "تونس",
    "Africa/Algiers": "الجزائر",
    "Africa/Casablanca": "الدار البيضاء (المغرب)",
    "Europe/Istanbul": "إسطنبول (تركيا)",
    "Europe/London": "لندن (بريطانيا)",
    "Europe/Berlin": "برلين (ألمانيا)",
    "Europe/Paris": "باريس (فرنسا)",
    "Europe/Stockholm": "ستوكهولم (السويد)",
    "America/New_York": "نيويورك (أمريكا)",
    "America/Chicago": "شيكاغو (أمريكا)",
    "America/Los_Angeles": "لوس أنجلوس (أمريكا)",
    "America/Toronto": "تورونتو (كندا)",
    "Australia/Sydney": "سيدني (أستراليا)",
}

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
    input, textarea {
        -webkit-touch-callout: default !important;
        -webkit-user-select: auto !important;
        user-select: auto !important;
    }
    
    /* 2. تصميم جميع الأزرار (البرمجية والروابط) لتكون خضراء وعريضة - جزء من التمويه */
    .stButton button, .stLinkButton a {
        background-color: #28a745 !important; 
        color: white !important;
        font-size: 20px !important;
        font-weight: bold !important;
        padding: 10px 25px !important;
        border-radius: 8px !important;
        text-align: center !important;
        text-decoration: none !important;
        width: 100% !important; 
        display: block !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        transition: 0.3s !important;
        border: none !important;
    }
    .stButton button:hover, .stLinkButton a:hover {
        background-color: #218838 !important; 
        transform: translateY(-2px) !important;
    }

    /* 3. تنسيق جدول مواعيد البوابة المتجاوب */
    .schedule-container {
        direction: rtl;
        text-align: right;
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .schedule-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        font-size: 15px;
    }
    .schedule-table th {
        background-color: #f1f5f9;
        color: #1e293b;
        padding: 10px;
        border-bottom: 2px solid #cbd5e1;
        text-align: right;
    }
    .schedule-table td {
        padding: 10px;
        border-bottom: 1px solid #e2e8f0;
        color: #334155;
    }
    .highlight-row {
        background-color: #f0fdf4 !important;
        font-weight: bold;
    }
    .dst-badge {
        display: inline-block;
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeeba;
        border-radius: 6px;
        padding: 2px 6px;
        font-size: 12px;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔧 Helper Functions & Timezone Math
# ==========================================

def format_time_arabic(hour, minute):
    period = "مساءً" if hour >= 12 else "صباحاً"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    return f"{h12}:{minute:02d} {period}"

def get_next_meeting_window(now_baghdad, target_weekday, open_h, open_m, close_h, close_m, end_h, end_m):
    """
    حساب التاريخ الدقيق للاجتماع القادم بتوقيت بغداد، مما يضمن دقة التحويل
    حسب التوقيت الصيفي أو الشتوي المطبق فعلياً في يوم الاجتماع القادم.
    """
    baghdad_tz = pytz.timezone("Asia/Baghdad")
    days_ahead = (target_weekday - now_baghdad.weekday()) % 7
    candidate_date = now_baghdad.date() + timedelta(days=days_ahead)

    end_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(end_h, end_m)))
    # إذا كان اليوم هو يوم الاجتماع ولكن الاجتماع انتهى، ننتقل للأسبوع القادم
    if days_ahead == 0 and now_baghdad > end_dt:
        candidate_date += timedelta(days=7)
        end_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(end_h, end_m)))

    open_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(open_h, open_m)))
    close_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(close_h, close_m)))
    return open_dt, close_dt, end_dt

def convert_window_to_tz(open_dt, close_dt, now_baghdad, tz_name):
    """
    تحويل وقت فتح وإغلاق البوابة إلى المنطقة الزمنية المستهدفة في تاريخ الاجتماع تحديداً،
    مع فحص ما إذا كان هناك تغيير في الساعة (صيفي/شتوي) بين اللحظة الحالية ويوم الاجتماع.
    """
    target_tz = pytz.timezone(tz_name)
    now_in_target = now_baghdad.astimezone(target_tz)
    open_in_target = open_dt.astimezone(target_tz)
    close_in_target = close_dt.astimezone(target_tz)

    # فحص تغير فرق التوقيت (DST) بين اليوم ويوم الاجتماع
    dst_changed = now_in_target.utcoffset() != open_in_target.utcoffset()

    open_str = format_time_arabic(open_in_target.hour, open_in_target.minute)
    close_str = format_time_arabic(close_in_target.hour, close_in_target.minute)

    # في حال تغير اليوم عند التحويل لدول بعيدة (مثل أمريكا أو أستراليا)
    ARABIC_WEEKDAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_note = ""
    if open_in_target.date() != open_dt.date():
        day_note = f" ({ARABIC_WEEKDAYS[open_in_target.weekday()]})"

    return {
        "range_str": f"من {open_str} حتى {close_str}{day_note}",
        "open_str": open_str,
        "close_str": close_str,
        "dst_changed": dst_changed,
        "date_str": open_in_target.strftime("%Y-%m-%d"),
    }

def render_live_clocks_and_local_detector(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt, next_meeting_label):
    """
    لوحة ساعات حية تعمل مباشرة في متصفح المستخدم بدون إعادة تحميل الصفحة (Zero Rerun)،
    وتتعرف تلقائياً على مدينة المستخدم وتفحص التوقيت الصيفي/الشتوي ليوم الاجتماع.
    """
    payload = {
        "sunOpenMs": int(sun_open_dt.timestamp() * 1000),
        "sunCloseMs": int(sun_close_dt.timestamp() * 1000),
        "wedOpenMs": int(wed_open_dt.timestamp() * 1000),
        "wedCloseMs": int(wed_close_dt.timestamp() * 1000),
        "nextMeetingLabel": next_meeting_label,
        "cityMap": ARABIC_CITY_NAMES,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <style>
        * {{
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Cairo", sans-serif;
            user-select: none;
        }}
        body {{
            margin: 0;
            padding: 2px;
            background: transparent;
            direction: rtl;
        }}
        .clocks-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 12px;
        }}
        @media (max-width: 640px) {{
            .clocks-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        .clock-card {{
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 10px 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        }}
        .city-title {{
            font-size: 14px;
            font-weight: 700;
            color: #334155;
            margin-bottom: 4px;
        }}
        .city-time {{
            font-size: 17px;
            font-weight: 800;
            color: #0f766e;
            letter-spacing: 0.3px;
        }}
        .local-banner {{
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border: 1px solid #86efac;
            border-right: 5px solid #16a34a;
            border-radius: 10px;
            padding: 12px 15px;
            color: #14532d;
            font-size: 14.5px;
            line-height: 1.6;
        }}
        .local-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 6px;
            border-bottom: 1px dashed #86efac;
            padding-bottom: 6px;
        }}
        .local-Schedule {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 6px;
        }}
        .dst-alert {{
            margin-top: 8px;
            background-color: #fffbeb;
            border: 1px solid #fde68a;
            border-right: 4px solid #f59e0b;
            color: #92400e;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 13px;
            display: none;
        }}
    </style>
    </head>
    <body>
        <div class="clocks-grid">
            <div class="clock-card">
                <div class="city-title">🇮🇶 بغداد</div>
                <div class="city-time" id="clk-baghdad">--:--:--</div>
            </div>
            <div class="clock-card">
                <div class="city-title">🇸🇦 الرياض</div>
                <div class="city-time" id="clk-riyadh">--:--:--</div>
            </div>
            <div class="clock-card">
                <div class="city-title">🇦🇪 دبي</div>
                <div class="city-time" id="clk-dubai">--:--:--</div>
            </div>
            <div class="clock-card">
                <div class="city-title">🇪🇬 القاهرة</div>
                <div class="city-time" id="clk-cairo">--:--:--</div>
            </div>
        </div>

        <div class="local-banner">
            <div class="local-header">
                <div>📍 <b>توقيتك المحلي المكتشف:</b> <span id="user-city-name">جاري التحديد...</span></div>
                <div>🕒 <b>الساعة لديك الآن:</b> <span id="clk-local" style="font-weight:800; color:#15803d;">--:--:--</span></div>
            </div>
            <div>
                🗓️ <b>مواعيد فتح البوابة القادمة حسب توقيتك المحلي:</b>
                <div class="local-Schedule">
                    <span>🔹 <b>الأحد:</b> <span id="local-sun-time">--</span></span>
                    <span>🔹 <b>الأربعاء:</b> <span id="local-wed-time">--</span></span>
                </div>
            </div>
            <div class="dst-alert" id="local-dst-alert">
                🔔 <b>تنبيه تغيير التوقيت:</b> ستشهد منطقتك الزمنية تغييراً في الساعة (التوقيت الصيفي/الشتوي) قبل موعد الاجتماع. الأوقات المعروضة أعلاه محسوبة ومحدّثة تلقائياً وفق التوقيت الجديد ليوم الاجتماع.
            </div>
        </div>

        <script>
            const DATA = {payload_json};
            const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Baghdad";
            const arabicCity = DATA.cityMap[userTz] || userTz;
            document.getElementById("user-city-name").textContent = arabicCity + " (" + userTz + ")";

            function formatArabicLiveClock(dateObj, tz) {{
                const parts = new Intl.DateTimeFormat('en-US', {{
                    timeZone: tz,
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                }}).formatToParts(dateObj);
                let h = 0, m = "00", s = "00";
                for (const p of parts) {{
                    if (p.type === 'hour') h = parseInt(p.value, 10);
                    if (p.type === 'minute') m = p.value;
                    if (p.type === 'second') s = p.value;
                }}
                if (h === 24) h = 0;
                const period = h >= 12 ? "مساءً" : "صباحاً";
                let h12 = h % 12;
                if (h12 === 0) h12 = 12;
                return h12 + ":" + m + ":" + s + " " + period;
            }}

            function formatArabicShortTime(ms, tz) {{
                const d = new Date(ms);
                const parts = new Intl.DateTimeFormat('en-US', {{
                    timeZone: tz,
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit'
                }}).formatToParts(d);
                let h = 0, m = "00";
                for (const p of parts) {{
                    if (p.type === 'hour') h = parseInt(p.value, 10);
                    if (p.type === 'minute') m = p.value;
                }}
                if (h === 24) h = 0;
                const period = h >= 12 ? "مساءً" : "صباحاً";
                let h12 = h % 12;
                if (h12 === 0) h12 = 12;
                return h12 + ":" + m + " " + period;
            }}

            function getTzOffsetMinutes(dateObj, tz) {{
                const utcDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: 'UTC' }}));
                const tzDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: tz }}));
                return Math.round((tzDate - utcDate) / 60000);
            }}

            function initStaticSchedules() {{
                const sunStr = "من " + formatArabicShortTime(DATA.sunOpenMs, userTz) + " حتى " + formatArabicShortTime(DATA.sunCloseMs, userTz);
                const wedStr = "من " + formatArabicShortTime(DATA.wedOpenMs, userTz) + " حتى " + formatArabicShortTime(DATA.wedCloseMs, userTz);
                document.getElementById("local-sun-time").textContent = sunStr;
                document.getElementById("local-wed-time").textContent = wedStr;

                // فحص ما إذا كان هناك تغيير توقيت صيفي/شتوي بين الآن وموعد الاجتماع
                const nowOffset = getTzOffsetMinutes(new Date(), userTz);
                const sunOffset = getTzOffsetMinutes(new Date(DATA.sunOpenMs), userTz);
                const wedOffset = getTzOffsetMinutes(new Date(DATA.wedOpenMs), userTz);
                if (nowOffset !== sunOffset || nowOffset !== wedOffset) {{
                    document.getElementById("local-dst-alert").style.display = "block";
                }}
            }}

            function tickClocks() {{
                const now = new Date();
                document.getElementById("clk-baghdad").textContent = formatArabicLiveClock(now, "Asia/Baghdad");
                document.getElementById("clk-riyadh").textContent = formatArabicLiveClock(now, "Asia/Riyadh");
                document.getElementById("clk-dubai").textContent = formatArabicLiveClock(now, "Asia/Dubai");
                document.getElementById("clk-cairo").textContent = formatArabicLiveClock(now, "Africa/Cairo");
                document.getElementById("clk-local").textContent = formatArabicLiveClock(now, userTz);
            }}

            initStaticSchedules();
            tickClocks();
            setInterval(tickClocks, 1000);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=215, scrolling=False)

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

@st.cache_data(ttl=60)
def get_todays_attendees(target_sheet_id, today_date_str):
    try:
        client = get_google_client()
        target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
        try:
            attendance_tab = safe_execute(lambda: target_db.worksheet("Attendance"))
        except Exception:
            attendance_tab = safe_execute(lambda: target_db.sheet1)
        
        records = safe_execute(lambda: attendance_tab.get_all_values())
        attended_emails = set()
        if records and len(records) > 1:
            for row in records[1:]:
                if len(row) >= 2:
                    row_time = str(row[0]).strip()
                    row_email = str(row[1]).strip().lower()
                    if row_time.startswith(today_date_str):
                        attended_emails.add(row_email)
        return attended_emails
    except Exception:
        return set()

@st.cache_data(ttl=600) 
def get_cached_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

def get_live_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()

# ==========================================
# ⏰ تحديد حالة البوابة وحساب مواعيد الاجتماعات القادمة
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
today_date_str = now.strftime("%Y-%m-%d")
weekday = now.weekday()
now_time = now.time()

# حساب التواريخ الدقيقة للاجتماع القادم ليومي الأحد والأربعاء
sun_open_dt, sun_close_dt, sun_end_dt = get_next_meeting_window(
    now, 6, SUN_OPEN_HOUR, SUN_OPEN_MIN, SUN_CLOSE_HOUR, SUN_CLOSE_MIN, SUN_END_HOUR, SUN_END_MIN
)
wed_open_dt, wed_close_dt, wed_end_dt = get_next_meeting_window(
    now, 2, WED_OPEN_HOUR, WED_OPEN_MIN, WED_CLOSE_HOUR, WED_CLOSE_MIN, WED_END_HOUR, WED_END_MIN
)

if sun_open_dt <= wed_open_dt:
    next_meeting_day_name = "الأحد"
    next_meeting_open_dt = sun_open_dt
else:
    next_meeting_day_name = "الأربعاء"
    next_meeting_open_dt = wed_open_dt

# بناء قائمة المدن للجدول (المدن الـ 4 الأساسية + مدينة المستخدم إذا كانت مختلفة)
detected_user_tz = getattr(st.context, "timezone", None)
cities_to_display = [dict(c, is_local=False) for c in REFERENCE_CITIES]

if detected_user_tz:
    existing_tzs = [c["tz"] for c in cities_to_display]
    if detected_user_tz not in existing_tzs:
        try:
            pytz.timezone(detected_user_tz)
            local_label = ARABIC_CITY_NAMES.get(detected_user_tz, detected_user_tz)
            cities_to_display.insert(0, {
                "name": f"توقيتك ({local_label})",
                "tz": detected_user_tz,
                "flag": "📍",
                "is_local": True
            })
        except Exception:
            pass
    else:
        for c in cities_to_display:
            if c["tz"] == detected_user_tz:
                c["is_local"] = True

# حساب الجدول المحول لكل مدينة مع رصد التوقيت الصيفي/الشتوي
schedule_rows = []
any_dst_change_detected = False

for city in cities_to_display:
    sun_conv = convert_window_to_tz(sun_open_dt, sun_close_dt, now, city["tz"])
    wed_conv = convert_window_to_tz(wed_open_dt, wed_close_dt, now, city["tz"])
    city_has_dst_shift = sun_conv["dst_changed"] or wed_conv["dst_changed"]
    if city_has_dst_shift:
        any_dst_change_detected = True

    schedule_rows.append({
        "flag": city["flag"],
        "name": city["name"],
        "is_local": city.get("is_local", False),
        "sun_range": sun_conv["range_str"],
        "wed_range": wed_conv["range_str"],
        "sun_dst": sun_conv["dst_changed"],
        "wed_dst": wed_conv["dst_changed"],
    })

is_testing = st.secrets.get("test_mode", False)
gate_status = "CLOSED" 

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

# ==========================================
# 📖 العنوان الرئيسي والساعات الحية ودليل الاستخدام 
# ==========================================
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)

# 🕒 عرض الساعات الحية والتعرف التلقائي على توقيت المستخدم
render_live_clocks_and_local_detector(
    sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt, next_meeting_day_name
)

# إضافة التلميح التقني هنا (الإضافة الأولى)
st.markdown("""
<div style="background-color: #e8f4f8; border-right: 5px solid #17a2b8; padding: 15px; border-radius: 8px; margin-bottom: 20px; direction: rtl; text-align: right;">
    <h4 style="color: #0c5460; margin-top: 0; margin-bottom: 10px;">💡 تلميح تقني لتجربة أفضل</h4>
    <p style="color: #0c5460; font-size: 15px; margin: 0;">
        إذا فتحت هذه البوابة مباشرة من داخل <b>تطبيق الإيميل</b> ولم يفتح معك (Zoom) عند الضغط على زر الدخول، نرجو الضغط على <b>النقاط الثلاث (⋮)</b> بالأعلى، واختيار <b>"فتح في المتصفح" (يرجى استخدام متصفح جوجل كروم لفتح البوابة)</b>.
    </p>
</div>
""", unsafe_allow_html=True)

with st.expander("📖 دليل الاستخدام والقواعد التنظيمية الهامة (اضغط للقراءة)", expanded=False):
    st.markdown("""
    **الإخوة والأخوات، أعضاء وضيوف زمالة الخليج، تحية طيبة وبعد..**
    
    لضمان بيئة آمنة للتعافي، وحرصاً منا على احترام وقت الجميع وحماية اجتماعاتنا، نضع بين أيديكم دليل استخدام "البوابة الآلية".
    
    صُمم هذا النظام ليحمي خصوصيتنا التامة؛ فنحن لا نطلب ولا نحفظ أي أسماء أو بيانات شخصية، فقط **"بريدك الإلكتروني"** كمعرف وحيد لك. النظام يعمل آلياً لضمان الانضباط وحماية المجموعة، ليبقى تركيزنا منصبّاً فقط على رسالتنا وتعافينا.
    
    نرجو قراءة الخطوات والقواعد التالية بعناية:
    
    ### 📝 خطوات الدخول:
    * **الرابط:** ادخل عبر الرابط المُرسل إلى بريدك الإلكتروني في يوم الاجتماع.
    * **البريد الإلكتروني:** اكتب إيميلك المسجل لدينا بدقة (حروف إنجليزية صغيرة وبدون مسافات).
    * **عهد التعافي:** يُشترط قراءة التعهد بصدق نية الحضور الفعلي ووضع علامة (صح) بجانبه. بدون هذا التعهد لن يُفتح لك باب الاجتماع.
    * **الدخول المباشر:** بعد الضغط على "تسجيل الحضور"، سيظهر لك زر أخضر ينقلك مباشرة لقاعة (Zoom).
    
    ### 🛑 الأمانة في الحضور (تنويه هام جداً):
    الأمانة هي حجر الأساس في برنامجنا. وقد لُوحظ مؤخراً قيام البعض بتسجيل الحضور عبر البوابة دون الدخول الفعلي لقاعة الاجتماع (زووم).
    
    نود التوضيح أن منصة (Zoom) تقوم تلقائياً بحفظ سجل دقيق بأسماء جميع الحاضرين ووقت دخولهم؛ لذا فإن آلية مطابقة من **"سجّل في البوابة"** مع من **"تواجد فعلياً في القاعة"** هي عملية بسيطة ومتاحة لدينا، ومعرفة من يحضر ومن يغيب ليس بالأمر الصعب إطلاقاً.
    
    نحن نثق بنوايا الجميع، ولكن نذكّر بأن التسجيل الوهمي هو استغلال لمرونة النظام وإخلال بـ "عهد التعافي". وننوه بشفافية أن استمرار استغلال هذا الأمر سيقودنا مستقبلاً إلى اتخاذ خطوات تنظيمية وتقنية تمنع هذا السلوك بشكل جذري. نرجو الحرص على التسجيل فقط عندما تكون مستعداً للدخول الفعلي، احتراماً للأمانة ولروح الزمالة.
    
    ### ⏰ أوقات البوابة (الالتزام بالوقت):
    النظام مبرمج آلياً ولا يقبل الاستثناءات، احتراماً لوقت المجموعة *(المواعيد الأساسية بتوقيت مكة المكرمة/بغداد، وتظهر محولة تلقائياً لمدينتك في جدول المواعيد)*:
    * **اجتماع الأحد:** يفتح التسجيل (8:45 م)، ويُغلق آلياً (9:20 م).
    * **اجتماع الأربعاء:** يفتح التسجيل (8:15 م)، ويُغلق آلياً (8:50 م).
    * **تنبيه حازم:** تُغلق القاعة تماماً من قبل المنسقين بعد 20 دقيقة من البداية. الدخول المبكر يعكس التزامنا الجاد بتعافينا.
    
    ### 🔄 ميزة إعادة الدخول (عند انقطاع الاتصال):
    إذا انقطع عندك الإنترنت أو خرجت من القاعة لخلل تقني، فلا تقلق. افتح رابط البوابة مرة أخرى وأدخل إيميلك. سيعرف النظام أنك "أثبت حضورك مسبقاً"، وسيعطيك رابط القاعة فوراً متجاوزاً خطوة التعهد، حتى لو كان وقت التسجيل الأساسي قد انتهى.
    
    ### 📊 المسؤولية تجاه الغياب (إيقاف الدعوات):
    يراجع النظام سجلات الحضور آلياً تطبيقاً لمبدأ المسؤولية:
    * **الالتزام:** بمجرد تسجيل دخولك الفعلي، يُصفّر النظام غياباتك السابقة.
    * **الغياب:** عدم الحضور يُحتسب غياباً، وسيرسل لك النظام رسالة تنبيه وافتقاد.
    * **إيقاف الدعوات:** إذا تجاوزت الحد الأقصى للغيابات المتتالية، سيتوقف النظام آلياً عن إرسال روابط الاجتماعات لك. الأولوية والمقاعد تُعطى دائماً للملتزمين بالحضور.
    
    ### 🛠 حماية المجموعة (حذف السجلات والإيميلات):
    يعمل النظام آلياً في الخلفية لحماية الزمالة وصيانة بياناتها:
    * **الإيميلات الوهمية:** أي إيميل وهمي، أو فيه خطأ يمنعه من استلام دعواتنا، سيكتشفه النظام آلياً بعد أول محاولة إرسال، ويقوم بشطبه نهائياً من سجلاتنا.
    * **الانقطاع الطويل:** من توقفت دعواته بسبب الغياب، واستمر في الانقطاع التام لمدة 90 يوماً متواصلة، سيتم مسح إيميله من النظام بالكامل لتوفير مساحة لغيره. وإذا أراد العودة يوماً، عليه التسجيل كعضو جديد.
    * **مسح الحضور:** لحماية خصوصية الأعضاء والضيوف، يمسح النظام آلياً أي سجلات حضور مر عليها 120 يوماً ولا يبقي لها أثراً.
    
    > **وُجد هذا النظام لتطبيق المبادئ قبل الشخصيات، ولحماية قاعاتنا من أي فوضى.**
    > **نشكر لكم التزامكم وأمانتكم.. نحن بالفعل نتعافى.**
    """)

# ==========================================
# 📅 دالة عرض جدول مواعيد البوابة لمختلف المدن
# ==========================================
def render_dynamic_schedule_box(title_text):
     FLAG_URLS = {
        "Asia/Baghdad": "https://flagcdn.com/w40/iq.png",
        "Asia/Riyadh": "https://flagcdn.com/w40/sa.png",
        "Asia/Dubai": "https://flagcdn.com/w40/ae.png",
        "Africa/Cairo": "https://flagcdn.com/w40/eg.png",
    }

    rows_html = ""
    for city, row in zip(cities_to_display, schedule_rows):
        row_bg = "background-color: #f0fdf4; font-weight: 700;" if row["is_local"] else "background-color: #ffffff;"
        local_tag = "<span style='background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:12px; font-size:11px; margin-right:6px;'>مدينتك</span>" if row["is_local"] else ""
        
        flag_url = FLAG_URLS.get(city["tz"])
        if flag_url:
            flag_html = f"<img src='{flag_url}' style='width:22px; height:15px; border-radius:3px; vertical-align:middle; margin-left:8px; box-shadow:0 1px 2px rgba(0,0,0,0.15);'>"
        else:
            flag_html = "<span style='margin-left:8px;'>📍</span>"

        sun_dst = "<div style='color:#b45309; background:#fef3c7; display:inline-block; padding:1px 6px; border-radius:6px; font-size:11px; margin-top:4px;'>🔄 توقيت شتوي/صيفي محدّث</div>" if row["sun_dst"] else ""
        wed_dst = "<div style='color:#b45309; background:#fef3c7; display:inline-block; padding:1px 6px; border-radius:6px; font-size:11px; margin-top:4px;'>🔄 توقيت شتوي/صيفي محدّث</div>" if row["wed_dst"] else ""

        # ملاحظة: عدم ترك مسافات بادئة (Indentation) يمنع Streamlit من تحويل الكود إلى صندوق أسود
        rows_html += (
            f"<tr style='{row_bg} border-bottom: 1px solid #e2e8f0;'>"
            f"<td style='padding:12px 10px; color:#1e293b; white-space:nowrap;'>{flag_html}<b>{row['name']}</b>{local_tag}</td>"
            f"<td style='padding:12px 10px; color:#334155;'><div>{row['sun_range']}</div>{sun_dst}</td>"
            f"<td style='padding:12px 10px; color:#334155;'><div>{row['wed_range']}</div>{wed_dst}</td>"
            f"</tr>"
        )

    dst_footer = ""
    if any_dst_change_detected:
        dst_footer = (
            "<div style='margin-top:12px; background-color:#fffbeb; border:1px solid #fde68a; border-right:4px solid #f59e0b; color:#92400e; padding:10px 12px; border-radius:8px; font-size:13.5px;'>"
            "🔔 <b>تنبيه التوقيت الصيفي/الشتوي:</b> بعض المدن الموضحة أعلاه تشهد تغييراً في الساعة قبل موعد الاجتماع القادم. تم حساب المواعيد أعلاه تلقائياً وفق التوقيت الجديد."
            "</div>"
        )

    full_html = (
        f"<div style='direction:rtl; text-align:right; background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:18px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,0.05);'>"
        f"<h4 style='margin:0 0 8px 0; color:#0f172a; font-size:18px;'>{title_text}</h4>"
        f"<div style='background:#f8fafc; border-right:4px solid #3b82f6; padding:8px 12px; border-radius:6px; margin-bottom:14px; font-size:14.5px; color:#334155;'>"
        f"📌 الاجتماع القادم هو اجتماع يوم <b>{next_meeting_day_name}</b> الموافق <b>{next_meeting_open_dt.strftime('%Y-%m-%d')}</b>"
        f"</div>"
        f"<div style='overflow-x:auto;'>"
        f"<table style='width:100%; border-collapse:collapse; font-size:14.5px; text-align:right;'>"
        f"<thead>"
        f"<tr style='background-color:#f1f5f9; color:#0f172a; border-bottom:2px solid #cbd5e1;'>"
        f"<th style='padding:12px 10px;'>المدينة</th>"
        f"<th style='padding:12px 10px;'>اجتماع الأحد ({sun_open_dt.strftime('%m/%d')})</th>"
        f"<th style='padding:12px 10px;'>اجتماع الأربعاء ({wed_open_dt.strftime('%m/%d')})</th>"
        f"</tr>"
        f"</thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table>"
        f"</div>"
        f"{dst_footer}"
        f"</div>"
    )
    st.markdown(full_html, unsafe_allow_html=True)

if gate_status == "CLOSED":
    st.warning("⛔ عذراً، تسجيل الحضور مغلق حالياً.")
    render_dynamic_schedule_box("🕒 مواعيد فتح وإغلاق البوابة حسب المدن (محسوبة لتاريخ الاجتماع القادم):")
    st.stop()

# ==========================================
# 🖥️ واجهة البوابة المفتوحة
# ==========================================
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

with st.expander("🕒 عرض جدول مواعيد البوابة حسب المدن (بغداد، الرياض، دبي، القاهرة، وتوقيتك المحلي)", expanded=False):
    render_dynamic_schedule_box("مواعيد فتح وإغلاق البوابة:")

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

# إذا قام المستخدم بتعديل الإيميل المكتوب، يتم تصفير حالة الفخ ليقوم بالتحقق من جديد
user_email = st.text_input("أدخل البريد الإلكتروني المسجل:", value=st.session_state.get('verified_email', '')).strip().lower()
if 'verified_email' in st.session_state and user_email != st.session_state['verified_email']:
    st.session_state['trap_stage_1_passed'] = False

if 'today_attendees' not in st.session_state:
    st.session_state['today_attendees'] = set()

# ==========================================
# 🎯 منطق التحقق (المرحلة الأولى - مصيدة التوثيق فقط)
# ==========================================
# يظهر هذا القسم فقط إذا لم يكمل المستخدم المرحلة الأولى
if not st.session_state.get('trap_stage_1_passed', False):
    
    if gate_status == "OPEN_NEW":
        st.markdown("---")
        st.markdown("### 🤝 عهد التعافي")
        pledge = st.checkbox("أتعهد بصدق وأمانة أمام نفسي وتجاه زمالتي، أنني أسجل الآن بنية الحضور الفعلي للاجتماع في وقته المحدد.")
        btn_text = "تسجيل الحضور والدخول"
    else:
        pledge = True
        btn_text = "التحقق والعودة للاجتماع (Re-join)"

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

                        if gate_status == "REJOIN_ONLY":
                            is_verified = False
                            if user_email in st.session_state.get('today_attendees', set()):
                                is_verified = True
                            else:
                                todays_attendees = get_todays_attendees(target_id, today_date_str)
                                if user_email in todays_attendees:
                                    is_verified = True

                            if is_verified:
                                # اجتياز المرحلة الأولى للإعادة
                                st.session_state['trap_stage_1_passed'] = True
                                st.session_state['zoom_link'] = zoom_link
                                st.session_state['is_rejoin'] = True
                                st.session_state['verified_email'] = user_email
                                st.rerun()
                            else:
                                st.error("❌ عذراً، لم نجد تسجيل حضور لك اليوم قبل إغلاق البوابة.")

                        else:
                            is_registered = False
                            cached_emails = get_cached_registered_emails(target_id)
                            if user_email in cached_emails:
                                is_registered = True
                            else:
                                live_emails = get_live_registered_emails(target_id)
                                if user_email in live_emails:
                                    is_registered = True
                                    get_cached_registered_emails.clear()

                            if is_registered:
                                # 🪤 الفخ هنا: لا نسجل اسمه في جوجل شيت! بل نمرره للمرحلة الثانية
                                st.session_state['trap_stage_1_passed'] = True
                                st.session_state['zoom_link'] = zoom_link
                                st.session_state['is_rejoin'] = False
                                st.session_state['verified_email'] = user_email
                                st.session_state['target_id'] = target_id
                                st.rerun()
                            else:
                                if selected_meeting == "الأربعاء":
                                    st.markdown("""
                                    <div style="background-color: #fff8e1; padding: 15px; border-radius: 8px; border-right: 5px solid #ffb300; text-align: right; margin-bottom: 20px;">
                                        <h4 style="color: #ff8f00; margin-top: 0;">عذراً، البريد الإلكتروني غير مسجل 📝</h4>
                                        <p style="color: #4e342e; font-size: 16px; margin-bottom: 0;">
                                            يبدو أن هذا الإيميل غير موجود في قائمة يوم الأربعاء، لكن يسعدنا جداً انضمامك إلينا!<br><br>
                                            <b>⏳ جاري تحويلك تلقائياً إلى صفحة التسجيل...</b>
                                        </p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    st.link_button("✨ الانتقال لصفحة التسجيل فوراً", WEDNESDAY_REGISTRATION_URL, use_container_width=True)
                                    redirect_code = f"""
                                    <meta http-equiv="refresh" content="4; url={WEDNESDAY_REGISTRATION_URL}">
                                    <script>
                                        setTimeout(function() {{ window.top.location.href = "{WEDNESDAY_REGISTRATION_URL}"; }}, 4000);
                                    </script>
                                    """
                                    st.markdown(redirect_code, unsafe_allow_html=True)
                                else:
                                    st.error(f"❌ عذراً، بريدك الإلكتروني غير مسجل في قائمة {selected_meeting}.")

                    except Exception as e:
                        st.error(f"حدث خطأ: {e}")
    else:
        st.info("💡 يرجى وضع علامة (صح) على التعهد لتفعيل زر الدخول.")

# ==========================================
# 🟢 زر الدخول المباشر (المرحلة الثانية - التسجيل الفعلي الخفي)
# ==========================================
# يظهر هذا القسم فقط لمن اجتاز خطوة التحقق بنجاح ويظن أنه قد سُجل فعلاً
if st.session_state.get('trap_stage_1_passed', False):
    st.markdown("---")
    
    # رسالة تمنح شعوراً وهمياً باكتمال التسجيل
    if st.session_state.get('is_rejoin', False):
        st.success("✅ مرحباً بعودتك! تم التحقق من تسجيلك المسبق.")
    else:
        st.success("✅ تم تسجيل حضورك بنجاح!")
        
    st.info("💡 اضغط على الزر أدناه للانتقال فوراً إلى قاعة (Zoom).")

    # الزر البرمجي الذي يكتب البيانات في القاعدة، ثم يحوله
    if st.button("🚀 الدخول المباشر للاجتماع", use_container_width=True):
        
        zoom_link = st.session_state['zoom_link']
        user_email_to_record = st.session_state['verified_email']
        
        # --- التسجيل الفعلي في جوجل شيت يحدث هنا للملتزمين فقط ---
        if not st.session_state.get('is_rejoin', False):
            with st.spinner("جاري تأكيد دخولك للقاعة..."):
                try:
                    baghdad_time = datetime.now(baghdad_tz).strftime("%Y-%m-%d %H:%M:%S")
                    client = get_google_client()
                    target_id = st.session_state['target_id']
                    target_db = safe_execute(lambda: client.open_by_key(target_id))
                    try:
                        attendance_tab = safe_execute(lambda: target_db.worksheet("Attendance"))
                    except Exception:
                        attendance_tab = safe_execute(lambda: target_db.sheet1)
                    
                    # الكتابة في الشيت
                    safe_execute(lambda: attendance_tab.append_row([baghdad_time, user_email_to_record]))
                    
                    # تحديث الكاش والجلسة حتى لا يتم تسجيله مرتين
                    get_todays_attendees.clear()
                    st.session_state['today_attendees'].add(user_email_to_record)
                    st.session_state['is_rejoin'] = True 
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الاتصال بقاعدة البيانات: {e}")
        
        # كود التوجيه الفوري لـ Zoom مباشرة بعد الكتابة
        st.markdown(f"""
        <meta http-equiv="refresh" content="0; url={zoom_link}">
        <script>
            window.top.location.href = "{zoom_link}";
        </script>
        """, unsafe_allow_html=True)
        
        # رسالة تظهر للحظات أثناء التحويل
        st.info("⏳ جاري فتح قاعة Zoom، يرجى الانتظار...")
        
        # الإضافة الثانية (طوق النجاة): تظهر مباشرة بعد رسالة الانتظار لتنقذ من تعطل متصفحهم
        st.warning("⚠️ إذا لم يفتح تطبيق زووم تلقائياً الآن، اضغط على الزر أدناه:")
        st.link_button("🔗 اضغط هنا لفتح قاعة Zoom يدوياً", zoom_link, use_container_width=True)
