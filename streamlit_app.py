import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import random

st.set_page_config(page_title="👫 我們的帳本", layout="wide", page_icon="💰")

try:
    API_URL = st.secrets["API_URL"]
    SHEET_URL = st.secrets["SHEET_URL"]
except:
    st.error("Secrets 設定缺失")
    st.stop()

@st.cache_data(ttl=1)
def load_data(url):
    try:
        # ... 原本的網址轉換 ...
        data = pd.read_csv(csv_url)
        
        if not data.empty:
            # 強制將金額與餘額轉為數字，出錯就變 0
            data['金額'] = pd.to_numeric(data['金額'], errors='coerce').fillna(0)
            data['餘額'] = pd.to_numeric(data['餘額'], errors='coerce').fillna(0)
        return data
    except:
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

df = load_data(SHEET_URL)

# 統計數據
balance = df["餘額"].iloc[-1] if not df.empty else 0
this_month = datetime.now().strftime("%Y-%m")
monthly_exp = df[(df['日期'].astype(str).str.startswith(this_month)) & (df['類型'] == '支出')]['金額'].sum() if not df.empty else 0

st.title("👫 我們的帳本 v6.0")
c1, c2 = st.columns(2)
c1.metric("目前總餘額", f"${balance:,.0f}")
c2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

# 新增功能
with st.expander("➕ 新增帳目", expanded=True):
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("日期", datetime.now())
        r_type = st.radio("類型", ["支出", "存款"], horizontal=True)
        cat = st.selectbox("分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他"]) if r_type == "支出" else "(存款)"
        item = st.text_input("項目描述")
        amount = st.number_input("金額", min_value=0, step=1)
        submit = st.form_submit_button("✅ 儲存紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('同步中...'):
            # 這裡不再傳送 new_balance，讓 Google 自己算
            payload = {
                "action": "add",
                "日期": date.strftime("%Y-%m-%d"),
                "類型": r_type, 
                "金額": float(amount), 
                "項目": item, 
                "分類": cat
            }
            resp = requests.post(API_URL, json=payload)
            if "Success" in resp.text:
                st.success("✅ 已儲存！")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()

st.divider()

# 顯示與刪除
st.subheader("📋 最近紀錄")
if not df.empty:
    recent_indices = df.tail(10).index.tolist()
    h = st.columns([2, 1, 1, 2, 2, 1, 1])
    headers = ["日期", "類型", "金額", "項目", "分類", "餘額", "操作"]
    for col, head in zip(h, headers): col.write(f"**{head}**")

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
                del_payload = {"action": "delete", "index": int(i)}
                if "Delete Success" in requests.post(API_URL, json=del_payload).text:
                    st.cache_data.clear()
                    st.rerun()
else:
    st.info("尚無資料")
