import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="👫 我們的甜蜜帳本", layout="centered")

# --- 設定區 ---
# 請將這裡換成剛才 Apps Script 產生的網址
API_URL = st.secrets["API_URL"]
# 請將這裡換成你的 Google 試算表「發佈到網路」的 CSV 連結，或繼續使用舊網址
SHEET_URL = st.secrets["SHEET_URL"]

def load_data():
    try:
        # 這裡改用 pandas 直接讀取 csv 格式
        csv_url = SHEET_URL.replace('/edit', '/export?format=csv')
        return pd.read_csv(csv_url)
    except:
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

df = load_data()

st.title("👫 我們的甜蜜帳本")

# 計算統計資訊
balance = 0
monthly_exp = 0
if not df.empty:
    df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
    df['餘額'] = pd.to_numeric(df['餘額'], errors='coerce').fillna(0)
    balance = df["餘額"].iloc[-1]
    this_month = datetime.now().strftime("%Y-%m")
    monthly_exp = df[(df['日期'].astype(str).str.startswith(this_month)) & (df['類型'] == '支出')]['金額'].sum()

c1, c2 = st.columns(2)
c1.metric("目前帳戶餘額", f"${balance:,.0f}")
c2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

with st.form("input_form", clear_on_submit=True):
    date = st.date_input("選擇日期", datetime.now())
    r_type = st.radio("交易類型", ["支出", "存款"], horizontal=True)
    cat = st.selectbox("分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他支出"]) if r_type == "支出" else "(存款)"
    item = st.text_input("項目描述")
    amount = st.number_input("金額", min_value=0, step=1)
    submit = st.form_submit_button("✅ 儲存這筆紀錄")

if submit:
    if item and amount > 0:
        new_balance = balance + amount if r_type == "存款" else balance - amount
        payload = {
            "日期": date.strftime("%Y-%m-%d"),
            "類型": r_type, 
            "金額": float(amount), 
            "項目": item, 
            "分類": cat, 
            "餘額": float(new_balance)
        }
        
        # 透過 API 寫入
        response = requests.post(API_URL, json=payload)
        
        if response.text == "Success":
            st.success("成功存入 Google 雲端！")
            st.rerun()
        else:
            st.error("寫入失敗，請檢查 API 網址")
    else:
        st.error("請填寫完整資訊！")

st.subheader("📋 最近紀錄")
st.dataframe(df.tail(10), use_container_width=True)
