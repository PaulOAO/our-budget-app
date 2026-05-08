import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import random

# 網頁基礎設定
st.set_page_config(page_title="👫 我們的帳本", layout="centered", page_icon="💰")

# 從 Secrets 讀取網址
try:
    API_URL = st.secrets["API_URL"]
    SHEET_URL = st.secrets["SHEET_URL"]
except:
    st.error("❌ 請在 Streamlit Secrets 中設定 API_URL 與 SHEET_URL")
    st.stop()

# 讀取資料函數 (終極防錯版)
@st.cache_data(ttl=1)
def load_data(url):
    try:
        # 強制轉換成 CSV 匯出網址
        csv_url = url.split('/edit')[0] + '/export?format=csv&gid=0'
        # 加入隨機參數繞過 Google 快取
        csv_url += f"&refresh={random.randint(1, 99999)}"
        
        data = pd.read_csv(csv_url)
        
        # 如果讀出來是空的或是欄位不對，強制建立正確結構
        required_cols = ["日期", "類型", "金額", "項目", "分類", "餘額"]
        if data.empty or not all(c in data.columns for c in required_cols):
            return pd.DataFrame(columns=required_cols)
            
        return data
    except Exception:
        # 發生任何錯誤 (如 EmptyDataError) 都要回傳正確的欄位格式
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

# 執行讀取
df = load_data(SHEET_URL)

# 計算統計資訊
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

# 顯示介面
st.title("👫 我們的帳本 v5.2")
c1, c2 = st.columns(2)
c1.metric("目前總餘額", f"${balance:,.0f}")
c2.metric("本月總消費", f"${monthly_exp:,.0f}")
st.divider()

# 輸入表單
with st.form("input_form", clear_on_submit=True):
    date = st.date_input("選擇日期", datetime.now())
    r_type = st.radio("交易類型", ["支出", "存款"], horizontal=True)
    cat = st.selectbox("分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他"]) if r_type == "支出" else "(存款)"
    item = st.text_input("項目描述")
    amount = st.number_input("金額", min_value=0, step=1)
    submit = st.form_submit_button("✅ 儲存紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('正在同步至雲端...'):
            new_balance = balance + amount if r_type == "存款" else balance - amount
            payload = {"日期": date.strftime("%Y-%m-%d"), "類型": r_type, "金額": float(amount), "項目": item, "分類": cat, "餘額": float(new_balance)}
            try:
                response = requests.post(API_URL, json=payload, timeout=10)
                if "Success" in response.text:
                    st.success("成功存入！網頁更新中...")
                    st.cache_data.clear()
                    time.sleep(1.5) # 稍微多等一下讓 Google 存檔
                    st.rerun()
                else:
                    st.error("寫入失敗，請檢查 Apps Script 部署")
            except Exception as e:
                st.error(f"連線錯誤: {e}")
    else:
        st.error("請輸入項目與金額")

st.subheader("📋 最近紀錄")
if not df.empty:
    st.dataframe(df.tail(10).iloc[::-1], use_container_width=True, hide_index=True)
else:
    st.info("目前尚無資料。")
