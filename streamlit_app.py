import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import random

# 1. 網頁基礎設定
st.set_page_config(page_title="👫 我們的帳本", layout="wide", page_icon="💰")

# 2. 讀取 Secrets
try:
    API_URL = st.secrets["API_URL"]
    SHEET_URL = st.secrets["SHEET_URL"]
except:
    st.error("Secrets 設定錯誤，請檢查後台 API_URL 與 SHEET_URL")
    st.stop()

# 3. 讀取資料函數 (強效繞過快取版)
@st.cache_data(ttl=1)
def load_data(url):
    try:
        csv_url = url.split('/edit')[0] + '/export?format=csv&gid=0'
        csv_url += f"&refresh={random.randint(1, 99999)}"
        
        data = pd.read_csv(csv_url)
        
        # 確保欄位正確
        required_cols = ["日期", "類型", "金額", "項目", "分類", "餘額"]
        if data.empty or not all(c in data.columns for c in required_cols):
            return pd.DataFrame(columns=required_cols)
        
        # 處理數值轉換，避免公式計算延遲導致的錯誤
        data['金額'] = pd.to_numeric(data['金額'], errors='coerce').fillna(0)
        data['餘額'] = pd.to_numeric(data['餘額'], errors='coerce').fillna(0)
        return data
    except:
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

df = load_data(SHEET_URL)

# 4. 統計計算
balance = df["餘額"].iloc[-1] if not df.empty else 0
this_month = datetime.now().strftime("%Y-%m")
monthly_exp = df[(df['日期'].astype(str).str.startswith(this_month)) & (df['類型'] == '支出')]['金額'].sum() if not df.empty else 0

# 5. 介面顯示
st.title("👫 我們的帳本 v6.5")
c1, c2 = st.columns(2)
c1.metric("目前總餘額", f"${balance:,.0f}")
c2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

# 6. 新增功能
with st.expander("➕ 新增帳目", expanded=True):
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("選擇日期", datetime.now())
        r_type = st.radio("類型", ["支出", "存款"], horizontal=True)
        cat = st.selectbox("分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他"]) if r_type == "支出" else "(存款)"
        item = st.text_input("項目描述")
        amount = st.number_input("金額", min_value=0, step=1)
        submit = st.form_submit_button("✅ 儲存紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('同步中...'):
            payload = {
                "action": "add",
                "日期": date.strftime("%Y-%m-%d"),
                "類型": r_type, 
                "金額": float(amount), 
                "項目": item, 
                "分類": cat
            }
            try:
                response = requests.post(API_URL, json=payload, timeout=10)
                if "Success" in response.text:
                    st.success("✅ 已儲存！")
                    st.cache_data.clear()
                    time.sleep(1.5) # 給 Google 一點時間計算公式
                    st.rerun()
            except Exception as e:
                st.error(f"連線錯誤：{e}")

st.divider()

# 7. 顯示與刪除功能
st.subheader("📋 最近紀錄")
if not df.empty:
    recent_indices = df.tail(10).index.tolist()
    h = st.columns([2, 1, 1, 2, 2, 1, 1])
    for col, head in zip(h, ["日期", "類型", "金額", "項目", "分類", "餘額", "操作"]):
        col.write(f"**{head}**")

    for i in reversed(recent_indices):
        row = df.loc[i]
        cols = st.columns([2, 1, 1, 2, 2, 1, 1])
        cols[0].write(row['日期'])
        cols[1].write(row['類型'])
        cols[2].write(f"${row['金額']:,.0f}")
        cols[3].write(row['項目'])
        cols[4].write(row['分類'])
        cols[5].write(f"${row['餘額']:,.0f}")
        
        if cols[6].button("🗑️", key=f"del_{i}"):
            with st.spinner("正在刪除..."):
                try:
                    res = requests.post(API_URL, json={"action": "delete", "index": int(i)})
                    if "Delete Success" in res.text:
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                except:
                    st.error("刪除失敗")
else:
    st.info("尚無資料，請新增第一筆。")
