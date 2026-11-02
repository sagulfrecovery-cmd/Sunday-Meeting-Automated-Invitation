# ------------------------------------------
# 🔴 القسم الثاني: حذف الحساب وإلغاء التسجيل
# ------------------------------------------
with tab_delete:
    st.markdown("### 🗑️ إلغاء التسجيل نهائياً من الزمالة")
    st.markdown("""
    <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; text-align: right; margin-bottom: 20px;">
        <h4 style="color: #856404; margin-top: 0;">⚠️ تنبيه هام وإخلاء مسؤولية</h4>
        <p style="color: #856404; font-size: 15px; margin-bottom: 0; line-height: 1.6;">
            استخدامك لهذا الخيار سيؤدي إلى <b>مسح بريدك الإلكتروني بشكل فوري ونهائي</b> من كافة سجلاتنا (قائمة الأحد وقائمة الأربعاء). ولن تتمكن من دخول أي اجتماعات قادمة.
            إذا أردت العودة للزمالة مستقبلاً، سيتوجب عليك التسجيل من جديد كعضو جديد.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    delete_email = st.text_input("أدخل بريدك الإلكتروني المراد حذفه:", key="delete_email_input").strip().lower()
    confirm_delete = st.checkbox("أؤكد رغبتي الأكيدة في مسح بياناتي نهائياً من سجلات البوابة.", key="confirm_del_chk")
    
    # 🌟 حاوية فارغة مخصصة لإظهار النافذة المنبثقة (Popup) فوق الشاشة
    overlay_placeholder = st.empty()
    
    if st.button("🗑️ حذف حسابي الآن", type="secondary", use_container_width=True, key="execute_delete_btn"):
        if not delete_email:
            st.error("يرجى إدخال البريد الإلكتروني الذي ترغب في حذفه.")
        elif not confirm_delete:
            st.error("يرجى تفعيل خيار التأكيد (وضع علامة صح) لتنفيذ الحذف.")
        else:
            # 1. إظهار شاشة التحميل المنبثقة التي تغلق الشاشة وتمنع النقر
            overlay_placeholder.markdown("""
            <style>
                .blocking-overlay {
                    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                    background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(5px);
                    z-index: 999999; display: flex; flex-direction: column;
                    justify-content: center; align-items: center;
                    direction: rtl; font-family: 'Cairo', sans-serif;
                }
                .spin-loader {
                    border: 6px solid #334155; border-top: 6px solid #ef4444;
                    border-radius: 50%; width: 80px; height: 80px;
                    animation: spin 1s linear infinite; margin-bottom: 25px;
                    box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
                }
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
            
            # 2. تنفيذ كود الحذف في الخلفية
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
                            
                            target_db_del = safe_execute(lambda: client.open_by_key(target_id_del))
                            reg_tab_del = safe_execute(lambda: target_db_del.worksheet("Registration"))
                            
                            emails_col = safe_execute(lambda: reg_tab_del.col_values(2))
                            
                            row_to_delete = None
                            for idx, val in enumerate(emails_col):
                                if val.strip().lower() == delete_email:
                                    row_to_delete = idx + 1 
                                    break
                                    
                            if row_to_delete:
                                safe_execute(lambda: reg_tab_del.delete_rows(row_to_delete))
                                deleted_from_any = True
                        except Exception:
                            continue
                            
                except Exception as loop_e:
                    overlay_placeholder.empty() # إخفاء الشاشة المنبثقة عند الخطأ
                    st.error(f"مشكلة أثناء قراءة السجلات: {loop_e}")
                    
                if deleted_from_any:
                    get_cached_registered_emails.clear()
                    
                    # 3. تغيير الشاشة المنبثقة لتظهر علامة النجاح وتأكيد الحذف
                    overlay_placeholder.markdown("""
                    <style>
                        .blocking-overlay {
                            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                            background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(5px);
                            z-index: 999999; display: flex; flex-direction: column;
                            justify-content: center; align-items: center;
                            direction: rtl; font-family: 'Cairo', sans-serif;
                        }
                        .success-icon {
                            font-size: 80px; margin-bottom: 20px;
                            animation: pop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                        }
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
                    
                    time.sleep(3.5) # إبقاء رسالة النجاح لثلاث ثوانٍ ونصف
                    st.rerun() # إعادة تحميل الصفحة تلقائياً
                else:
                    overlay_placeholder.empty() # إخفاء الشاشة المنبثقة
                    st.info("💡 لم نعثر على هذا البريد الإلكتروني في سجلاتنا. قد يكون غير مسجل أو تم حذفه مسبقاً.")
                    
            except Exception as e:
                overlay_placeholder.empty() # إخفاء الشاشة المنبثقة
                st.error(f"حدث خطأ أثناء محاولة الاتصال بقاعدة البيانات: {e}")
