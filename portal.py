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

# المدن المرجعية مع روابط أعلام SVG رسمية (تظهر بوضوح على ويندوز وأيفون وأندرويد)
REFERENCE_CITIES = [
    {
        "name": "بغداد",
        "tz": "Asia/Baghdad",
        "flag_url": "https://flagcdn.com/w40/iq.png",
    },
    {
        "name": "الرياض",
        "tz": "Asia/Riyadh",
        "flag_url": "https://flagcdn.com/w40/sa.png",
    },
    {
        "name": "دبي",
        "tz": "Asia/Dubai",
        "flag_url": "https://flagcdn.com/w40/ae.png",
    },
    {
        "name": "القاهرة",
        "tz": "Africa/Cairo",
        "flag_url": "https://flagcdn.com/w40/eg.png",
    },
]

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
    "Asia/Aden": "عدن (اليمن)",
    "Africa/Khartoum": "الخرطوم (السودان)",
    "Africa/Tripoli": "طرابلس (ليبيا)",
    "Europe/Istanbul": "إسطنبول (تركيا)",
    "Europe/London": "لندن (بريطانيا)",
    "America/New_York": "نيويورك (أمريكا)",
}

# ==========================================
# 🛡️ إعدادات واجهة المستخدم
# ==========================================
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖", layout="wide")

st.markdown("""
<style>
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
    baghdad_tz = pytz.timezone("Asia/Baghdad")
    days_ahead = (target_weekday - now_baghdad.weekday()) % 7
    candidate_date = now_baghdad.date() + timedelta(days=days_ahead)

    end_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(end_h, end_m)))
    if days_ahead == 0 and now_baghdad > end_dt:
        candidate_date += timedelta(days=7)
        end_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(end_h, end_m)))

    open_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(open_h, open_m)))
    close_dt = baghdad_tz.localize(datetime.combine(candidate_date, dt_time(close_h, close_m)))
    return open_dt, close_dt, end_dt

def convert_window_to_tz(open_dt, close_dt, now_baghdad, tz_name):
    target_tz = pytz.timezone(tz_name)
    now_in_target = now_baghdad.astimezone(target_tz)
    open_in_target = open_dt.astimezone(target_tz)
    close_in_target = close_dt.astimezone(target_tz)

    dst_changed = now_in_target.utcoffset() != open_in_target.utcoffset()
    open_str = format_time_arabic(open_in_target.hour, open_in_target.minute)
    close_str = format_time_arabic(close_in_target.hour, close_in_target.minute)

    ARABIC_WEEKDAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_note = ""
    if open_in_target.date() != open_dt.date():
        day_note = f" ({ARABIC_WEEKDAYS[open_in_target.weekday()]})"

    return {
        "range_str": f"من {open_str} حتى {close_str}{day_note}",
        "dst_changed": dst_changed,
    }

def render_unified_dashboard(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt, next_meeting_label, next_meeting_date_str, schedule_data, any_dst_change):
    """
    عنصر تحكم موحد (Option A): يدمج الساعات الحية، الأعلام الرسمية، وأوقات الأحد والأربعاء لكل مدينة في واجهة عصرية متجاوبة.
    """
    payload = {
        "sunOpenMs": int(sun_open_dt.timestamp() * 1000),
        "sunCloseMs": int(sun_close_dt.timestamp() * 1000),
        "wedOpenMs": int(wed_open_dt.timestamp() * 1000),
        "wedCloseMs": int(wed_close_dt.timestamp() * 1000),
        "nextMeetingLabel": next_meeting_label,
        "nextMeetingDate": next_meeting_date_str,
        "cities": schedule_data,
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
            padding: 4px;
            background: transparent;
            direction: rtl;
        }}
        .dashboard-container {{
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        }}
        .dashboard-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            border-bottom: 2px solid #f1f5f9;
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}
        .next-meeting-badge {{
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 700;
        }}
        .cities-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
        }}
        .city-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 14px;
            text-align: right;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            transition: transform 0.2s ease;
        }}
        .city-card.local-card {{
            background: #f0fdf4;
            border: 2px solid #22c55e;
        }}
        .city-card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            border-bottom: 1px dashed #cbd5e1;
            padding-bottom: 8px;
        }}
        .city-name-wrapper {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            color: #1e293b;
            font-size: 15px;
        }}
        .city-flag {{
            width: 24px;
            height: 16px;
            border-radius: 3px;
            object-fit: cover;
            box-shadow: 0 1px 2px rgba(0,0,0,0.15);
        }}
        .live-clock {{
            font-size: 15px;
            font-weight: 800;
            color: #0d9488;
            background: #ccfbf1;
            padding: 2px 8px;
            border-radius: 6px;
        }}
        .schedule-info {{
            font-size: 13.5px;
            color: #334155;
            margin-bottom: 6px;
        }}
        .schedule-info b {{
            color: #0f172a;
        }}
        .dst-tag {{
            display: inline-block;
            background: #fef3c7;
            color: #b45309;
            font-size: 11px;
            padding: 1px 6px;
            border-radius: 4px;
            margin-top: 2px;
        }}
        .global-dst-notice {{
            margin-top: 14px;
            background-color: #fffbeb;
            border: 1px solid #fde68a;
            border-right: 4px solid #f59e0b;
            color: #92400e;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13.5px;
            display: none;
        }}
    </style>
    </head>
    <body>
        <div class="dashboard-container">
            <div class="dashboard-header">
                <div style="font-size: 17px; font-weight: 800; color: #0f172a;">
                    🕒 لوحة المواعيد والساعات الحية لفتح البوابة
                </div>
                <div class="next-meeting-badge" id="next-meeting-text">
                    📌 الاجتماع القادم: جاري التحميل...
                </div>
            </div>

            <div class="cities-grid" id="cities-grid-container">
                <!-- يتم تعبئتها ديناميكياً عبر الجافاسكريبت -->
            </div>

            <div class="global-dst-notice" id="global-dst-alert">
                🔔 <b>تنبيه التوقيت الصيفي/الشتوي:</b> بعض المدن الموضحة أعلاه ستشهد تغييراً في الساعة قبل موعد الاجتماع القادم. لقد قام النظام بحساب المواعيد أعلاه تلقائياً بناءً على التوقيت الجديد الساري يوم الاجتماع.
            </div>
        </div>

        <script>
            const DATA = {{payload_json}};
            const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Baghdad";
            const arabicUserCity = DATA.cityMap[userTz] || userTz;

            document.getElementById("next-meeting-text").innerHTML = 
                `📌 الاجتماع القادم: <b>${{DATA.nextMeetingLabel}}</b> (الموافق <b>${{DATA.nextMeetingDate}}</b>)`;

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

            let anyDst = {str(any_dst_change).lower()};

            function buildCards() {{
                const grid = document.getElementById("cities-grid-container");
                grid.innerHTML = "";

                // أولاً: بطاقة توقيت المستخدم المحلي إذا لم تكن مطابقة لإحدى المدن الأساسية
                let listToRender = [...DATA.cities];
                const hasUserTz = listToRender.some(c => c.tz === userTz);
                
                if (!hasUserTz) {{
                    listToRender.unshift({{
                        name: "توقيتك (" + arabicUserCity + ")",
                        tz: userTz,
                        flag_url: "https://flagcdn.com/w40/un.png",
                        is_local: true
                    }});
                }} else {{
                    listToRender.forEach(c => {{
                        if (c.tz === userTz) c.is_local = true;
                    }});
                }}

                listToRender.forEach(city => {{
                    const sunOpenStr = formatArabicShortTime(DATA.sunOpenMs, city.tz);
                    const sunCloseStr = formatArabicShortTime(DATA.sunCloseMs, city.tz);
                    const wedOpenStr = formatArabicShortTime(DATA.wedOpenMs, city.tz);
                    const wedCloseStr = formatArabicShortTime(DATA.wedCloseMs, city.tz);

                    const nowOffset = getTzOffsetMinutes(new Date(), city.tz);
                    const sunOffset = getTzOffsetMinutes(new Date(DATA.sunOpenMs), city.tz);
                    const isDst = nowOffset !== sunOffset;
                    if (isDst) anyDst = true;

                    const cardClass = city.is_local ? "city-card local-card" : "city-card";
                    const localBadge = city.is_local ? "<span style='background:#dcfce7; color:#15803d; padding:1px 6px; border-radius:10px; font-size:10.5px; margin-right:4px;'>مدينتك</span>" : "";
                    const dstBadge = isDst ? "<div class='dst-tag'>🔄 توقيت صيفي/شتوي محدّث</div>" : "";

                    const htmlCard = `
                        <div class="${{cardClass}}">
                            <div class="city-card-header">
                                <div class="city-name-wrapper">
                                    <img src="${{city.flag_url}}" class="city-flag" onerror="this.style.display='none'">
                                    <span>${{city.name}}</span>
                                    ${{localBadge}}
                                </div>
                                <div class="live-clock" id="clock-${{city.tz.replace(/[^a-zA-Z0-9]/g, '_')}}">--:--:--</div>
                            </div>
                            <div class="schedule-info">
                                🔹 <b>الأحد:</b> من ${{sunOpenStr}} حتى ${{sunCloseStr}}
                            </div>
                            <div class="schedule-info" style="margin-bottom:0;">
                                🔹 <b>الأربعاء:</b> من ${{wedOpenStr}} حتى ${{wedCloseStr}}
                            </div>
                            ${{dstBadge}}
                        </div>
                    `;
                    grid.innerHTML += htmlCard;
                }});

                if (anyDst) {{
                    document.getElementById("global-dst-alert").style.display = "block";
                }}
            }}

            function updateClocks() {{
                const now = new Date();
                const listToRender = [...DATA.cities];
                if (!listToRender.some(c => c.tz === userTz)) {{
                    listToRender.unshift({{ tz: userTz }});
                }}
                listToRender.forEach(city => {{
                    const elId = "clock-" + city.tz.replace(/[^a-zA-Z0-9]/g, '_');
                    const el = document.getElementById(elId);
                    if (el) {{
                        el.textContent = formatArabicLiveClock(now, city.tz);
                    }}
                }});
            }}

            buildCards();
            updateClocks();
            setInterval(updateClocks, 1000);
        </script>
    </body>
    </html>
    """
    # ضبط الارتفاع ليتناسب مع عدد البطاقات (صفين من البطاقات)
    components.html(html_code, height=360, scrolling=False)

# ==========================================
# ⏰ تحديد حالة البوابة وحساب مواعيد الاجتماعات القادمة
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
today_date_str = now.strftime("%Y-%m-%d")
weekday = now.weekday()
now_time = now.time()

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

# فحص تغير التوقيت الصيفي/الشتوي للمدن الأساسية
any_dst_change_detected = False
for c in REFERENCE_CITIES:
    sun_conv = convert_window_to_tz(sun_open_dt, sun_close_dt, now, c["tz"])
    wed_conv = convert_window_to_tz(wed_open_dt, wed_close_dt, now, c["tz"])
    if sun_conv["dst_changed"] or wed_conv["dst_changed"]:
        any_dst_change_detected = True

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
# 📖 العنوان الرئيسي ولوحة المواعيد الموحدة
# ==========================================
st.markdown("<h1 style='text-align: center;'>بوابة زمالة الخليج - تسجيل الحضور</h1>", unsafe_allow_html=True)

# استدعاء اللوحة الموحدة (Option A) التي تدمج الساعات والأعلام والأوقات بكل سلاسة
render_unified_dashboard(
    sun_open_dt,
    sun_close_dt,
    wed_open_dt,
    wed_close_dt,
    next_meeting_day_name,
    next_meeting_open_dt.strftime('%Y-%m-%d'),
    REFERENCE_CITIES,
    any_dst_change_detected
)

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
    النظام مبرمج آلياً ولا يقبل الاستثناءات، احتراماً لوقت المجموعة *(المواعيد الأساسية بتوقيت مكة المكرمة/بغداد، وتظهر محولة تلقائياً لمدينتك في لوحة المواعيد بالأعلى)*:
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

if gate_status == "CLOSED":
    st.warning("⛔ عذراً، تسجيل الحضور مغلق حالياً.")
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

user_email = st.text_input("أدخل البريد الإلكتروني المسجل:", value=st.session_state.get('verified_email', '')).strip().lower()
if 'verified_email' in st.session_state and user_email != st.session_state['verified_email']:
    st.session_state['trap_stage_1_passed'] = False

if 'today_attendees' not in st.session_state:
    st.session_state['today_attendees'] = set()

# ==========================================
# 🎯 منطق التحقق (المرحلة الأولى)
# ==========================================
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
# 🟢 زر الدخول المباشر (المرحلة الثانية)
# ==========================================
if st.session_state.get('trap_stage_1_passed', False):
    st.markdown("---")
    
    if st.session_state.get('is_rejoin', False):
        st.success("✅ مرحباً بعودتك! تم التحقق من تسجيلك المسبق.")
    else:
        st.success("✅ تم تسجيل حضورك بنجاح!")
        
    st.info("💡 اضغط على الزر أدناه للانتقال فوراً إلى قاعة (Zoom).")

    if st.button("🚀 الدخول المباشر للاجتماع", use_container_width=True):
        zoom_link = st.session_state['zoom_link']
        user_email_to_record = st.session_state['verified_email']
        
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
                    
                    safe_execute(lambda: attendance_tab.append_row([baghdad_time, user_email_to_record]))
                    
                    get_todays_attendees.clear()
                    st.session_state['today_attendees'].add(user_email_to_record)
                    st.session_state['is_rejoin'] = True 
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الاتصال بقاعدة البيانات: {e}")
        
        st.markdown(f"""
        <meta http-equiv="refresh" content="0; url={zoom_link}">
        <script>
            window.top.location.href = "{zoom_link}";
        </script>
        """, unsafe_allow_html=True)
        
        st.info("⏳ جاري فتح قاعة Zoom، يرجى الانتظار...")
        st.warning("⚠️ إذا لم يفتح تطبيق زووم تلقائياً الآن، اضغط على الزر أدناه:")
        st.link_button("🔗 اضغط هنا لفتح قاعة Zoom يدوياً", zoom_link, use_container_width=True)
