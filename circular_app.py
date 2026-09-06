import io
import os
import json
import base64
import datetime
import pandas as pd
import streamlit as st
from PIL import Image

try:
    from streamlit_drawable_canvas import st_canvas
    HAS_CANVAS = True
except ImportError:
    HAS_CANVAS = False

# -----------------------------------------------------------------------------
# 0. JSON 自動存取 helper 函數 (解決刷新網頁資料消失問題)
# -----------------------------------------------------------------------------
CIRCULARS_FILE = "circulars_data.json"
STAFF_FILE = "staff_data.json"

def save_staff_to_json():
    """儲存教職員名單至 JSON 檔案"""
    if "staff_df" in st.session_state:
        st.session_state.staff_df.to_json(STAFF_FILE, orient="records", force_ascii=False, indent=4)

def load_staff_from_json():
    """從 JSON 載入教職員名單"""
    if os.path.exists(STAFF_FILE):
        try:
            return pd.read_json(STAFF_FILE, dtype={"staff_id": str})
        except Exception:
            pass
    return pd.DataFrame([
        {"staff_id": "001", "name": "張校長", "email": "principal@school.edu.hk"},
        {"staff_id": "002", "name": "李副校長", "email": "v_principal@school.edu.hk"},
        {"staff_id": "003", "name": "陳主任 (教務)", "email": "academic@school.edu.hk"},
        {"staff_id": "004", "name": "林主任 (訓輔)", "email": "discipline@school.edu.hk"},
        {"staff_id": "005", "name": "黃老師", "email": "teacher_wong@school.edu.hk"},
        {"staff_id": "006", "name": "何老師", "email": "teacher_ho@school.edu.hk"},
        {"staff_id": "007", "name": "周老師", "email": "teacher_chow@school.edu.hk"},
    ])

def save_circulars_to_json():
    """儲存所有傳閱單與簽名檔 (圖片轉 Base64) 至 JSON 檔案"""
    if "circulars" not in st.session_state:
        return
    
    data_to_save = {}
    for cid, cinfo in st.session_state.circulars.items():
        signatures_copy = {}
        for sid, sinfo in cinfo.get("signatures", {}).items():
            sig_entry = {
                "status": sinfo.get("status", False),
                "time": sinfo.get("time", "")
            }
            # 將 PIL 圖片轉為 Base64 字串儲存
            if "image" in sinfo and sinfo["image"] is not None:
                buf = io.BytesIO()
                sinfo["image"].save(buf, format="PNG")
                sig_entry["image_b64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
            else:
                sig_entry["image_b64"] = None
                
            signatures_copy[sid] = sig_entry
            
        data_to_save[cid] = {
            "id": cinfo["id"],
            "title": cinfo["title"],
            "description": cinfo["description"],
            "deadline": str(cinfo["deadline"]), # 日期轉字串
            "published_at": cinfo["published_at"],
            "signatures": signatures_copy
        }
        
    with open(CIRCULARS_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

def load_circulars_from_json():
    """從 JSON 載入傳閱單與將 Base64 還原為 PIL 簽名圖檔"""
    if not os.path.exists(CIRCULARS_FILE):
        return {}
    
    try:
        with open(CIRCULARS_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        loaded_circulars = {}
        for cid, cinfo in raw_data.items():
            signatures = {}
            for sid, sinfo in cinfo.get("signatures", {}).items():
                sig_entry = {
                    "status": sinfo.get("status", False),
                    "time": sinfo.get("time", "")
                }
                if sinfo.get("image_b64"):
                    img_bytes = base64.b64decode(sinfo["image_b64"])
                    sig_entry["image"] = Image.open(io.BytesIO(img_bytes))
                else:
                    sig_entry["image"] = None
                signatures[sid] = sig_entry
                
            # 將日期字串還原為 datetime.date
            deadline_val = cinfo.get("deadline")
            if isinstance(deadline_val, str):
                deadline_val = datetime.datetime.strptime(deadline_val, "%Y-%m-%d").date()
                
            loaded_circulars[cid] = {
                "id": cinfo["id"],
                "title": cinfo["title"],
                "description": cinfo["description"],
                "deadline": deadline_val,
                "published_at": cinfo["published_at"],
                "signatures": signatures
            }
        return loaded_circulars
    except Exception as e:
        st.error(f"載入 JSON 歷史紀錄失敗：{e}")
        return {}

# -----------------------------------------------------------------------------
# 1. 頁面配置與高對比 Dropdown 選單 CSS (莫蘭迪高對比配色)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="學校電子傳閱與簽核系統",
    page_icon="🌿",
    layout="wide"
)

# 初始化版面文字設定 (Admin 可自訂)
if "site_config" not in st.session_state:
    st.session_state.site_config = {
        "system_title": "🌿 學校電子傳閱與簽核系統",
        "sidebar_title": "🌿 學校傳閱系統",
        "sign_page_title": "📝 教師電子簽核",
        "sign_instructions": "請選擇您的姓名，詳細閱讀文件說明後，於下方簽名畫布進行手寫電子簽署。",
        "progress_page_title": "📊 傳閱進度看板",
        "admin_title": "🛠️ 行政管理與簽名檔總覽"
    }

cfg = st.session_state.site_config

st.markdown("""
    <style>
    .stApp {
        background-color: #FAF8F5;
        color: #1A1A1A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Noto Sans TC", sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #EFECE6 !important;
        border-right: 1px solid #E2DDD5;
    }
    h1, h2, h3, h4, h5 {
        color: #1F3025 !important;
        font-weight: 700;
    }

    /* 1. 放大 Drop Down 選單標題 (例如：📌 請選擇要簽核的傳閱文件： / 請選擇您的姓名：) */
    .stSelectbox label, div[data-widget="stSelectbox"] label {
        font-size: 1.4rem !important;   /* 字體再放大 */
        font-weight: 800 !important;
        color: #122017 !important;
        background-color: #DDE8DC !important;
        padding: 6px 14px !important;
        border-radius: 6px !important;
        border-left: 6px solid #2E4B38 !important;
        margin-bottom: 10px !important;
        display: inline-block !important;
    }

    /* 2. 放大 Drop Down 選單內容選項 (例如：2627 教師時間表當值核對 / 徐 劍) */
    div[data-baseweb="select"] {
        border-radius: 10px !important;
        border: 2px solid #2E4B38 !important;
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.08) !important;
        min-height: 56px !important;
    }
    div[data-baseweb="select"] * {
        font-size: 1.35rem !important;  /* 選項文字再放大 */
        font-weight: 700 !important;
        color: #101813 !important;      /* 深黑色 */
    }
    ul[data-baseweb="menu"] li {
        font-size: 1.25rem !important;  /* 下拉清單內項目放大 */
        padding: 14px 18px !important;
    }

    /* 3. 改深色與放大：發佈時間與截止日期 (st.caption) */
    [data-testid="stCaptionContainer"], .stCaption {
        color: #1A1A1A !important;      /* 從淺灰改為深黑 */
        font-size: 1.15rem !important;  /* 字體加大 */
        font-weight: 700 !important;
        margin-top: 6px !important;
        margin-bottom: 12px !important;
    }

    /* 4. 改深色與放大：傳閱說明引用區塊 (blockquote) */
    blockquote {
        color: #111111 !important;      /* 高對比深黑色 */
        font-size: 1.25rem !important;  /* 內文放大 */
        font-weight: 600 !important;
        line-height: 1.7 !important;
        background-color: #EAEFEA !important; /* 加深背景底色 */
        border-left: 6px solid #2E4B38 !important;
        padding: 14px 18px !important;
        border-radius: 6px !important;
    }

    .stButton>button {
        background-color: #2E4B38 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 12px 26px !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }
    .stButton>button:hover {
        background-color: #1B3023 !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 初始化 Session State (自動讀取 JSON 檔案)
# -----------------------------------------------------------------------------
if "staff_df" not in st.session_state:
    st.session_state.staff_df = load_staff_from_json()

if "circulars" not in st.session_state:
    st.session_state.circulars = load_circulars_from_json()

# -----------------------------------------------------------------------------
# 3. 側邊欄：權限管控與導覽
# -----------------------------------------------------------------------------
st.sidebar.title(cfg["sidebar_title"])

user_role = st.sidebar.radio("🔑 選擇身份", ["教職員 (Teacher)", "行政管理員 (Admin)"])

is_admin = False
if user_role == "行政管理員 (Admin)":
    admin_pwd = st.sidebar.text_input("輸入 Admin 密碼", type="password", help="預設密碼：admin123")
    if admin_pwd == "jmk1224*":
        is_admin = True
        st.sidebar.success("已解鎖 ADMIN 管理權限")
    else:
        st.sidebar.warning("請輸入密碼以存取管理功能")

if is_admin:
    menu_options = [
        "➕ 發佈新傳閱單",
        "👥 教師名單管理",
        "📝 教師簽核",
        "📊 傳閱進度看板",
        "🛠️ 行政管理與 Excel 匯出",
        "⚙️ 版面文字設定",
        "🔔 催辦提醒與通知管理"
    ]
else:
    menu_options = [
        "📝 教師簽核",
        "📊 傳閱進度看板"
    ]

menu = st.sidebar.selectbox("📌 系統功能選單", menu_options)

st.sidebar.markdown("---")
st.sidebar.caption(f"目前已有 {len(st.session_state.circulars)} 份傳閱單紀錄 (已啟用 JSON 永久儲存)")

# -----------------------------------------------------------------------------
# 頁面 1：發佈新傳閱單 (ADMIN)
# -----------------------------------------------------------------------------
if menu == "➕ 發佈新傳閱單":
    st.title("➕ 發佈新電子傳閱單")
    st.write("設定傳閱文件名稱與截止日期。每次發佈均會建立獨立的新表格，並自動同步至 JSON 檔。")
    
    today = datetime.date.today()
    active_circulars = [
        c_info['title'] for c_id, c_info in st.session_state.circulars.items() 
        if c_info['deadline'] >= today
    ]
    
    if active_circulars:
        st.info(f"💡 目前有 {len(active_circulars)} 份進行中的傳閱單（最新：《{active_circulars[-1]}》）。")
    
    with st.form("publish_form"):
        new_title = st.text_input("📄 文件名稱 / 事由", placeholder="例：【行政傳閱】下學期校委會會議紀錄")
        new_desc = st.text_area("📝 傳閱說明 / 附件摘要", placeholder="請各位老師詳細閱讀，並於視窗內完成電子手寫簽署。")
        new_deadline = st.date_input("📅 簽核截止日期", value=today + datetime.timedelta(days=3))
        
        submit_btn = st.form_submit_button("🚀 發佈新傳閱單")
        
    if submit_btn:
        if not new_title.strip():
            st.error("請輸入文件名稱！")
        else:
            cid = f"CIRC_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.circulars[cid] = {
                "id": cid,
                "title": new_title,
                "description": new_desc,
                "deadline": new_deadline,
                "published_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "signatures": {}
            }
            save_circulars_to_json()  # 💾 寫入 JSON
            st.success(f"🎉 成功發佈《{new_title}》！系統已建立新傳閱表格並永久儲存。")

# -----------------------------------------------------------------------------
# 頁面 2：教師名單管理 (ADMIN)
# -----------------------------------------------------------------------------
elif menu == "👥 教師名單管理":
    st.title("👥 教師名單管理")
    st.write("您可以自由新增、修改、刪除教職員名單，或透過 Excel/CSV 檔進行批量更新。")
    
    tab1, tab2, tab3 = st.tabs(["📋 目前名單檢視", "➕ 單筆增刪/修改", "📤 批次上傳 Excel/CSV"])
    
    with tab1:
        st.dataframe(st.session_state.staff_df, use_container_width=True)
        
    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("新增 / 修改成員")
            s_id = st.text_input("教職編號 (Staff ID)", value="008")
            s_name = st.text_input("教師姓名", value="新老師")
            s_email = st.text_input("電郵地址", value="teacher@school.edu.hk")
            if st.button("💾 儲存 / 更新資料"):
                df = st.session_state.staff_df
                if s_id in df["staff_id"].astype(str).values:
                    df.loc[df["staff_id"].astype(str) == s_id, ["name", "email"]] = [s_name, s_email]
                    st.success(f"已更新編號 {s_id} 的資料！")
                else:
                    new_row = pd.DataFrame([{"staff_id": str(s_id), "name": s_name, "email": s_email}])
                    st.session_state.staff_df = pd.concat([df, new_row], ignore_index=True)
                    st.success(f"已新增成員 {s_name}！")
                save_staff_to_json()  # 💾 寫入 JSON
                st.rerun()
                
        with col_b:
            st.subheader("刪除成員")
            del_name = st.selectbox("選擇要移除的教職員：", st.session_state.staff_df["name"].tolist())
            if st.button("🗑️ 刪除該成員"):
                st.session_state.staff_df = st.session_state.staff_df[st.session_state.staff_df["name"] != del_name]
                save_staff_to_json()  # 💾 寫入 JSON
                st.success(f"已刪除 {del_name}")
                st.rerun()
                
    with tab3:
        uploaded_file = st.file_uploader("上傳 Excel 或 CSV 檔 (需包含 staff_id, name, email 欄位)", type=["xlsx", "csv"])
        if uploaded_file and st.button("📥 匯入並覆蓋名單"):
            try:
                if uploaded_file.name.endswith(".csv"):
                    new_df = pd.read_csv(uploaded_file, dtype={"staff_id": str})
                else:
                    new_df = pd.read_excel(uploaded_file, dtype={"staff_id": str})
                
                required_cols = {"staff_id", "name", "email"}
                if required_cols.issubset(new_df.columns):
                    st.session_state.staff_df = new_df[list(required_cols)]
                    save_staff_to_json()  # 💾 寫入 JSON
                    st.success("教職員名單更新成功！")
                    st.rerun()
                else:
                    st.error(f"格式不符，請確保檔案包含以下欄位：{required_cols}")
            except Exception as e:
                st.error(f"匯入失敗：{e}")

# -----------------------------------------------------------------------------
# 頁面 3：教師電子簽核
# -----------------------------------------------------------------------------
elif menu == "📝 教師簽核":
    st.title(cfg["sign_page_title"])
    st.info(cfg["sign_instructions"])
    
    if not st.session_state.circulars:
        st.info("🍃 目前行政處尚未發佈任何傳閱文件。")
    else:
        c_options = {c_id: c_data["title"] for c_id, c_data in st.session_state.circulars.items()}
        selected_cid = st.selectbox("📌 請選擇要簽核的傳閱文件：", options=list(c_options.keys()), format_func=lambda x: c_options[x])
        
        circular = st.session_state.circulars[selected_cid]
        
        st.subheader(f"{circular['title']}")
        st.caption(f"發佈時間：{circular['published_at']} ｜ 截止日期：{circular['deadline']}")
        st.markdown(f"> {circular['description']}")
        st.markdown("---")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_name = st.selectbox("請選擇您的姓名：", st.session_state.staff_df["name"].tolist())
            staff_row = st.session_state.staff_df[st.session_state.staff_df["name"] == selected_name].iloc[0]
            sid = str(staff_row["staff_id"])
            
            sig_data = circular["signatures"].get(sid, {})
            is_signed = sig_data.get("status", False)
            
            if is_signed:
                st.success(f"✅ **{selected_name}**，您已於 `{sig_data['time']}` 完成電子簽署。")
                if "image" in sig_data and sig_data["image"] is not None:
                    st.image(sig_data["image"], caption="已儲存的手寫簽名記錄", width=220)
            else:
                st.markdown("✍️ **請於下方畫布進行電子手寫簽署：**")
                
                if HAS_CANVAS:
                    canvas_result = st_canvas(
                        fill_color="rgba(255, 255, 255, 0)",
                        stroke_width=2,
                        stroke_color="#000000",
                        background_color="#FFFFFF",
                        height=150,
                        width=350,
                        drawing_mode="freedraw",
                        update_streamlit=True,
                        return_image_data=True,
                        key=f"canvas_{selected_cid}_{sid}"
                    )
                    
                    if st.button("🖊️ 確認送出電子簽署"):
                        if canvas_result is not None and canvas_result.image_data is not None:
                            img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            circular["signatures"][sid] = {
                                "status": True,
                                "time": now_str,
                                "image": img
                            }
                            save_circulars_to_json()  # 💾 寫入 JSON (包含簽名檔 Base64)
                            st.success("🎉 電子簽署完成並已寫入紀錄！")
                            st.rerun()
                else:
                    st.warning("⚠️ 未偵測到 `streamlit-drawable-canvas` 套件，改用一鍵確認簽署：")
                    if st.button("🖊️ 確認完成簽核"):
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        circular["signatures"][sid] = {"status": True, "time": now_str, "image": None}
                        save_circulars_to_json()  # 💾 寫入 JSON
                        st.success("🎉 完成簽核！")
                        st.rerun()

# -----------------------------------------------------------------------------
# 頁面 4：傳閱進度看板 (同事可相互查看進度 + ADMIN 簽名畫廊)
# -----------------------------------------------------------------------------
elif menu == "📊 傳閱進度看板":
    st.title(cfg["progress_page_title"])
    
    if not st.session_state.circulars:
        st.info("🍃 目前無進行中的傳閱文件。")
    else:
        c_options = {c_id: c_data["title"] for c_id, c_data in st.session_state.circulars.items()}
        selected_cid = st.selectbox("📌 檢視傳閱文件進度：", options=list(c_options.keys()), format_func=lambda x: c_options[x])
        circular = st.session_state.circulars[selected_cid]
        
        df = st.session_state.staff_df.copy()
        df["staff_id"] = df["staff_id"].astype(str)
        df["狀態"] = df["staff_id"].apply(
            lambda x: "✅ 已完成" if circular["signatures"].get(x, {}).get("status", False) else "❌ 未完成"
        )
        df["簽核時間"] = df["staff_id"].apply(
            lambda x: circular["signatures"].get(x, {}).get("time", "-")
        )
        
        total = len(df)
        done_cnt = len(df[df["狀態"] == "✅ 已完成"])
        pending_cnt = total - done_cnt
        
        c1, c2, c3 = st.columns(3)
        c1.metric("總人數", f"{total} 人")
        c2.metric("已完成簽核", f"{done_cnt} 人", f"{round(done_cnt/total*100, 1)}%")
        c3.metric("未完成人數", f"{pending_cnt} 人")
        
        st.progress(done_cnt / total)
        st.markdown("---")
        
        tab_list = ["❌ 未完成名單", "✅ 已完成名單"]
        if is_admin:
            tab_list.append("🖼️ ADMIN 簽名檔一目了然總覽")
            
        tabs = st.tabs(tab_list)
        
        with tabs[0]:
            st.dataframe(
                df[df["狀態"] == "❌ 未完成"][["staff_id", "name"]].rename(columns={"staff_id": "教職編號", "name": "姓名"}),
                use_container_width=True
            )
        with tabs[1]:
            st.dataframe(
                df[df["狀態"] == "✅ 已完成"][["staff_id", "name", "簽核時間"]].rename(columns={"staff_id": "教職編號", "name": "姓名"}),
                use_container_width=True
            )
            
      # ADMIN 獨享：圖文並茂快速審視畫廊 + 單獨重置功能
        if is_admin and len(tabs) > 2:
            with tabs[2]:
                st.subheader("🖼️ 所有教職員簽名圖檔一覽")
                cols = st.columns(3)
                for idx, row in df.iterrows():
                    sid = str(row["staff_id"])
                    s_name = row["name"]
                    sig_info = circular["signatures"].get(sid, {})
                    has_sig = sig_info.get("status", False)
                    
                    with cols[idx % 3]:
                        st.markdown(f"**👤 {s_name}** (`{sid}`)")
                        if has_sig:
                            st.caption(f"簽核時間：{sig_info.get('time', '-')}")
                            if "image" in sig_info and sig_info["image"] is not None:
                                st.image(sig_info["image"], width=180)
                            else:
                                st.success("已完成簽核 (無圖檔)")
                            
                            # 🔴 ADMIN 重置按鈕
                            if st.button(f"🔄 重置 {s_name} 的簽核", key=f"reset_{selected_cid}_{sid}"):
                                circular["signatures"].pop(sid, None)  # 刪除該筆簽核紀錄
                                save_circulars_to_json()              # 即時寫入 JSON 儲存
                                st.success(f"已重置 {s_name} 的簽核！該位同事現在可以重新簽署。")
                                st.rerun()
                        else:
                            st.error("❌ 尚未完成簽署")
                        st.markdown("---")

# -----------------------------------------------------------------------------
# 頁面 5：行政管理與 Excel 匯出
# -----------------------------------------------------------------------------
elif menu == "🛠️ 行政管理與 Excel 匯出":
    st.title(cfg["admin_title"])
    
    if not st.session_state.circulars:
        st.info("🍃 目前尚無發佈傳閱文件。")
    else:
        st.subheader("📋 選擇傳閱表格進行檢視與匯出")
        c_options = {c_id: f"{c_data['title']} (發佈時間: {c_data['published_at']})" for c_id, c_data in st.session_state.circulars.items()}
        selected_cid = st.selectbox("選擇表格：", options=list(c_options.keys()), format_func=lambda x: c_options[x])
        
        circular = st.session_state.circulars[selected_cid]
        
        report_df = st.session_state.staff_df.copy()
        report_df["staff_id"] = report_df["staff_id"].astype(str)
        report_df["簽核狀態"] = report_df["staff_id"].apply(
            lambda x: "已完成" if circular["signatures"].get(x, {}).get("status", False) else "未完成"
        )
        report_df["簽核時間"] = report_df["staff_id"].apply(
            lambda x: circular["signatures"].get(x, {}).get("time", "-")
        )
        
        export_df = report_df[["staff_id", "name", "簽核狀態", "簽核時間", "email"]]
        export_df.columns = ["教職員編號", "姓名", "簽核狀態", "簽核時間", "電郵地址"]
        
        st.dataframe(export_df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='傳閱簽核結果')
        buffer.seek(0)
        
        st.download_button(
            label="📥 匯出 Excel 報告 (.xlsx)",
            data=buffer,
            file_name=f"傳閱報告_{circular['title']}_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# -----------------------------------------------------------------------------
# 頁面 6：版面文字與標題自訂設定 (ADMIN)
# -----------------------------------------------------------------------------
elif menu == "⚙️ 版面文字設定":
    st.title("⚙️ ADMIN 自訂全站版面文字")
    st.write("您可以在此修改系統各頁面的標題與引導提示，修改後將即時生效。")
    
    with st.form("custom_text_form"):
        new_sidebar_title = st.text_input("側邊欄系統主標題", value=cfg["sidebar_title"])
        new_sign_title = st.text_input("教師簽核頁面標題", value=cfg["sign_page_title"])
        new_sign_instructions = st.text_area("教師簽核頁面指引文字", value=cfg["sign_instructions"])
        new_progress_title = st.text_input("進度看板頁面標題", value=cfg["progress_page_title"])
        new_admin_title = st.text_input("行政管理頁面標題", value=cfg["admin_title"])
        
        save_cfg_btn = st.form_submit_button("💾 儲存版面設定")
        
    if save_cfg_btn:
        st.session_state.site_config.update({
            "sidebar_title": new_sidebar_title,
            "sign_page_title": new_sign_title,
            "sign_instructions": new_sign_instructions,
            "progress_page_title": new_progress_title,
            "admin_title": new_admin_title
        })
        st.success("🎉 版面文字已更新！")
        st.rerun()

# -----------------------------------------------------------------------------
# 頁面 7：催辦提醒與通知管理
# -----------------------------------------------------------------------------
elif menu == "🔔 催辦提醒與通知管理":
    st.title("🔔 催辦提醒與通知管理")
    
    if not st.session_state.circulars:
        st.info("🍃 目前無進行中的傳閱文件。")
    else:
        c_options = {c_id: c_data["title"] for c_id, c_data in st.session_state.circulars.items()}
        selected_cid = st.selectbox("選擇要催辦的傳閱文件：", options=list(c_options.keys()), format_func=lambda x: c_options[x])
        circular = st.session_state.circulars[selected_cid]
        
        today = datetime.date.today()
        deadline = circular["deadline"]
        days_left = (deadline - today).days
        
        st.write(f"**當前日期：** {today} ｜ **截止日期：** {deadline}")
        
        if days_left <= 3:
            st.warning(f"⚠️ 距離截止日期僅剩 **{days_left} 天**！已觸發前 3 天催辦警示。")
        else:
            st.info(f"💡 距離截止日期還有 **{days_left} 天**。")
            
        st.markdown("---")
        
        pending_list = [
            row for _, row in st.session_state.staff_df.iterrows()
            if not circular["signatures"].get(str(row["staff_id"]), {}).get("status", False)
        ]
        pending_df = pd.DataFrame(pending_list)
        
        col_x, col_y = st.columns(2)
        with col_x:
            st.subheader("💬 通訊群組提醒字條 (Reminder)")
            names_str = "、".join(pending_df["name"].tolist()) if not pending_df.empty else "無"
            
            reminder_text = (
                f"【溫馨提示：請記得完成電子傳閱簽核】\n\n"
                f"各位同工好，以下傳閱文件將於 **{deadline}** 截止：\n"
                f"📄 **文件：** {circular['title']}\n\n"
                f"📌 **尚待簽核同工：**\n{names_str}\n\n"
                f"請未簽核的老師撥冗登入系統點擊簽核，感謝大家的協助！🌿"
            )
            st.text_area("複製提醒字條：", value=reminder_text, height=220)
            
        with col_y:
            st.subheader("📧 Email 催辦")
            if not pending_df.empty:
                st.write("未完成同工：", ", ".join(pending_df["name"].tolist()))
                if st.button("📤 發送催辦電郵"):
                    st.success(f"已發送提醒信件至 {len(pending_df)} 位未完成同工！")
            else:
                st.success("🎉 所有老師皆已完成簽核！")
