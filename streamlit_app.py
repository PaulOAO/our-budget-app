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
    st.error("❌ Secrets 設定錯誤，請確認 Streamlit 後台已填入 API_URL 與 SHEET_URL")
    st.stop()

# 3. 讀取資料函數 (強效繞過快取版)
@st.cache_data(ttl=1)
def load_data(url):
    try:
        # 將編輯網址轉換成 CSV 匯出格式
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/export?format=csv&gid=0"
        # 加入隨機參數防止 Google 傳回舊的快取資料
        csv_url += f"&refresh={random.randint(1, 99999)}"
        
        data = pd.read_csv(csv_url)
        
        # 確保欄位存在，避免讀到空表時報錯
        required_cols = ["日期", "類型", "金額", "項目", "分類", "餘額"]
        if data.empty or not all(c in data.columns for c in required_cols):
            return pd.DataFrame(columns=required_cols)
        
        # 數值轉換：確保公式算出來的結果能正確顯示為數字
        data['金額'] = pd.to_numeric(data['金額'], errors='coerce').fillna(0)
        data['餘額'] = pd.to_numeric(data['餘額'], errors='coerce').fillna(0)
        return data
    except:
        return pd.DataFrame(columns=["日期", "類型", "金額", "項目", "分類", "餘額"])

# 執行讀取資料
df = load_data(SHEET_URL)

# 4. 統計計算
balance = df["餘額"].iloc[-1] if not df.empty else 0
this_month = datetime.now().strftime("%Y-%m")
# 確保日期是字串以便進行月份篩選
df['日期'] = df['日期'].astype(str)
monthly_exp = df[(df['日期'].str.startswith(this_month)) & (df['類型'] == '支出')]['金額'].sum() if not df.empty else 0

# 5. 介面顯示
st.title("👫 我們的帳本 v6.6")

col_m1, col_m2 = st.columns(2)
col_m1.metric("目前總餘額", f"${balance:,.0f}")
col_m2.metric("本月總消費", f"${monthly_exp:,.0f}")

st.divider()

# 6. 新增功能表單 (動態顯示選單)
with st.expander("➕ 新增帳目", expanded=True):
    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("選擇日期", datetime.now())
        r_type = st.radio("交易類型", ["支出", "存款"], horizontal=True)
        
        # 只有點選支出時，才跳出消費分類選單
        if r_type == "支出":
            cat = st.selectbox("消費分類", ["餐飲美食", "交通運輸", "居家生活", "休閒娛樂", "購物開銷", "醫療保健", "其他"])
        else:
            cat = "(存款收入)"
            
        item = st.text_input("項目描述 (例如：晚餐、公積金)")
        amount = st.number_input("金額", min_value=0, step=1)
        
        submit = st.form_submit_button("✅ 儲存紀錄")

if submit:
    if item and amount > 0:
        with st.spinner('正在儲存至 Google 試算表...'):
            payload = {
                "action": "add",
                "日期": date.strftime("%Y-%m-%d"),
                "類型": r_type, 
                "金額": float(amount), 
                "項目": item, 
                "分類": cat
            }
            try:
                response = requests.post(API_URL, json=payload, timeout=15)
                if response.status_code == 200:
                    st.success("✅ 儲存成功！")
                    st.cache_data.clear()
                    time.sleep(1.2) # 給 Google 伺服器一點時間運算公式
                    st.rerun()
                else:
                    st.error(f"儲存失敗，代碼：{response.status_code}")
            except Exception as e:
                st.error(f"連線錯誤：{e}")
    else:
        st.error("⚠️ 請填寫完整內容！")

st.divider()

# 7. 顯示歷史紀錄與優化後的刪除功能
st.subheader("📋 最近紀錄")
if not df.empty:
    recent_indices = df.tail(10).index.tolist()
    
    # 建立表頭
    h = st.columns([2, 1, 1, 2, 2, 1, 1])
    headers = ["日期", "類型", "金額", "項目", "分類", "餘額", "操作"]
    for col, head in zip(h, headers):
        col.write(f"**{head}**")

    # 倒序顯示最新 10 筆紀錄
    for i in reversed(recent_indices):
        row = df.loc[i]
        cols = st.columns([2, 1, 1, 2, 2, 1, 1])
        cols[0].write(row['日期'])
        cols[1].write(row['類型'])
        cols[2].write(f"${row['金額']:,.0f}")
        cols[3].write(row['項目'])
        cols[4].write(row['分類'])
        cols[5].write(f"${row['餘額']:,.0f}")
        
        # 刪除按鈕與改進後的偵錯邏輯
        if cols[6].button("🗑️", key=f"del_{i}"):
            with st.spinner("正在刪除並重算餘額..."):
                try:
                    # 延長 Timeout 並放寬判斷條件
                    res = requests.post(
                        API_URL, 
                        json={"action": "delete", "index": int(i)}, 
                        timeout=20
                    )
                    
                    if res.status_code == 200:
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        # 即使回傳非 200，若刪除動作已執行，手動刷新也會對
                        st.cache_data.clear()
                        st.rerun()
                        
                except requests.exceptions.Timeout:
                    # 處理 Google Apps Script 執行緩慢的情況
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"刪除發生異常：{e}")
else:
    st.info("目前尚無資料，趕快記下第一筆帳吧！")

# 8. 消費分析按鈕
if st.checkbox("📊 顯示本月消費圓餅圖"):
    if not df.empty and monthly_exp > 0:
        this_month_df = df[(df['日期'].str.startswith(this_month)) & (df['類型'] == '支出')]
        if not this_month_df.empty:
            cat_stats = this_month_df.groupby('分類')['金額'].sum()
            st.pie_chart(cat_stats)
