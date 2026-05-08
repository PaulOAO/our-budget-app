import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# 設定網頁標籤與佈局
st.set_page_config(page_title="👫 我們的甜蜜帳本", layout="centered", page_icon="💰")

# 從 Secrets 讀取設定
try:
    API_URL = st.secrets["API_URL"]
    SHEET_URL = st.secrets["SHEET_URL"]
except:
    st.error("請在 Streamlit Secrets 中設定 API_URL 與 SHEET_URL")
    st.stop()

# 強制每 60 秒更新一次快取，存檔時會手動清空
@st.cache_data(ttl=60)
def load_data(url):
    try:
        # 將編輯網址轉為 CSV 匯出網址，這在讀取上最快最穩
        csv_url = url.replace('/edit', '/export?format=csv')
        # 加上 timestamp 參數防止瀏覽器快取舊資料
        csv_url += f"&cache_buster={datetime.now().timestamp()}"
        data = pd.read_csv(csv_url)
        return data
    except Exception as e:
        # 如果讀取失敗，回傳空的結構
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

# 載入資料
df = load_data(SHEET_URL)

# --- 頁面標題 ---
st.title("👫 我們的甜蜜帳本 v5.0")

# --- 數據統計 ---
balance = 0
monthly_exp = 0

if not df.empty:
    # 確保數值欄位格式正確
    df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
    df['餘額'] = pd.to_numeric(df['餘額'], errors='coerce').fillna(0)
    
    # 獲取最新餘額
    balance = df["餘額"].iloc[-1]
    
    # 計算本月總支出
    this_month = datetime.now().strftime("%Y-%m")
    df['日期'] = df['日期'].astype(str)
    monthly_df = df[(df['日期'].str.startswith(this_month)) & (df['類型'] == '支出')]
    monthly_exp = monthly_df['金額'].sum()

# 顯示頂部指標
c1, c2 = st.columns(2)
c1.metric("目前總餘額", f"${balance:,.0f}")
c2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

# --- 輸入表單 ---
with st.form("input_form", clear_on_submit=True):
    date = st.date_input("選擇日期", datetime.now())
    r_type = st.radio("交易類型", ["支出", "存款"], horizontal=True)
    
    # 動態分類選單
    if r_type == "支出":
        cat = st.selectbox("消費分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他支出"])
    else:
        cat = "(存款)"
        
    item = st.text_input("項目描述 (例如：晚餐、公積金)")
    amount = st.number_input("金額", min_value=0, step=1)
    
    submit = st.form_submit_button("✅ 儲存這筆紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('正在同步至雲端...'):
            # 計算新餘額
            new_balance = balance + amount if r_type == "存款" else balance - amount
            
            # 準備發送給 Google Apps Script 的資料
            payload = {
                "日期": date.strftime("%Y-%m-%d"),
                "類型": r_type, 
                "金額": float(amount), 
                "項目": item, 
                "分類": cat, 
                "餘額": float(new_balance)
            }
            
            try:
                # 透過 API 寫入資料
                response = requests.post(API_URL, json=payload, timeout=10)
                if "Success" in response.text:
                    st.success("紀錄成功！資料已更新。")
                    # 重要：手動清除快取並重整網頁
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"寫入失敗，API 回應：{response.text}")
            except Exception as e:
                st.error(f"連線錯誤：{e}")
    else:
        st.error("請填寫項目名稱與金額喔！")

# --- 歷史紀錄區 ---
st.subheader("📋 最近 10 筆紀錄")
if not df.empty:
    # 倒序顯示最新紀錄在最上面
    display_df = df.tail(10).iloc[::-1]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("目前尚無資料，快來記下第一筆吧！")

# --- 分類分析區 ---
if st.button("📊 查看本月消費佔比"):
    if not df.empty and not monthly_df.empty:
        cat_stats = monthly_df.groupby('分類')['金額'].sum()
        st.pie_chart(cat_stats)
        for c, v in cat_stats.items():
            st.write(f"• {c}: ${v:,.0f} ({(v/monthly_exp)*100:.1f}%)")
    else:
        st.write("本月尚無消費紀錄可供分析。")
