import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime
import twstock

# =========================
# Secrets
# =========================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

st.set_page_config(page_title="AI交易面板 Mobile v13.4", layout="wide")
st.title("📱 AI交易面板 Mobile v13.4｜台股雷達 + 手機通知")

if "sent_alerts" not in st.session_state:
    st.session_state.sent_alerts = set()

# =========================
# AI 概念股池
# =========================
AI_STOCK_POOL = {
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
    "2382.TW": "廣達",
    "3231.TW": "緯創",
    "6669.TW": "緯穎",
    "3017.TW": "奇鋐",
    "3324.TWO": "雙鴻",
    "3661.TW": "世芯-KY",
    "2454.TW": "聯發科",
    "3035.TW": "智原",
    "3443.TW": "創意",
    "2376.TW": "技嘉",
    "2377.TW": "微星",
    "2356.TW": "英業達",
    "2308.TW": "台達電",
    "3105.TWO": "穩懋",
    "4906.TW": "正文",
    "6285.TW": "啟碁",
    "8046.TW": "南電",
    "3189.TWO": "景碩",
    "2383.TW": "台光電",
    "2368.TW": "金像電",
    "6274.TWO": "台燿",
    "6213.TW": "聯茂",
}

# =========================
# Sidebar
# =========================
st.sidebar.header("掃描設定")

scan_mode = st.sidebar.selectbox(
    "掃描來源",
    ["全部台股", "AI概念股池", "自訂清單"],
    index=1
)

scan_limit = st.sidebar.slider("掃描台股檔數", 10, 500, 50)

custom_text = st.sidebar.text_area(
    "自訂清單，一行一檔",
    value="2330.TW\n2317.TW\n2382.TW\n3231.TW\n6669.TW\n3017.TW\n3661.TW\n3105.TWO"
)

refresh_sec = st.sidebar.slider("刷新秒數", 60, 1200, 180)
auto_refresh = st.sidebar.checkbox("自動刷新", value=False)

st.sidebar.header("推播設定")
alert_score = st.sidebar.slider("推播最低分數", 60, 100, 75)
only_volume_alert = st.sidebar.checkbox("推播需成交量放大", value=True)
avoid_hot_rsi = st.sidebar.checkbox("避開 RSI 過熱推播", value=True)

# =========================
# Telegram
# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

if st.sidebar.button("測試 Telegram 通知"):
    ok = send_telegram("✅ AI交易面板 Mobile v13.4 測試通知成功")
    if ok:
        st.sidebar.success("已送出")
    else:
        st.sidebar.error("發送失敗，請檢查 Secrets")

if st.sidebar.button("清除通知紀錄"):
    st.session_state.sent_alerts = set()
    st.sidebar.success("已清除")

# =========================
# 股票清單
# =========================
@st.cache_data(ttl=3600)
def get_tw_stocks(limit):
    result = []

    for code, info in twstock.codes.items():
        if len(code) == 4 and info.type == "股票":
            if info.market == "上市":
                yf_code = f"{code}.TW"
            elif info.market == "上櫃":
                yf_code = f"{code}.TWO"
            else:
                continue

            result.append({
                "名稱": f"{info.name} {code}",
                "代號": yf_code,
                "市場": info.market
            })

        if len(result) >= limit:
            break

    return result

def get_scan_list():
    if scan_mode == "AI概念股池":
        return [
            {"名稱": f"{name} {code.replace('.TW','').replace('.TWO','')}", "代號": code, "市場": "AI概念"}
            for code, name in AI_STOCK_POOL.items()
        ]

    if scan_mode == "自訂清單":
        result = []
        for code in custom_text.splitlines():
            code = code.strip()
            if not code:
                continue
            result.append({
                "名稱": code,
                "代號": code,
                "市場": "自訂"
            })
        return result

    return get_tw_stocks(scan_limit)

# =========================
# 技術資料
# =========================
@st.cache_data(ttl=120)
def get_data(code):
    data = yf.download(code, period="10mo", interval="1d", progress=False, auto_adjust=False)

    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data[["Open", "High", "Low", "Close", "Volume"]]
    data = data.apply(pd.to_numeric, errors="coerce").dropna()

    if len(data) < 90:
        return None

    data["MA5"] = data["Close"].rolling(5).mean()
    data["MA20"] = data["Close"].rolling(20).mean()
    data["MA60"] = data["Close"].rolling(60).mean()
    data["VOL20"] = data["Volume"].rolling(20).mean()
    data["HIGH20"] = data["High"].rolling(20).max()
    data["HIGH60"] = data["High"].rolling(60).max()

    delta = data["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    data["RSI"] = 100 - (100 / (1 + rs))

    ema12 = data["Close"].ewm(span=12, adjust=False).mean()
    ema26 = data["Close"].ewm(span=26, adjust=False).mean()
    data["MACD"] = ema12 - ema26
    data["SIGNAL"] = data["MACD"].ewm(span=9, adjust=False).mean()

    return data.dropna()

# =========================
# 判斷邏輯
# =========================
def judge(data, is_ai_stock=False):
    l = data.iloc[-1]
    p = data.iloc[-2]

    trend_up = l["Close"] > l["MA20"] > l["MA60"]
    macd_up = l["MACD"] > l["SIGNAL"]
    macd_cross_up = p["MACD"] <= p["SIGNAL"] and l["MACD"] > l["SIGNAL"]
    vol_up = l["Volume"] > l["VOL20"] * 1.5
    breakout20 = l["Close"] >= p["HIGH20"]
    breakout60 = l["Close"] >= p["HIGH60"]
    break_ma20 = p["Close"] <= p["MA20"] and l["Close"] > l["MA20"]
    rsi_ok = 45 <= l["RSI"] <= 75
    rsi_turn = p["RSI"] < 50 and l["RSI"] >= 50
    rsi_hot = l["RSI"] > 82
    weak = l["Close"] < l["MA20"]
    strong_today = ((l["Close"] - p["Close"]) / p["Close"]) * 100 >= 3

    score = 0
    tags = []

    if trend_up:
        score += 25
        tags.append("突破月線")
    if macd_up:
        score += 15
    if macd_cross_up:
        score += 15
        tags.append("MACD翻正")
    if vol_up:
        score += 20
        tags.append("爆量股")
    if breakout20:
        score += 15
        tags.append("突破20日高")
    if breakout60:
        score += 20
        tags.append("創波段高")
    if rsi_ok:
        score += 10
    if rsi_turn:
        score += 10
        tags.append("RSI轉強")
    if strong_today:
        score += 10
        tags.append("今日強勢")
    if is_ai_stock:
        score += 5
        tags.append("AI概念股")

    score = min(score, 100)

    short_stop = data["Low"].tail(5).min()
    swing_stop = l["MA20"]
    defense_line = l["MA60"]

    if rsi_hot:
        action = "🔴 建議減碼"
        reason = "RSI 過熱"
    elif weak:
        action = "🔴 建議出場"
        reason = "跌破 MA20"
    elif score >= 80:
        action = "🟢 強買點"
        reason = "多頭 + 放量 + 突破 + 動能轉強"
    elif score >= 65:
        action = "🟡 可觀察買點"
        reason = "條件不錯，但尚未完全確認"
    elif trend_up and macd_up:
        action = "✅ 多頭續抱"
        reason = "趨勢仍強"
    elif l["MACD"] < l["SIGNAL"]:
        action = "⚠️ 轉弱觀察"
        reason = "MACD 轉弱"
    else:
        action = "⏸ 觀望"
        reason = "無明確訊號"

    if not tags:
        tags.append("一般觀察")

    return {
        "action": action,
        "reason": reason,
        "score": score,
        "tags": tags,
        "short_stop": short_stop,
        "swing_stop": swing_stop,
        "defense_line": defense_line,
        "vol_up": vol_up,
        "rsi_hot": rsi_hot,
        "breakout20": breakout20,
        "breakout60": breakout60,
        "macd_cross_up": macd_cross_up,
        "rsi_turn": rsi_turn,
        "strong_today": strong_today,
        "break_ma20": break_ma20,
    }

def should_alert(judgement):
    if judgement["score"] < alert_score:
        return False

    if only_volume_alert and not judgement["vol_up"]:
        return False

    if avoid_hot_rsi and judgement["rsi_hot"]:
        return False

    if "強買點" in judgement["action"] or "可觀察買點" in judgement["action"]:
        return True

    return False

# =========================
# 掃描
# =========================
stocks = get_scan_list()

st.subheader(f"📡 掃描來源：{scan_mode}｜共 {len(stocks)} 檔")

results = []
progress = st.progress(0)

for i, item in enumerate(stocks):
    name = item["名稱"]
    code = item["代號"]
    is_ai_stock = code in AI_STOCK_POOL or scan_mode == "AI概念股池"

    try:
        d = get_data(code)
        if d is None:
            continue

        j = judge(d, is_ai_stock=is_ai_stock)
        l = d.iloc[-1]
        p = d.iloc[-2]
        change_pct = ((l["Close"] - p["Close"]) / p["Close"]) * 100

        alert_key = f"{datetime.now().date()}-{code}-{j['action']}-{j['score']}"

        if should_alert(j) and alert_key not in st.session_state.sent_alerts:
            send_telegram(
                f"📱 AI交易雷達通知 v13.4\n"
                f"股票：{name}\n"
                f"代號：{code}\n"
                f"收盤：{l['Close']:.2f}\n"
                f"漲跌幅：{change_pct:.2f}%\n"
                f"RSI：{l['RSI']:.2f}\n"
                f"分數：{j['score']}\n"
                f"建議：{j['action']}\n"
                f"分類：{'、'.join(j['tags'])}\n"
                f"原因：{j['reason']}\n"
                f"短線停損：{j['short_stop']:.2f}\n"
                f"波段停損：{j['swing_stop']:.2f}\n"
                f"防守線：{j['defense_line']:.2f}"
            )
            st.session_state.sent_alerts.add(alert_key)

        results.append({
            "名稱": name,
            "代號": code,
            "收盤": round(l["Close"], 2),
            "漲跌幅%": round(change_pct, 2),
            "RSI": round(l["RSI"], 2),
            "分數": j["score"],
            "分類": "、".join(j["tags"]),
            "成交量放大": "是" if j["vol_up"] else "否",
            "突破20日高": "是" if j["breakout20"] else "否",
            "創波段高": "是" if j["breakout60"] else "否",
            "建議": j["action"],
            "原因": j["reason"],
            "短線停損": round(j["short_stop"], 2),
            "波段停損": round(j["swing_stop"], 2),
            "防守線": round(j["defense_line"], 2),
        })

    except Exception as e:
        results.append({
            "名稱": name,
            "代號": code,
            "收盤": None,
            "漲跌幅%": None,
            "RSI": None,
            "分數": 0,
            "分類": "-",
            "成交量放大": "-",
            "突破20日高": "-",
            "創波段高": "-",
            "建議": "讀取失敗",
            "原因": str(e),
            "短線停損": None,
            "波段停損": None,
            "防守線": None,
        })

    progress.progress((i + 1) / len(stocks))

df = pd.DataFrame(results)

if df.empty:
    st.error("沒有掃描到有效資料。")
    st.stop()

df = df.sort_values(by=["分數", "漲跌幅%"], ascending=False).reset_index(drop=True)

# =========================
# Top 5
# =========================
st.subheader("🏆 今日 Top 5 雷達")
top5 = df.head(5)
st.dataframe(
    top5[["名稱", "代號", "收盤", "漲跌幅%", "RSI", "分數", "分類", "建議", "短線停損", "波段停損"]],
    use_container_width=True
)

# =========================
# 分類 Tabs
# =========================
strong_df = df[df["分類"].str.contains("今日強勢", na=False)]
ai_df = df[df["分類"].str.contains("AI概念股", na=False)]
volume_df = df[df["分類"].str.contains("爆量股", na=False)]
ma20_df = df[df["分類"].str.contains("突破月線", na=False)]
macd_df = df[df["分類"].str.contains("MACD翻正", na=False)]
rsi_df = df[df["分類"].str.contains("RSI轉強", na=False)]
high_df = df[df["分類"].str.contains("創波段高", na=False)]
buy_df = df[df["建議"].str.contains("強買點|可觀察買點", na=False)]
risk_df = df[df["建議"].str.contains("出場|減碼", na=False)]

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "🔥 今日強勢",
    "🤖 AI概念股",
    "💥 爆量股",
    "📈 突破月線",
    "🟢 MACD翻正",
    "💪 RSI轉強",
    "🚀 創波段高",
    "🟡 買點",
    "🔴 風險",
    "📋 全部",
])

with tab1:
    st.dataframe(strong_df, use_container_width=True)

with tab2:
    st.dataframe(ai_df, use_container_width=True)

with tab3:
    st.dataframe(volume_df, use_container_width=True)

with tab4:
    st.dataframe(ma20_df, use_container_width=True)

with tab5:
    st.dataframe(macd_df, use_container_width=True)

with tab6:
    st.dataframe(rsi_df, use_container_width=True)

with tab7:
    st.dataframe(high_df, use_container_width=True)

with tab8:
    st.dataframe(buy_df, use_container_width=True)

with tab9:
    st.dataframe(risk_df, use_container_width=True)

with tab10:
    st.dataframe(df, use_container_width=True)

st.caption(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()
