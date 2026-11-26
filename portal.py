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

# قاموس المدن المتاح في القائمة المنسدلة
ARABIC_CITY_NAMES = {
    "Asia/Baghdad": "بغداد (العراق)",
    "Asia/Riyadh": "الرياض (السعودية)",
    "Asia/Dubai": "دبي (الإمارات)",
    "Asia/Muscat": "مسقط (عُمان)",
    "Asia/Kuwait": "الكويت",
    "Asia/Qatar": "الدوحة (قطر)",
    "Asia/Bahrain": "المنامة (البحرين)",
    "Asia/Amman": "عمّان (الأردن)",
    "Asia/Beirut": "بيروت (لبنان)",
    "Asia/Damascus": "دمشق (سوريا)",
    "Asia/Gaza": "غزة (فلسطين)",
    "Asia/Hebron": "الخليل (فلسطين)",
    "Asia/Jerusalem": "القدس",
    "Asia/Aden": "عدن (اليمن)",
    "Africa/Cairo": "القاهرة (مصر)",
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
    "America/New_York": "نيويورك (الساحل الشرقي لأمريكا)",
    "America/Chicago": "شيكاغو (وسط أمريكا)",
    "America/Los_Angeles": "لوس أنجلوس (الساحل الغربي)",
    "America/Toronto": "تورونتو (كندا)",
    "Australia/Sydney": "سيدني (أستراليا)",
}

# ==========================================
# 🛡️ إعدادات واجهة المستخدم وتنسيق RTL الشامل
# ==========================================
st.set_page_config(page_title="بوابة زمالة الخليج", page_icon="📖", layout="centered")

st.markdown("""
<style>
    /* ضبط الاتجاه من اليمين لليسار لكامل الصفحة والنوافذ المنبثقة */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], div[role="dialog"] {
        direction: rtl !important;
        text-align: right !important;
        -webkit-touch-callout: none !important;
        -webkit-user-select: none !important;
        user-select: none !important;
    }

    div[role="dialog"] header, div[role="dialog"] h2, div[role="dialog"] h3 {
        direction: rtl !important;
        text-align: right !important;
    }

    input, textarea {
        -webkit-touch-callout: default !important;
        -webkit-user-select: auto !important;
        user-select: auto !important;
    }

    /* تقليل الفراغ العلوي الزائد في Streamlit */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* تنسيق التبويبات RTL متوافق مع الوضع الليلي والنهاري */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        gap: 6px !important;
        border-bottom: 2px solid rgba(128, 128, 128, 0.25) !important;
    }
    div[data-testid="stTabs"] button {
        font-size: 14.5px !important;
        font-weight: 800 !important;
        padding: 10px 12px !important;
        color: var(--text-color) !important;
        opacity: 0.72 !important;
        border-radius: 8px 8px 0 0 !important;
        transition: 0.2s !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--text-color) !important;
        opacity: 1 !important;
        border-bottom: 3px solid #2563eb !important;
        background-color: var(--secondary-background-color) !important;
    }

    /* محاذاة مربعات الاختيار (Checkbox) بعرض كامل وتباين واضح في كل الأوضاع */
    div[data-testid="stCheckbox"] {
        width: 100% !important;
    }
    div[data-testid="stCheckbox"] label {
        display: flex !important;
        flex-direction: row !important;
        align-items: flex-start !important;
        gap: 10px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        direction: rtl !important;
        text-align: right !important;
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
        padding: 12px 14px !important;
        border-radius: 8px !important;
        border: 1px solid rgba(128, 128, 128, 0.35) !important;
    }
    div[data-testid="stCheckbox"] label p {
        color: var(--text-color) !important;
        font-size: 14.5px !important;
        line-height: 1.6 !important;
        margin: 0 !important;
    }

    /* محاذاة حقول الإدخال */
    div[data-testid="stTextInput"] label {
        direction: rtl !important;
        text-align: right !important;
        width: 100% !important;
        font-weight: 700 !important;
    }
    div[data-testid="stTextInput"] input {
        direction: ltr !important;
        text-align: right !important;
        font-size: 16px !important;
        padding: 10px 12px !important;
    }

    /* محاذاة التنبيهات والقوائم المطوية */
    div[data-testid="stAlert"], div[data-testid="stExpander"] summary {
        direction: rtl !important;
        text-align: right !important;
    }

    /* الأزرار الرئيسية */
    .stButton button[kind="primary"], .stLinkButton a {
        background-color: #16a34a !important; 
        color: white !important;
        font-size: 17px !important;
        font-weight: bold !important;
        padding: 11px 22px !important;
        border-radius: 8px !important;
        text-align: center !important;
        text-decoration: none !important;
        width: 100% !important; 
        display: block !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.1) !important;
        transition: 0.2s !important;
        border: none !important;
    }
    .stButton button[kind="primary"]:hover, .stLinkButton a:hover {
        background-color: #15803d !important; 
        transform: translateY(-1px) !important;
    }

    /* زر الحذف */
    .stButton button[kind="secondary"] {
        background-color: #dc2626 !important;
        color: white !important;
        font-size: 16px !important;
        font-weight: bold !important;
        padding: 10px 22px !important;
        border-radius: 8px !important;
        width: 100% !important;
        border: none !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.1) !important;
        transition: 0.2s !important;
    }
    .stButton button[kind="secondary"]:hover {
        background-color: #b91c1c !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔧 Helper Functions & Modal Popup
# ==========================================
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


@st.dialog("✅ تم تسجيلك بنجاح — يرجى القراءة والتأكيد")
def show_registration_popup(popup_data):
    """نافذة منبثقة تعرض الموعد الثابت بتوقيت بغداد والرياض وطريقة الدخول وتتطلب التأكيد"""
    popup_html = f"""
<div style="direction: rtl; text-align: right; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Cairo', sans-serif; color: #0f172a;">
<div style="background: #f0fdf4; border: 1px solid #86efac; border-right: 4px solid #16a34a; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; font-size: 13.5px; color: #14532d; line-height: 1.6;">
🎉 تم حفظ بريدك <span style="direction: ltr; display: inline-block; background: #dcfce7; padding: 1px 6px; border-radius: 4px; font-weight: 700; color: #166534;">{popup_data['email']}</span> في قائمة <b>{popup_data['meetingTitle']}</b>.<br>
📩 <b>ملاحظة:</b> ستصلك رسالة دعوة عبر الإيميل قبل موعد الجلسة القادمة (يُرجى تفقد البريد الوارد أو الرسائل غير المرغوب فيها Spam).
</div>
<div style="background: #eff6ff; border: 1px solid #93c5fd; border-right: 4px solid #2563eb; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px;">
<div style="font-size: 14.5px; font-weight: 800; color: #1e3a8a; margin-bottom: 5px;">📅 موعد الاجتماع (كل يوم {popup_data['dayName']} — القادم: {popup_data['nextDate']})</div>
<div style="font-size: 13.5px; color: #1e40af; font-weight: 700; line-height: 1.6;">
🕒 {popup_data['refTimeText']} بتوقيت <b>بغداد والرياض</b>.<br>
⚠️ تُغلق قاعة الاجتماع تماماً بعد <b>{ROOM_LOCK_MINUTES} دقيقة</b> من بداية الجلسة.
</div>
<div style="font-size: 12.5px; color: #334155; margin-top: 6px; border-top: 1px dashed #93c5fd; padding-top: 6px; line-height: 1.5;">
🌍 <b>للمقيمين خارج توقيت بغداد والرياض:</b> يُرجى معرفة الموعد المقابل لمدينتك بنفسك من خلال قائمة <b>«مواعيد الاجتماعات في المدن الأخرى»</b> في أعلى البوابة.
</div>
</div>
<div style="background: #f8fafc; border: 1px solid #cbd5e1; border-right: 4px solid #0f172a; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px;">
<div style="font-size: 14.5px; font-weight: 800; color: #0f172a; margin-bottom: 6px;">🚪 كيف تدخل للاجتماع؟</div>
<ol style="margin: 0; padding-right: 18px; font-size: 13px; color: #334155; line-height: 1.65;">
<li style="margin-bottom: 4px;">عند حلول وقت الفتح، افتح رابط البوابة (من الإيميل أو احفظه في متصفحك).</li>
<li style="margin-bottom: 4px;">اختر التبويب الأول <b>«🚪 دخول الاجتماع»</b> وأدخل بريدك الإلكتروني المسجل.</li>
<li style="margin-bottom: 4px;">ضع علامة (✓) على <b>عهد التعافي</b> واضغط زر الدخول لينقلك مباشرة لقاعة <b>Zoom</b>.</li>
<li><b>تنويه لمستخدمي الموبايل فقط:</b> إذا فتحت البوابة من داخل تطبيق الإيميل على <b>الموبايل</b> ولم يفتح (Zoom)، اضغط على النقاط الثلاث <b>(⋮)</b> بالأعلى واختر <b>«فتح في المتصفح»</b> واستخدم <b>متصفح جوجل كروم (Chrome) حصراً</b>.</li>
</ol>
</div>
</div>
"""
    st.markdown(popup_html, unsafe_allow_html=True)

    if st.button("✅ نعم، قرأت التعليمات وفهمت موعد وطريقة الدخول", type="primary", use_container_width=True, key="ack_reg_popup_btn"):
        st.session_state.pop("reg_popup_data", None)
        st.rerun()


def render_compact_hero_card(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt, next_meeting_label, next_meeting_dt, gate_status):
    """بطاقة حالة مدمجة تعرض توقيت العضو المحلي والعدّاد التنازلي بوضوح دون حجب التبويبات"""
    payload = {
        "sunOpenMs": int(sun_open_dt.timestamp() * 1000),
        "sunCloseMs": int(sun_close_dt.timestamp() * 1000),
        "wedOpenMs": int(wed_open_dt.timestamp() * 1000),
        "wedCloseMs": int(wed_close_dt.timestamp() * 1000),
        "nextMeetingLabel": next_meeting_label,
        "gateStatus": gate_status,
        "cityMap": ARABIC_CITY_NAMES,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    next_meeting_date_str = next_meeting_dt.strftime("%Y-%m-%d")

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Cairo", sans-serif; user-select: none; }}
        html, body {{ margin: 0; padding: 0; background: transparent; direction: rtl; overflow: hidden; }}
        .hero-card {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: white; border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.12); }}
        .hero-top {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
        .hero-title {{ font-size: 15.5px; font-weight: 700; color: #f8fafc; }}
        .status-badge {{ font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px; background-color: #475569; color: #f8fafc; }}
        .status-badge.open {{ background-color: #16a34a; color: #ffffff; animation: pulse 2s infinite; }}
        .status-badge.rejoin {{ background-color: #2563eb; color: #ffffff; }}
        @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45); }} 70% {{ box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }} }}
        .hero-main {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }}
        .local-time-box {{ display: flex; flex-direction: column; gap: 2px; }}
        .local-time-label {{ font-size: 12px; color: #94a3b8; }}
        .local-time-value {{ font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: 0.3px; }}
        .local-city-label {{ font-size: 12.5px; color: #38bdf8; font-weight: 600; }}
        .schedule-info-box {{ display: flex; flex-direction: column; gap: 3px; text-align: left; background: rgba(255,255,255,0.06); padding: 8px 12px; border-radius: 8px; }}
        .schedule-info-label {{ font-size: 11.5px; color: #94a3b8; }}
        .schedule-info-value {{ font-size: 13.5px; font-weight: 700; color: #f8fafc; }}
        .countdown-bar {{ background: rgba(15, 23, 42, 0.65); border: 1px solid #334155; border-radius: 8px; padding: 6px 10px; text-align: center; font-size: 13px; font-weight: 700; color: #fde047; }}
        .countdown-bar.live {{ color: #4ade80; border-color: #166534; background: rgba(22, 101, 52, 0.25); }}
        .smart-alert {{ margin-top: 6px; background-color: #fffbeb; border: 1px solid #fde68a; border-right: 4px solid #f59e0b; color: #92400e; padding: 6px 10px; border-radius: 8px; font-size: 12px; display: none; line-height: 1.5; }}
        @media (max-width: 540px) {{
            .hero-main {{ flex-direction: column; align-items: stretch; }}
            .schedule-info-box {{ text-align: right; }}
        }}
    </style>
    </head>
    <body>
        <div class="hero-card">
            <div class="hero-top">
                <div class="hero-title">📅 القادم: {next_meeting_label} ({next_meeting_date_str})</div>
                <div id="gate-status-badge" class="status-badge">🕒 القاعة مغلقة</div>
            </div>
            <div class="hero-main">
                <div class="local-time-box">
                    <div class="local-time-label">🕒 ساعتك المحلية الآن</div>
                    <div class="local-time-value" id="clk-local">--:--:--</div>
                    <div class="local-city-label" id="user-city-name">جاري تحديد مدينتك...</div>
                </div>
                <div class="schedule-info-box">
                    <div class="schedule-info-label">⏰ مواعيد القاعة بتوقيتك المحلي</div>
                    <div class="schedule-info-value" id="local-open-time">--</div>
                    <div class="schedule-info-value" id="local-close-time">--</div>
                </div>
            </div>
            <div class="countdown-bar" id="countdown-bar">⏳ جاري حساب الوقت المتبقي...</div>
        </div>
        <div class="smart-alert" id="inapp-browser-alert">
            💡 <b>تنبيه لمستخدمي الموبايل فقط:</b> يبدو أنك تفتح البوابة من داخل تطبيق الإيميل؛ لفتح Zoom بسلاسة اضغط على <b>(⋮)</b> بالأعلى واختر <b>«فتح في المتصفح»</b> واستخدم <b>متصفح جوجل كروم (Chrome) حصراً</b>.
        </div>
        <div class="smart-alert" id="local-dst-alert">
            🔔 <b>تنبيه التوقيت:</b> ستشهد مدينتك تغييراً في الساعة (التوقيت الصيفي/الشتوي) قبل موعد الاجتماع.
        </div>

        <script>
            const DATA = {payload_json};
            const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Baghdad";
            const arabicCity = DATA.cityMap[userTz] || userTz;
            document.getElementById("user-city-name").textContent = "📍 " + arabicCity;

            // اكتشاف تلقائي للمتصفح الداخلي لتطبيقات الإيميل على الموبايل فقط
            const ua = navigator.userAgent || "";
            const isMobile = /Android|iPhone|iPad|iPod/i.test(ua);
            const isInApp = /FBAN|FBAV|Instagram|Line|MicroMessenger|wv|WebView|GSA|Outlook|Yahoo/i.test(ua);
            if (isMobile && isInApp) {{
                document.getElementById("inapp-browser-alert").style.display = "block";
            }}

            function formatArabicLiveClock(dateObj, tz) {{
                const parts = new Intl.DateTimeFormat('en-US', {{timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'}}).formatToParts(dateObj);
                let h = 0, m = "00", s = "00";
                for (const p of parts) {{ if (p.type === 'hour') h = parseInt(p.value, 10); if (p.type === 'minute') m = p.value; if (p.type === 'second') s = p.value; }}
                if (h === 24) h = 0; const period = h >= 12 ? "مساءً" : "صباحاً"; let h12 = h % 12; if (h12 === 0) h12 = 12;
                return h12 + ":" + m + ":" + s + " " + period;
            }}

            function formatArabicShortTime(ms, tz) {{
                const d = new Date(ms); const parts = new Intl.DateTimeFormat('en-US', {{timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit'}}).formatToParts(d);
                let h = 0, m = "00";
                for (const p of parts) {{ if (p.type === 'hour') h = parseInt(p.value, 10); if (p.type === 'minute') m = p.value; }}
                if (h === 24) h = 0; const period = h >= 12 ? "مساءً" : "صباحاً"; let h12 = h % 12; if (h12 === 0) h12 = 12;
                return h12 + ":" + m + " " + period;
            }}

            function getTzOffsetMinutes(dateObj, tz) {{
                const utcDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: 'UTC' }}));
                const tzDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: tz }}));
                return Math.round((tzDate - utcDate) / 60000);
            }}

            const isSunday = DATA.nextMeetingLabel === "الأحد";
            const targetOpenMs = isSunday ? DATA.sunOpenMs : DATA.wedOpenMs;
            const targetCloseMs = isSunday ? DATA.sunCloseMs : DATA.wedCloseMs;

            function initHero() {{
                const badge = document.getElementById("gate-status-badge");
                const cdBar = document.getElementById("countdown-bar");

                if (DATA.gateStatus === "OPEN_NEW") {{
                    badge.className = "status-badge open";
                    badge.textContent = "🟢 القاعة مفتوحة الآن";
                    cdBar.className = "countdown-bar live";
                    cdBar.textContent = "⚡ القاعة مفتوحة الآن — أدخل بريدك بالأسفل للدخول";
                }} else if (DATA.gateStatus === "REJOIN_ONLY") {{
                    badge.className = "status-badge rejoin";
                    badge.textContent = "🔵 إعادة دخول فقط";
                    cdBar.className = "countdown-bar live";
                    cdBar.textContent = "🔄 متاح حالياً لإعادة دخول من سجّل حضوره اليوم فقط";
                }} else {{
                    badge.className = "status-badge";
                    badge.textContent = "🕒 القاعة مغلقة (التسجيل المسبق متاح)";
                }}

                document.getElementById("local-open-time").textContent = "🔓 يفتح الدخول: " + formatArabicShortTime(targetOpenMs, userTz);
                document.getElementById("local-close-time").textContent = "🔒 يغلق الدخول: " + formatArabicShortTime(targetCloseMs, userTz);

                const nowOffset = getTzOffsetMinutes(new Date(), userTz);
                const openOffset = getTzOffsetMinutes(new Date(targetOpenMs), userTz);
                if (nowOffset !== openOffset) {{
                    document.getElementById("local-dst-alert").style.display = "block";
                }}
            }}

            function tick() {{
                const now = new Date();
                document.getElementById("clk-local").textContent = formatArabicLiveClock(now, userTz);

                if (DATA.gateStatus === "CLOSED") {{
                    const diffMs = targetOpenMs - now.getTime();
                    const cdBar = document.getElementById("countdown-bar");
                    if (diffMs > 0) {{
                        const totalSec = Math.floor(diffMs / 1000);
                        const days = Math.floor(totalSec / 86400);
                        const hours = Math.floor((totalSec % 86400) / 3600);
                        const mins = Math.floor((totalSec % 3600) / 60);
                        const secs = totalSec % 60;
                        let parts = [];
                        if (days > 0) parts.push(days + " يوم");
                        parts.push(hours + " ساعة");
                        parts.push(mins + " دقيقة");
                        parts.push(secs + " ثانية");
                        cdBar.textContent = "⏳ يفتح الدخول بعد: " + parts.join(" و ");
                    }} else {{
                        cdBar.textContent = "🔄 حان موعد الفتح — قم بتحديث الصفحة";
                    }}
                }}
            }}

            initHero();
            tick();
            setInterval(tick, 1000);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=240, scrolling=False)


def render_world_clocks_selector(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt):
    """قسم الساعات المرجعية والبحث عن المدن الأخرى داخل القائمة المطوية"""
    payload = {
        "sunOpenMs": int(sun_open_dt.timestamp() * 1000),
        "sunCloseMs": int(sun_close_dt.timestamp() * 1000),
        "wedOpenMs": int(wed_open_dt.timestamp() * 1000),
        "wedCloseMs": int(wed_close_dt.timestamp() * 1000),
        "cityMap": ARABIC_CITY_NAMES,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Cairo", sans-serif; user-select: none; }}
        html, body {{ margin: 0; padding: 2px; background: transparent; direction: rtl; overflow: hidden; }}
        .clocks-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }}
        .clock-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px; text-align: center; }}
        .city-title {{ font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 2px; }}
        .city-time {{ font-size: 13.5px; font-weight: 800; color: #0f766e; }}
        .select-label {{ font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 5px; display: block; }}
        .city-select {{ width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid #cbd5e1; font-size: 14px; background-color: #f8fafc; color: #1e293b; outline: none; }}
        .custom-result-card {{ margin-top: 8px; background: #f0fdf4; border: 1px solid #bbf7d0; border-right: 4px solid #22c55e; border-radius: 8px; padding: 8px 12px; display: none; }}
        .custom-card-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #bbf7d0; padding-bottom: 4px; margin-bottom: 5px; }}
        .custom-card-title {{ font-weight: 700; color: #166534; font-size: 13.5px; }}
        .custom-card-time {{ font-weight: 800; color: #15803d; font-size: 14px; }}
        .custom-schedule-row {{ font-size: 13px; color: #14532d; margin-bottom: 2px; }}
        .dst-alert {{ margin-top: 6px; background-color: #fffbeb; border: 1px solid #fde68a; color: #92400e; padding: 5px 8px; border-radius: 6px; font-size: 12px; display: none; }}
        @media (max-width: 540px) {{ .clocks-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    </style>
    </head>
    <body>
        <div class="clocks-grid">
            <div class="clock-card"><div class="city-title">🇮🇶 بغداد</div><div class="city-time" id="clk-baghdad">--:--:--</div></div>
            <div class="clock-card"><div class="city-title">🇸🇦 الرياض</div><div class="city-time" id="clk-riyadh">--:--:--</div></div>
            <div class="clock-card"><div class="city-title">🇦🇪 دبي</div><div class="city-time" id="clk-dubai">--:--:--</div></div>
            <div class="clock-card"><div class="city-title">🇪🇬 القاهرة</div><div class="city-time" id="clk-cairo">--:--:--</div></div>
        </div>
        <label class="select-label" for="custom-city-select">اختر مدينة لمعرفة مواعيد الأسبوع كاملة:</label>
        <select id="custom-city-select" class="city-select" onchange="updateCustomCityCard()">
            <option value="">-- اختر المدينة / المنطقة --</option>
        </select>
        <div id="custom-result-card" class="custom-result-card">
            <div class="custom-card-header">
                <div class="custom-card-title" id="custom-card-title-text">المدينة</div>
                <div class="custom-card-time" id="clk-custom">--:--:--</div>
            </div>
            <div class="custom-schedule-row">🔹 <b>الأحد:</b> <span id="custom-sun-times">--</span></div>
            <div class="custom-schedule-row">🔹 <b>الأربعاء:</b> <span id="custom-wed-times">--</span></div>
            <div class="dst-alert" id="custom-dst-alert">🔔 ستشهد هذه المدينة تغييراً في التوقيت الصيفي/الشتوي قبل الاجتماع.</div>
        </div>

        <script>
            const DATA = {payload_json};
            const selectEl = document.getElementById("custom-city-select");
            for (const [tz, name] of Object.entries(DATA.cityMap)) {{
                const opt = document.createElement("option"); opt.value = tz; opt.textContent = name; selectEl.appendChild(opt);
            }}
            function formatArabicLiveClock(dateObj, tz) {{
                const parts = new Intl.DateTimeFormat('en-US', {{timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'}}).formatToParts(dateObj);
                let h = 0, m = "00", s = "00";
                for (const p of parts) {{ if (p.type === 'hour') h = parseInt(p.value, 10); if (p.type === 'minute') m = p.value; if (p.type === 'second') s = p.value; }}
                if (h === 24) h = 0; const period = h >= 12 ? "مساءً" : "صباحاً"; let h12 = h % 12; if (h12 === 0) h12 = 12;
                return h12 + ":" + m + ":" + s + " " + period;
            }}
            function formatArabicShortTime(ms, tz) {{
                const d = new Date(ms); const parts = new Intl.DateTimeFormat('en-US', {{timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit'}}).formatToParts(d);
                let h = 0, m = "00";
                for (const p of parts) {{ if (p.type === 'hour') h = parseInt(p.value, 10); if (p.type === 'minute') m = p.value; }}
                if (h === 24) h = 0; const period = h >= 12 ? "مساءً" : "صباحاً"; let h12 = h % 12; if (h12 === 0) h12 = 12;
                return h12 + ":" + m + " " + period;
            }}
            function getTzOffsetMinutes(dateObj, tz) {{
                const utcDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: 'UTC' }}));
                const tzDate = new Date(dateObj.toLocaleString('en-US', {{ timeZone: tz }}));
                return Math.round((tzDate - utcDate) / 60000);
            }}
            function updateCustomCityCard() {{
                const selectedTz = selectEl.value; const card = document.getElementById("custom-result-card");
                if (!selectedTz) {{ card.style.display = "none"; return; }}
                card.style.display = "block";
                document.getElementById("custom-card-title-text").textContent = "📍 " + DATA.cityMap[selectedTz];
                document.getElementById("custom-sun-times").textContent = "من " + formatArabicShortTime(DATA.sunOpenMs, selectedTz) + " حتى " + formatArabicShortTime(DATA.sunCloseMs, selectedTz);
                document.getElementById("custom-wed-times").textContent = "من " + formatArabicShortTime(DATA.wedOpenMs, selectedTz) + " حتى " + formatArabicShortTime(DATA.wedCloseMs, selectedTz);
                const nowOffset = getTzOffsetMinutes(new Date(), selectedTz);
                const sunOffset = getTzOffsetMinutes(new Date(DATA.sunOpenMs), selectedTz);
                const wedOffset = getTzOffsetMinutes(new Date(DATA.wedOpenMs), selectedTz);
                document.getElementById("custom-dst-alert").style.display = (nowOffset !== sunOffset || nowOffset !== wedOffset) ? "block" : "none";
                document.getElementById("clk-custom").textContent = formatArabicLiveClock(new Date(), selectedTz);
            }}
            function tickClocks() {{
                const now = new Date();
                document.getElementById("clk-baghdad").textContent = formatArabicLiveClock(now, "Asia/Baghdad");
                document.getElementById("clk-riyadh").textContent = formatArabicLiveClock(now, "Asia/Riyadh");
                document.getElementById("clk-dubai").textContent = formatArabicLiveClock(now, "Asia/Dubai");
                document.getElementById("clk-cairo").textContent = formatArabicLiveClock(now, "Africa/Cairo");
                if (selectEl.value) {{ document.getElementById("clk-custom").textContent = formatArabicLiveClock(now, selectEl.value); }}
            }}
            tickClocks();
            setInterval(tickClocks, 1000);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=255, scrolling=False)


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
    if reg_df.empty or reg_df.shape[1] < 2:
        return []
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()


def get_live_registered_emails(target_sheet_id):
    client = get_google_client()
    target_db = safe_execute(lambda: client.open_by_key(target_sheet_id))
    reg_tab = safe_execute(lambda: target_db.worksheet("Registration"))
    records = safe_execute(lambda: reg_tab.get_all_records())
    reg_df = pd.DataFrame(records)
    if reg_df.empty or reg_df.shape[1] < 2:
        return []
    return reg_df.iloc[:, 1].astype(str).str.lower().str.strip().tolist()


def get_latest_sunday_removal(sun_db, email_to_check):
    """إرجاع أحدث تاريخ حذف للعضو من تبويب Removal Log في شيت الأحد (أو None)"""
    try:
        log_tab = safe_execute(lambda: sun_db.worksheet("Removal Log"))
        rows = safe_execute(lambda: log_tab.get_all_values())
        if not rows or len(rows) < 2:
            return None
        latest_dt = None
        for row in rows[1:]:
            if len(row) >= 2 and str(row[1]).strip().lower() == email_to_check:
                ts = pd.to_datetime(str(row[0]).strip(), errors="coerce")
                if pd.notna(ts):
                    ts_naive = ts.to_pydatetime().replace(tzinfo=None)
                    if latest_dt is None or ts_naive > latest_dt:
                        latest_dt = ts_naive
        return latest_dt
    except gspread.exceptions.WorksheetNotFound:
        return None
    except Exception:
        return None


def log_sunday_self_removal(sun_db, deleted_email, baghdad_tz):
    """تسجيل الحذف الذاتي فوراً في تبويب Removal Log بشيت الأحد لمنع الالتفاف خلال فترة الـ 5 دقائق"""
    try:
        try:
            log_tab = safe_execute(lambda: sun_db.worksheet("Removal Log"))
        except gspread.exceptions.WorksheetNotFound:
            log_tab = safe_execute(lambda: sun_db.add_worksheet(title="Removal Log", rows=1000, cols=3))
            safe_execute(lambda: log_tab.update("A1:C1", [["Timestamp", "Email Address", "Source"]]))

        baghdad_ts = datetime.now(baghdad_tz).strftime("%Y-%m-%d %H:%M:%S")
        safe_execute(lambda: log_tab.insert_row(
            [baghdad_ts, deleted_email, "Streamlit Self-Delete"],
            index=2,
            value_input_option="RAW"
        ))
    except Exception:
        pass


# ==========================================
# ⏰ تحديد حالة البوابة
# ==========================================
baghdad_tz = pytz.timezone("Asia/Baghdad")
now = datetime.now(baghdad_tz)
today_date_str = now.strftime("%Y-%m-%d")
weekday = now.weekday()
now_time = now.time()

sun_open_dt, sun_close_dt, sun_end_dt = get_next_meeting_window(now, 6, SUN_OPEN_HOUR, SUN_OPEN_MIN, SUN_CLOSE_HOUR, SUN_CLOSE_MIN, SUN_END_HOUR, SUN_END_MIN)
wed_open_dt, wed_close_dt, wed_end_dt = get_next_meeting_window(now, 2, WED_OPEN_HOUR, WED_OPEN_MIN, WED_CLOSE_HOUR, WED_CLOSE_MIN, WED_END_HOUR, WED_END_MIN)

if sun_open_dt <= wed_open_dt:
    next_meeting_day_name = "الأحد"
    next_meeting_open_dt = sun_open_dt
else:
    next_meeting_day_name = "الأربعاء"
    next_meeting_open_dt = wed_open_dt

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
# 🔔 إظهار النافذة المنبثقة بعد التسجيل (إن وجدت)
# ==========================================
if "reg_popup_data" in st.session_state and st.session_state["reg_popup_data"]:
    show_registration_popup(st.session_state["reg_popup_data"])

# ==========================================
# 📖 العنوان وبطاقة الوقت المدمجة
# ==========================================
st.markdown("<h2 style='text-align: center; margin-bottom: 10px;'>📖 بوابة زمالة الخليج</h2>", unsafe_allow_html=True)

render_compact_hero_card(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt, next_meeting_day_name, next_meeting_open_dt, gate_status)

with st.expander("🌍 مواعيد الاجتماعات في المدن الأخرى (بغداد، الرياض، دبي، القاهرة، وغيرها)", expanded=False):
    render_world_clocks_selector(sun_open_dt, sun_close_dt, wed_open_dt, wed_close_dt)

# ==========================================
# 🔘 نظام التبويبات الثلاثة الرئيسية (مرتبة من اليمين لليسار)
# ==========================================
tab_join, tab_register_wednesday, tab_register_sunday = st.tabs([
    "🚪 دخول الاجتماع", 
    "📝 التسجيل للأربعاء (المفتوح)", 
    "🔒 التسجيل للأحد (المغلق)"
])

# ------------------------------------------
# 🟢 القسم الأول: دخول الاجتماع
# ------------------------------------------
with tab_join:
    if gate_status == "CLOSED":
        st.info("🕒 **قاعة الاجتماع مغلقة حالياً.** يُفتح الدخول قبل موعد الاجتماع مباشرة كما هو موضح في العدّاد بالأعلى.\n\nإذا لم تكن مسجلاً بعد، يمكنك التسجيل الآن من تبويب **«التسجيل للأربعاء (المفتوح)»**.")
    else:
        data_loaded_successfully = False
        try:
            meetings_data = get_meetings_data()
            available_meetings = [str(x).strip() for x in meetings_data['Meeting Day'].tolist()]
            data_loaded_successfully = True
        except Exception as e:
            st.error(f"خطأ أثناء جلب البيانات: {e}")
            
        if data_loaded_successfully:
            selected_meeting = "الأحد" if weekday == 6 else "الأربعاء"
            if is_testing:
                selected_meeting = st.radio("اختر الاجتماع (وضع الاختبار):", options=["الأحد", "الأربعاء"], horizontal=True, key="test_radio")
                
            if selected_meeting not in available_meetings:
                st.error(f"⚠️ لم يتم العثور على إعدادات اجتماع **{selected_meeting}**.")
            else:
                if gate_status == "REJOIN_ONLY":
                    st.warning(f"⏳ **اجتماع {selected_meeting} (إعادة دخول فقط):** انتهت فترة التسجيل الأولى؛ البوابة متاحة الآن فقط لمن أثبت حضوره اليوم وانقطع اتصاله.")
                else:
                    st.markdown(f"""
                    <div style="background-color: #fef2f2; padding: 12px 15px; border-radius: 8px; border-right: 4px solid #dc2626; margin-bottom: 14px;">
                        <div style="color: #991b1b; font-weight: 800; font-size: 15px;">
                            📌 اجتماع اليوم: {selected_meeting} &nbsp;|&nbsp; ⚠️ تُغلق القاعة تماماً بعد {ROOM_LOCK_MINUTES} دقيقة من البداية
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                user_email = st.text_input("البريد الإلكتروني المسجل:", placeholder="example@email.com", value=st.session_state.get('verified_email', ''), key="join_email_input").strip().lower()
                
                if 'verified_email' in st.session_state and user_email != st.session_state['verified_email']:
                    st.session_state['trap_stage_1_passed'] = False
                    
                if 'today_attendees' not in st.session_state:
                    st.session_state['today_attendees'] = set()
                    
                if not st.session_state.get('trap_stage_1_passed', False):
                    if gate_status == "OPEN_NEW":
                        pledge = st.checkbox("🤝 أتعهد بصدق وأمانة أمام نفسي وتجاه زمالتي، أنني أسجل الآن بنية الحضور الفعلي للاجتماع في وقته المحدد.", key="pledge_chk")
                        btn_text = "تسجيل الحضور والانتقال للقاعة"
                    else:
                        pledge = True
                        btn_text = "التحقق والعودة للاجتماع (Re-join)"
                        
                    if pledge:
                        if st.button(btn_text, type="primary", use_container_width=True, key="verify_btn"):
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
                                                    st.error("❌ بريدك الإلكتروني غير مسجل في قائمة الأربعاء. يرجى التسجيل أولاً من تبويب «التسجيل للأربعاء (المفتوح)».")
                                                else:
                                                    st.error("❌ بريدك الإلكتروني غير مسجل في قائمة الأحد. يرجى التحقق من أهليتك في تبويب «التسجيل للأحد (المغلق)».")
                                                    
                                    except Exception as e:
                                        st.error(f"حدث خطأ: {e}")
                    else:
                        st.caption("💡 ضع علامة (✓) على التعهد أعلاه لتفعيل زر الدخول.")
                        
                if st.session_state.get('trap_stage_1_passed', False):
                    st.markdown("---")
                    if st.session_state.get('is_rejoin', False):
                        st.success("✅ مرحباً بعودتك! تم التحقق من تسجيلك المسبق.")
                    else:
                        st.success("✅ تم التحقق بنجاح! اضغط الزر الأخضر للدخول إلى قاعة (Zoom):")
                    
                    if st.button("🚀 الدخول المباشر لقاعة Zoom", type="primary", use_container_width=True, key="direct_entry_btn"):
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
                                        
                                    safe_execute(lambda: attendance_tab.insert_row([baghdad_time, user_email_to_record], index=2))
                                    
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
                        st.link_button("🔗 اضغط هنا إذا لم يفتح Zoom تلقائياً", zoom_link, use_container_width=True)
                        st.caption("💡 ملاحظة لمستخدمي الموبايل فقط: إذا فتحت البوابة من داخل تطبيق الإيميل ولم يفتح Zoom تلقائياً، اضغط (⋮) بالأعلى واختر «فتح في المتصفح» واستخدم متصفح جوجل كروم (Chrome) حصراً.")

    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
    with st.expander("📖 دليل الاستخدام والقواعد التنظيمية (اضغط للقراءة)", expanded=False):
        st.markdown("""
        **الإخوة والأخوات، أعضاء وضيوف زمالة الخليج، تحية طيبة وبعد..**
        
        لضمان بيئة آمنة للتعافي، وحرصاً منا على احترام وقت الجميع وحماية اجتماعاتنا، نضع بين أيديكم دليل استخدام "البوابة الآلية".
        صُمم هذا النظام ليحمي خصوصيتنا التامة؛ فنحن لا نطلب ولا نحفظ أي أسماء أو بيانات شخصية، فقط **"بريدك الإلكتروني"** كمعرف وحيد لك.
        
        ### 📝 خطوات الدخول:
        * **الرابط:** ادخل عبر الرابط المُرسل إلى بريدك الإلكتروني.
        * **البريد الإلكتروني:** اكتب إيميلك المسجل لدينا بدقة.
        * **عهد التعافي:** يُشترط قراءة التعهد بصدق نية الحضور الفعلي.
        * **الدخول المباشر:** بعد الضغط على "تسجيل الحضور"، سيظهر لك زر أخضر ينقلك مباشرة لقاعة (Zoom).
        
        ### 🛑 الأمانة في الحضور (تنويه هام جداً):
        نود التوضيح أن منصة (Zoom) تقوم تلقائياً بحفظ سجل دقيق بأسماء جميع الحاضرين ووقت دخولهم؛ لذا فإن آلية مطابقة من **"سجّل في البوابة"** مع من **"تواجد فعلياً في القاعة"** هي عملية بسيطة لدينا. نرجو الحرص على التسجيل فقط عندما تكون مستعداً للدخول الفعلي.
        
        ### ⏰ أوقات البوابة (الالتزام بالوقت):
        النظام مبرمج آلياً ولا يقبل الاستثناءات *(المواعيد تظهر محولة تلقائياً لمدينتك في لوحة الأوقات بالأعلى)*:
        * **تنبيه حازم:** تُغلق القاعة تماماً بعد 20 دقيقة من البداية. الدخول المبكر يعكس التزامنا الجاد بتعافينا.
        
        ### 🔄 ميزة إعادة الدخول (عند انقطاع الاتصال):
        إذا انقطع عندك الإنترنت، افتح البوابة مرة أخرى وأدخل إيميلك. سيعرف النظام أنك "أثبت حضورك مسبقاً"، وسيعطيك الرابط فوراً.
        
        ### 🛠 حماية المجموعة:
        يعمل النظام آلياً في الخلفية لحماية الزمالة عبر إيقاف الدعوات للمنقطعين ومسح الإيميلات الوهمية.
        
        > **وُجد هذا النظام لتطبيق المبادئ قبل الشخصيات، ولحماية قاعاتنا من أي فوضى.**
        """)

# ------------------------------------------
# 🟢 القسم الثاني: التسجيل لاجتماع الأربعاء (المفتوح)
# ------------------------------------------
with tab_register_wednesday:
    st.markdown("#### 📝 التسجيل المسبق لاجتماع الأربعاء (المفتوح)")
    
    is_active_meeting_time = (gate_status != "CLOSED")
    
    if is_active_meeting_time:
        st.warning("⛔ **خدمة التسجيل متوقفة مؤقتاً أثناء انعقاد الاجتماع.** يرجى العودة للتسجيل بعد انتهاء الجلسة.")
    else:
        st.info("💡 **نقطة البداية للجميع:** اجتماع الأربعاء مفتوح لكل من لديه الرغبة في التعافي. تسجيلك هنا يتيح لك حضور الأربعاء والبدء ببناء رصيد حضورك.")
        
        new_wed_email = st.text_input("أدخل بريدك الإلكتروني للتسجيل:", placeholder="example@email.com", key="reg_wed_input").strip().lower()
        
        if 'wed_ready_to_pledge' not in st.session_state:
            st.session_state['wed_ready_to_pledge'] = False
        if 'wed_checked_email' not in st.session_state:
            st.session_state['wed_checked_email'] = ""

        if new_wed_email != st.session_state['wed_checked_email']:
            st.session_state['wed_ready_to_pledge'] = False

        if not st.session_state['wed_ready_to_pledge']:
            if st.button("🔍 الخطوة 1: التحقق من البريد", type="primary", use_container_width=True, key="btn_check_wed"):
                if not new_wed_email:
                    st.warning("يرجى إدخال البريد الإلكتروني أولاً.")
                else:
                    with st.spinner("جاري التحقق من السجلات..."):
                        try:
                            client = get_google_client()
                            meetings_data_all = get_meetings_data()
                            wed_info = meetings_data_all[meetings_data_all['Meeting Day'] == "الأربعاء"].iloc[0]
                            wed_sheet_id = str(wed_info['Target Sheet ID']).strip()
                            
                            wed_db = safe_execute(lambda: client.open_by_key(wed_sheet_id))
                            wed_reg_tab = safe_execute(lambda: wed_db.worksheet("Registration"))
                            wed_emails = safe_execute(lambda: wed_reg_tab.col_values(2))
                            wed_emails_clean = [str(e).strip().lower() for e in wed_emails[1:]]
                            
                            if new_wed_email in wed_emails_clean:
                                st.success("✅ أنت مسجل مسبقاً في اجتماع الأربعاء! يمكنك الدخول مباشرة وقت الاجتماع من تبويب «دخول الاجتماع».")
                            else:
                                st.session_state['wed_ready_to_pledge'] = True
                                st.session_state['wed_checked_email'] = new_wed_email
                                st.rerun() 
                        except Exception as e:
                            st.error(f"خطأ أثناء الاتصال بقاعدة البيانات: {e}")

        if st.session_state['wed_ready_to_pledge']:
            st.success("✅ بريدك الإلكتروني متاح للتسجيل. يرجى تأكيد التعهد لإتمام التسجيل:")
            
            pledge_wed = st.checkbox("🤝 أتعهد إني بالغ قانونيا حسب قوانين بلد الإقامة وأتعهد بصدق وأمانة تجاه نفسي وتجاه الزمالة، أنني أسجل اليوم بنية الحضور الفعلي للتعافي.", key="pledge_wed_chk")
            
            if st.button("✅ الخطوة 2: تأكيد التسجيل النهائي", type="primary", use_container_width=True, key="btn_confirm_wed"):
                if not pledge_wed:
                    st.caption("💡 ضع علامة (✓) على التعهد أعلاه لتفعيل زر التسجيل.")
                else:
                    with st.spinner("جاري إضافتك لقائمة اجتماع الأربعاء..."):
                        try:
                            client = get_google_client()
                            meetings_data_all = get_meetings_data()
                            wed_info = meetings_data_all[meetings_data_all['Meeting Day'] == "الأربعاء"].iloc[0]
                            wed_sheet_id = str(wed_info['Target Sheet ID']).strip()
                            
                            wed_db = safe_execute(lambda: client.open_by_key(wed_sheet_id))
                            wed_reg_tab = safe_execute(lambda: wed_db.worksheet("Registration"))
                            
                            now_bg = datetime.now(baghdad_tz)
                            baghdad_time = f"{now_bg.month}/{now_bg.day}/{now_bg.year} {now_bg.hour}:{now_bg.minute:02d}:{now_bg.second:02d}"
                            registered_email = st.session_state['wed_checked_email']
                            
                            safe_execute(lambda: wed_reg_tab.insert_row(
                                [baghdad_time, registered_email, "أتعهد إني بالغ قانونيا حسب قوانين بلد الإقامة", 0],
                                index=2,
                                value_input_option="USER_ENTERED"
                            ))
                            
                            get_cached_registered_emails.clear()
                            
                            st.session_state['wed_ready_to_pledge'] = False
                            st.session_state['wed_checked_email'] = ""
                            st.session_state['reg_popup_data'] = {
                                "meetingTitle": "اجتماع الأربعاء (المفتوح)",
                                "dayName": "الأربعاء",
                                "nextDate": wed_open_dt.strftime("%Y-%m-%d"),
                                "email": registered_email,
                                "refTimeText": "تفتح البوابة من 8:15 مساءً حتى 8:50 مساءً (يبدأ الاجتماع الساعة 8:30 مساءً)",
                            }
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"خطأ أثناء إضافة البيانات: {e}")

# ------------------------------------------
# 🟢 القسم الثالث: التسجيل لاجتماع الأحد (المغلق)
# ------------------------------------------
with tab_register_sunday:
    st.markdown("#### 🔒 التسجيل المسبق لاجتماع الأحد (المغلق)")
    
    is_active_meeting_time = (gate_status != "CLOSED")
    
    if is_active_meeting_time:
        st.warning("⛔ **خدمة فحص الأهلية والتسجيل متوقفة مؤقتاً أثناء انعقاد الاجتماع.** يرجى العودة بعد انتهاء الجلسة.")
    else:
        st.info("💡 **شروط الانضمام لاجتماع الأحد:** أن تكون مسجلاً في اجتماع الأربعاء وحاضراً لـ **4 اجتماعات أربعاء** خلال آخر 3 أشهر *(وفي حال إلغاء تسجيل سابق من الأحد، تُحتسب الجلسات بعد تاريخ الإلغاء فقط)*.")
        
        new_reg_email = st.text_input("أدخل بريدك الإلكتروني للفحص والتسجيل:", placeholder="example@email.com", key="reg_sun_input").strip().lower()
        
        if 'sun_eligibility_passed' not in st.session_state:
            st.session_state['sun_eligibility_passed'] = False
        if 'checked_email' not in st.session_state:
            st.session_state['checked_email'] = ""

        if new_reg_email != st.session_state['checked_email']:
            st.session_state['sun_eligibility_passed'] = False

        if not st.session_state['sun_eligibility_passed']:
            if st.button("🔍 الخطوة 1: فحص رصيد الحضور", type="primary", use_container_width=True, key="btn_check_sun"):
                if not new_reg_email:
                    st.warning("يرجى إدخال البريد الإلكتروني أولاً.")
                else:
                    with st.spinner("جاري فحص سجلات حضورك..."):
                        try:
                            client = get_google_client()
                            meetings_data_all = get_meetings_data()
                            sun_info = meetings_data_all[meetings_data_all['Meeting Day'] == "الأحد"].iloc[0]
                            sun_sheet_id = str(sun_info['Target Sheet ID']).strip()
                            
                            sun_db = safe_execute(lambda: client.open_by_key(sun_sheet_id))
                            sun_reg_tab = safe_execute(lambda: sun_db.worksheet("Registration"))
                            sun_emails = safe_execute(lambda: sun_reg_tab.col_values(2))
                            sun_emails_clean = [str(e).strip().lower() for e in sun_emails[1:]]
                            
                            if new_reg_email in sun_emails_clean:
                                st.success("✅ أنت مسجل مسبقاً في اجتماع الأحد! يمكنك الدخول مباشرة وقت الاجتماع من تبويب «دخول الاجتماع».")
                            else:
                                latest_removal_dt = get_latest_sunday_removal(sun_db, new_reg_email)

                                wed_info = meetings_data_all[meetings_data_all['Meeting Day'] == "الأربعاء"].iloc[0]
                                wed_sheet_id = str(wed_info['Target Sheet ID']).strip()
                                wed_db = safe_execute(lambda: client.open_by_key(wed_sheet_id))

                                wed_reg_tab = safe_execute(lambda: wed_db.worksheet("Registration"))
                                wed_reg_emails = safe_execute(lambda: wed_reg_tab.col_values(2))
                                wed_reg_clean = [str(e).strip().lower() for e in wed_reg_emails[1:]]

                                if new_reg_email not in wed_reg_clean:
                                    st.error("❌ يجب أن تكون مسجلاً في قائمة اجتماع الأربعاء أولاً لتتمكن من التسجيل في اجتماع الأحد.")
                                    if latest_removal_dt is not None:
                                        st.warning(f"ℹ️ نظراً لإلغاء تسجيلك السابق من اجتماع الأحد بتاريخ ({latest_removal_dt.strftime('%Y-%m-%d')})، يرجى إعادة التسجيل في تبويب «التسجيل للأربعاء (المفتوح)» أولاً ثم إتمام حضور 4 اجتماعات أربعاء جديدة.")
                                    else:
                                        st.info("💡 يرجى التوجه إلى تبويب «التسجيل للأربعاء (المفتوح)» أولاً، ثم إتمام حضور 4 اجتماعات أربعاء خلال آخر 3 أشهر.")
                                else:
                                    try:
                                        wed_att_tab = safe_execute(lambda: wed_db.worksheet("Attendance"))
                                    except Exception:
                                        wed_att_tab = safe_execute(lambda: wed_db.sheet1)
                                        
                                    wed_records = safe_execute(lambda: wed_att_tab.get_all_records())
                                    wed_df = pd.DataFrame(wed_records)
                                    
                                    if not wed_df.empty and 'Timestamp' in wed_df.columns:
                                        email_col = 'Email' if 'Email' in wed_df.columns else ('Email Address' if 'Email Address' in wed_df.columns else None)
                                        if email_col:
                                            user_att = wed_df[wed_df[email_col].astype(str).str.lower().str.strip() == new_reg_email].copy()
                                            user_att['Timestamp'] = pd.to_datetime(user_att['Timestamp'], errors="coerce")
                                            cutoff_90 = datetime.now(baghdad_tz).replace(tzinfo=None) - timedelta(days=90)

                                            if latest_removal_dt is not None and latest_removal_dt > cutoff_90:
                                                recent_att = user_att[user_att['Timestamp'] > latest_removal_dt]
                                                counted_from_removal = True
                                            else:
                                                recent_att = user_att[user_att['Timestamp'] >= cutoff_90]
                                                counted_from_removal = False
                                            
                                            unique_days_count = recent_att['Timestamp'].dt.date.nunique()
                                            
                                            if unique_days_count >= 4:
                                                st.session_state['sun_eligibility_passed'] = True
                                                st.session_state['checked_email'] = new_reg_email
                                                st.rerun() 
                                            else:
                                                meetings_left = 4 - unique_days_count
                                                st.error(f"⚠️ رصيد حضورك المحتسب حالياً هو ({unique_days_count}) اجتماعات فقط. متبقي لك **{meetings_left}** اجتماعات أربعاء.")
                                                if counted_from_removal:
                                                    st.info(f"ℹ️ نظراً لإلغاء تسجيلك السابق من اجتماع الأحد بتاريخ ({latest_removal_dt.strftime('%Y-%m-%d')})، يتم احتساب اجتماعات الأربعاء التي حضرتها بعد هذا التاريخ فقط.")
                                        else:
                                            st.error("لم نتمكن من تحديد عمود الإيميل في سجلات الأربعاء.")
                                    else:
                                        st.error("لا توجد سجلات حضور كافية في اجتماع الأربعاء حالياً.")
                        except Exception as e:
                            st.error(f"خطأ أثناء الاتصال بقاعدة البيانات: {e}")

        if st.session_state['sun_eligibility_passed']:
            st.success("✅ أثبتت السجلات حضورك لـ 4 اجتماعات. يرجى تأكيد التعهد لإتمام التسجيل:")
            
            pledge_4_meetings = st.checkbox("🤝 أتعهد إني بالغ قانونيا حسب قوانين بلد الإقامة وأتعهد بصدق وأمانة تجاه نفسي وتجاه الزمالة، أنني قد أتممت حضور الـ 4 اجتماعات كاملة من البداية للنهاية.", key="pledge_sun_chk")
            
            if st.button("✅ الخطوة 2: تأكيد التسجيل النهائي", type="primary", use_container_width=True, key="btn_confirm_sun"):
                if not pledge_4_meetings:
                    st.caption("💡 ضع علامة (✓) على التعهد أعلاه لتفعيل زر التسجيل.")
                else:
                    with st.spinner("جاري إضافتك لقائمة اجتماع الأحد..."):
                        try:
                            client = get_google_client()
                            meetings_data_all = get_meetings_data()
                            sun_info = meetings_data_all[meetings_data_all['Meeting Day'] == "الأحد"].iloc[0]
                            sun_sheet_id = str(sun_info['Target Sheet ID']).strip()
                            
                            sun_db = safe_execute(lambda: client.open_by_key(sun_sheet_id))
                            sun_reg_tab = safe_execute(lambda: sun_db.worksheet("Registration"))
                            
                            now_bg = datetime.now(baghdad_tz)
                            baghdad_time = f"{now_bg.month}/{now_bg.day}/{now_bg.year} {now_bg.hour}:{now_bg.minute:02d}:{now_bg.second:02d}"
                            registered_email = st.session_state['checked_email']
                            
                            safe_execute(lambda: sun_reg_tab.insert_row(
                                [baghdad_time, registered_email, "أتعهد إني بالغ قانونيا حسب قوانين بلد الإقامة", 0],
                                index=2,
                                value_input_option="USER_ENTERED"
                            ))
                            
                            get_cached_registered_emails.clear()
                            
                            st.session_state['sun_eligibility_passed'] = False
                            st.session_state['checked_email'] = ""
                            st.session_state['reg_popup_data'] = {
                                "meetingTitle": "اجتماع الأحد (المغلق)",
                                "dayName": "الأحد",
                                "nextDate": sun_open_dt.strftime("%Y-%m-%d"),
                                "email": registered_email,
                                "refTimeText": "تفتح البوابة من 8:45 مساءً حتى 9:20 مساءً (يبدأ الاجتماع الساعة 9:00 مساءً)",
                            }
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"خطأ أثناء إضافة البيانات: {e}")

# ==========================================
# 🔴 تذييل الصفحة: إلغاء التسجيل ومسح الحساب
# ==========================================
st.markdown("---")
with st.expander("⚙️ إلغاء التسجيل ومسح الحساب نهائياً", expanded=False):
    st.markdown("""
    <div style="background-color: #fffbeb; padding: 12px 15px; border-radius: 8px; border-right: 4px solid #f59e0b; text-align: right; margin-bottom: 14px;">
        <div style="color: #92400e; font-size: 14px; line-height: 1.6;">
            <b>⚠️ تنبيه:</b> استخدامك لهذا الخيار سيؤدي إلى <b>مسح بريدك الإلكتروني بشكل فوري ونهائي</b> من كافة سجلاتنا (قائمة الأربعاء وقائمة الأحد)، ولن تتمكن من دخول الاجتماعات القادمة إلا بعد إعادة التسجيل كعضو جديد.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    delete_email = st.text_input("أدخل بريدك الإلكتروني المراد حذفه:", placeholder="example@email.com", key="delete_email_input").strip().lower()
    confirm_delete = st.checkbox("أؤكد رغبتي الأكيدة في مسح بياناتي نهائياً من سجلات البوابة.", key="confirm_del_chk")
    
    overlay_placeholder = st.empty()
    
    if st.button("🗑️ حذف حسابي الآن", type="secondary", use_container_width=True, key="execute_delete_btn"):
        if not delete_email:
            st.error("يرجى إدخال البريد الإلكتروني الذي ترغب في حذفه.")
        elif not confirm_delete:
            st.error("يرجى تفعيل خيار التأكيد (وضع علامة صح) لتنفيذ الحذف.")
        else:
            overlay_placeholder.markdown("""
            <style>
                .blocking-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(5px); z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; direction: rtl; font-family: 'Cairo', sans-serif; }
                .spin-loader { border: 6px solid #334155; border-top: 6px solid #ef4444; border-radius: 50%; width: 80px; height: 80px; animation: spin 1s linear infinite; margin-bottom: 25px; box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                .overlay-title { color: #f8fafc; font-size: 24px; font-weight: 700; margin: 0 0 10px 0; text-align: center; }
                .overlay-subtitle { color: #94a3b8; font-size: 16px; margin: 0; text-align: center; }
            </style>
            <div class="blocking-overlay">
                <div class="spin-loader"></div>
                <h2 class="overlay-title">جاري مسح بياناتك نهائياً...</h2>
                <p class="overlay-subtitle">⏳ يرجى عدم النقر أو إغلاق الصفحة حتى تكتمل العملية</p>
            </div>
            """, unsafe_allow_html=True)
            
            try:
                client = get_google_client()
                deleted_from_any = False
                
                try:
                    meetings_data_del = get_meetings_data()
                    available_meetings_del = [str(x).strip() for x in meetings_data_del['Meeting Day'].tolist()]
                    
                    for meeting_day in available_meetings_del:
                        try:
                            meeting_info_del = meetings_data_del[meetings_data_del['Meeting Day'] == meeting_day].iloc[0]
                            target_id_del = str(meeting_info_del['Target Sheet ID']).strip()
                            
                            target_db_del = safe_execute(lambda tid=target_id_del: client.open_by_key(tid))
                            reg_tab_del = safe_execute(lambda d=target_db_del: d.worksheet("Registration"))
                            
                            emails_col = safe_execute(lambda t=reg_tab_del: t.col_values(2))
                            
                            rows_to_delete = [
                                idx for idx, val in enumerate(emails_col[1:], start=2)
                                if str(val).strip().lower() == delete_email
                            ]
                            
                            for row_num in reversed(rows_to_delete):
                                safe_execute(lambda t=reg_tab_del, r=row_num: t.delete_rows(r))
                                deleted_from_any = True

                            if rows_to_delete and meeting_day == "الأحد":
                                log_sunday_self_removal(target_db_del, delete_email, baghdad_tz)
                        except Exception:
                            continue
                            
                except Exception as loop_e:
                    overlay_placeholder.empty()
                    st.error(f"مشكلة أثناء قراءة السجلات: {loop_e}")
                    
                if deleted_from_any:
                    get_cached_registered_emails.clear()
                    
                    overlay_placeholder.markdown("""
                    <style>
                        .blocking-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(5px); z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; direction: rtl; font-family: 'Cairo', sans-serif; }
                        .success-icon { font-size: 80px; margin-bottom: 20px; animation: pop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
                        @keyframes pop { 0% { transform: scale(0); } 100% { transform: scale(1); } }
                        .overlay-title { color: #22c55e; font-size: 26px; font-weight: 700; margin: 0 0 10px 0; text-align: center; }
                        .overlay-subtitle { color: #f8fafc; font-size: 16px; margin: 0; text-align: center; }
                    </style>
                    <div class="blocking-overlay">
                        <div class="success-icon">✅</div>
                        <h2 class="overlay-title">تمت العملية بنجاح</h2>
                        <p class="overlay-subtitle">تم مسح بريدك الإلكتروني وإلغاء تسجيلك بالكامل.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    time.sleep(3.5)
                    st.rerun()
                else:
                    overlay_placeholder.empty()
                    st.info("💡 لم نعثر على هذا البريد الإلكتروني في سجلاتنا. قد يكون غير مسجل أو تم حذفه مسبقاً.")
                    
            except Exception as e:
                overlay_placeholder.empty()
                st.error(f"حدث خطأ أثناء محاولة الاتصال بقاعدة البيانات: {e}")
