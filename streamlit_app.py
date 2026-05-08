import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import random

# 1. 網頁基礎設定
st.set_page_config(page_title="👫 我們的帳本", layout="wide", page_icon="💰")

# 2. 從 Secrets 讀取網址
try:
    API_URL = st.secrets["API_URL"]
    SHEET_URL = st.secrets["SHEET_URL"]
except Exception:
    st.error("❌ 偵測不到 Secrets 設定，請確認 Streamlit 後台填入 API_URL 與 SHEET_URL")
    st.stop()

# 3. 讀取資料函數 (加強版：徹底解決不更新問題)
@st.cache_data(ttl=1)
def load_data(url):
    try:
        # 將網址轉為 CSV 匯出格式
        csv_url = url.split('/edit')[0] + '/export?format=csv&gid=0'
        # 加入隨機參數，強迫 Google 伺服器交出最新檔案
        csv_url += f"&refresh={random.randint(1, 99999)}"
        
        data = pd.read_csv(csv_url)
        
        # 確保必要的欄位都存在，避免空表報錯
        required_cols = ["日期", "類型", "金額", "項目", "分類", "餘額"]
        if data.empty or not all(c in data.columns for c in required_cols):
            return pd.DataFrame(columns=required_cols)
        return data
    except Exception:
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

# 執行讀取
df = load_data(SHEET_URL)

# 4. 數據統計計算
balance = 0
monthly_exp = 0
if not df.empty:
    df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
    df['餘額'] = pd.to_numeric(df['餘額'], errors='coerce').fillna(0)
    balance = df["餘額"].iloc[-1]
    this_month = datetime.now().strftime("%Y-%m")
    df['日期'] = df['日期'].astype(str)
    monthly_df = df[(df['日期'].str.startswith(this_month)) & (df['類型'] == '支出')]
    monthly_exp = monthly_df['金額'].sum()

# 5. 介面顯示
st.title("👫 我們的帳本 v5.5")

col1, col2 = st.columns(2)
col1.metric("目前總餘額", f"${balance:,.0f}")
col2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

# 6. 輸入表單
with st.expander("➕ 新增帳目", expanded=True):
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("選擇日期", datetime.now())
        r_type = st.radio("交易類型", ["支出", "存款"], horizontal=True)
        
        if r_type == "支出":
            cat = st.selectbox("分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他"])
        else:
            cat = "(存款)"
            
        item = st.text_input("項目描述 (如：晚餐、領薪水)")
        amount = st.number_input("金額", min_value=0, step=1)
        
        submit = st.form_submit_button("✅ 儲存紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('同步中...'):
            new_balance = balance + amount if r_type == "存款" else balance - amount
            payload = {
                "action": "add",
                "日期": date.strftime("%Y-%m-%d"),
                "類型": r_type, 
                "金額": float(amount), 
                "項目": item, 
                "分類": cat, 
                "餘額": float(new_balance)
            }
            try:
                response = requests.post(API_URL, json=payload, timeout=10)
                if "Success" in response.text:
                    st.success("✅ 已存入！")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"連線錯誤：{e}")
    else:
        st.error("⚠️ 請填寫完整內容！")

st.divider()

# 7. 顯示歷史紀錄與刪除功能
st.subheader("📋 最近紀錄 (可刪除最後 10 筆)")
if not df.empty:
    # 取得最後 10 筆資料的索引
    recent_indices = df.tail(10).index.tolist()
    
    # 建立表頭
    h_cols = st.columns([2, 1, 1, 2, 2, 1, 1])
    h_cols[0].write("**日期**")
    h_cols[1].write("**類型**")
    h_cols[2].write("**金額**")
    h_cols[3].write("**項目**")
    h_cols[4].write("**分類**")
    h_cols[5].write("**餘額**")
    h_cols[6].write("**操作**")

    # 倒序顯示，讓最新的在上面
    for i in reversed(recent_indices):
        row = df.loc[i]
        cols = st.columns([2, 1, 1, 2, 2, 1, 1])
        cols[0].write(row['日期'])
        cols[1].write(row['類型'])
        cols[2].write(f"${row['金額']:,.0f}")
        cols[3].write(row['項目'])
        cols[4].write(row['分類'])
        cols[5].write(f"${row['餘額']:,.0f}")
        
        # 刪除按鈕
        if cols[6].button("🗑️", key=f"del_{i}"):
            with st.spinner("正在刪除..."):
                del_payload = {"action": "delete", "index": int(i)}
                del_resp = requests.post(API_URL, json=del_payload)
                if "Delete Success" in del_resp.text:
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("刪除失敗")
else:
    st.info("目前尚無資料。")

# 8. 簡單圖表
if st.checkbox("📊 顯示本月消費分析"):
    if not df.empty and monthly_exp > 0:
        cat_data = monthly_df.groupby('分類')['金額'].sum()
        st.pie_chart(cat_data)
