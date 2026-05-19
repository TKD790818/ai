from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import twstock

try:
    import shioaji as sj
except Exception:
    sj = None

# =========================
# 基本設定
# =========================
TW_TZ = ZoneInfo("Asia/Taipei")

TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
SHIOAJI_API_KEY = st.secrets.get("SHIOAJI_API_KEY", "")
SHIOAJI_SECRET_KEY = st.secrets.get("SHIOAJI_SECRET_KEY", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    st.error("尚未設定 TELEGRAM_TOKEN 或 TELEGRAM_CHAT_ID")
    st.stop()

st.set_page_config(
    page_title="AI交易面板 Mobile v14.1",
    layout="wide"
)

# =========================
# Lite UI CSS：只改外觀，不動數據邏輯
# =========================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 1200px;
    }
    .main-title {
        font-size: 28px;
        font-weight: 900;
        margin-bottom: 2px;
    }
    .sub-title {
        color: #64748b;
        font-size: 14px;
        margin-bottom: 16px;
    }
    .dash-card {
        padding: 16px;
        border-radius: 20px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.80));
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.15);
        margin-bottom: 12px;
    }
    .dash-label {
        font-size: 13px;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    .dash-value {
        font-size: 24px;
        font-weight: 900;
        color: #f8fafc;
    }
    .dash-sub {
        font-size: 12px;
        color: #cbd5e1;
        margin-top: 4px;
    }
    .heat-title {
        font-size: 20px;
        font-weight: 900;
        margin: 18px 0 8px 0;
    }
    .heat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
        gap: 10px;
        margin-bottom: 18px;
    }
    .heat-box {
        padding: 14px;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: #0f172a;
        color: white;
    }
    .heat-name {
        font-size: 15px;
        font-weight: 800;
    }
    .heat-score {
        font-size: 28px;
        font-weight: 900;
        margin-top: 6px;
    }
    .heat-meta {
        font-size: 12px;
        color: #cbd5e1;
        margin-top: 6px;
        line-height: 1.45;
    }
    .heat-green { background: linear-gradient(135deg, rgba(16, 185, 129, 0.92), rgba(6, 95, 70, 0.92)); }
    .heat-lime { background: linear-gradient(135deg, rgba(101, 163, 13, 0.92), rgba(63, 98, 18, 0.92)); }
    .heat-gray { background: linear-gradient(135deg, rgba(51, 65, 85, 0.95), rgba(15, 23, 42, 0.95)); }
    .heat-orange { background: linear-gradient(135deg, rgba(249, 115, 22, 0.92), rgba(124, 45, 18, 0.92)); }
    .heat-red { background: linear-gradient(135deg, rgba(239, 68, 68, 0.92), rgba(127, 29, 29, 0.92)); }
    .mini-note {
        color: #64748b;
        font-size: 13px;
        margin-top: -4px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="main-title">📱 AI交易面板 Mobile v14.1</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Shioaji 即時行情｜市場情緒｜類股熱力圖｜主力雷達｜空方警戒</div>', unsafe_allow_html=True)

if "sent_alerts" not in st.session_state:
    st.session_state.sent_alerts = set()

# =========================
# 主題股票池
# =========================
THEME_POOLS = {
    "AI概念股": {
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
    },
    "半導體": {
        "2330.TW": "台積電",
        "2454.TW": "聯發科",
        "3661.TW": "世芯-KY",
        "3443.TW": "創意",
        "3035.TW": "智原",
        "2379.TW": "瑞昱",
        "2408.TW": "南亞科",
        "2303.TW": "聯電",
        "3105.TWO": "穩懋",
    },
    "AI伺服器": {
        "2317.TW": "鴻海",
        "2382.TW": "廣達",
        "3231.TW": "緯創",
        "6669.TW": "緯穎",
        "2356.TW": "英業達",
        "2376.TW": "技嘉",
        "2377.TW": "微星",
    },
    "散熱": {
        "3017.TW": "奇鋐",
        "3324.TWO": "雙鴻",
        "3653.TW": "健策",
        "2421.TW": "建準",
    },
    "PCB / CCL": {
        "2383.TW": "台光電",
        "2368.TW": "金像電",
        "6274.TWO": "台燿",
        "6213.TW": "聯茂",
        "8046.TW": "南電",
    },
    "光通訊 / 網通": {
        "4906.TW": "正文",
        "6285.TW": "啟碁",
        "2345.TW": "智邦",
        "3081.TWO": "聯亞",
    },
    "記憶體": {
        "2408.TW": "南亞科",
        "2344.TW": "華邦電",
        "3260.TWO": "威剛",
        "8299.TWO": "群聯",
    },
    "金融": {
        "2881.TW": "富邦金",
        "2882.TW": "國泰金",
        "2891.TW": "中信金",
        "2886.TW": "兆豐金",
    },
    "航運": {
        "2603.TW": "長榮",
        "2609.TW": "陽明",
        "2615.TW": "萬海",
        "2618.TW": "長榮航",
    },
}

# =========================
# Sidebar
# =========================
st.sidebar.header("系統狀態")
st.sidebar.write("Shioaji：", "✅ 已設定" if SHIOAJI_API_KEY and SHIOAJI_SECRET_KEY else "❌ 未設定")
st.sidebar.write("Telegram：", "✅ 已設定" if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID else "❌ 未設定")

st.sidebar.header("掃描設定")
scan_mode = st.sidebar.selectbox(
    "掃描來源",
    [
        "AI概念股",
        "半導體",
        "AI伺服器",
        "散熱",
        "PCB / CCL",
        "光通訊 / 網通",
        "記憶體",
        "金融",
        "航運",
        "全部台股",
    ],
    index=0,
)

scan_limit = st.sidebar.slider("全部台股掃描檔數", 10, 500, 50)
refresh_sec = st.sidebar.slider("刷新秒數", 60, 1200, 180)
auto_refresh = st.sidebar.checkbox("自動刷新", value=False)

st.sidebar.header("多方推播設定")
alert_score = st.sidebar.slider("多方推播最低分數", 60, 100, 75)
only_volume_alert = st.sidebar.checkbox("多方推播需成交量放大", value=True)
avoid_hot_rsi = st.sidebar.checkbox("避開 RSI 過熱推播", value=True)

st.sidebar.header("空方警戒設定")
bear_alert_score = st.sidebar.slider("空方警戒推播最低分數", 60, 100, 75)
enable_bear_alert = st.sidebar.checkbox("啟用空方警戒推播", value=True)

st.sidebar.header("盤中量能設定")
intraday_hot_ratio = st.sidebar.slider("盤中爆量倍數", 1.2, 5.0, 2.0, 0.1)
major_force_amount = st.sidebar.number_input("主力雷達最低成交值", value=100000000, step=10000000)

# =========================
# Shioaji
# =========================
@st.cache_resource
def init_shioaji():
    if sj is None:
        return None, "尚未安裝 shioaji"

    if not SHIOAJI_API_KEY or not SHIOAJI_SECRET_KEY:
        return None, "尚未設定 SHIOAJI_API_KEY 或 SHIOAJI_SECRET_KEY"

    try:
        api = sj.Shioaji(simulation=True)
        api.login(api_key=SHIOAJI_API_KEY, secret_key=SHIOAJI_SECRET_KEY)
        return api, "Shioaji 已登入"
    except Exception as e:
        return None, f"Shioaji 登入失敗：{e}"

api, shioaji_status = init_shioaji()
st.sidebar.caption(shioaji_status)

# =========================
# 工具函式
# =========================
def clean_code(yf_code):
    return yf_code.replace(".TW", "").replace(".TWO", "")


def is_market_time():
    now = datetime.now(TW_TZ)
    weekday_ok = now.weekday() <= 4
    current_minutes = now.hour * 60 + now.minute
    market_open = 9 * 60
    market_close = 13 * 60 + 30
    return weekday_ok and market_open <= current_minutes <= market_close


def market_progress_ratio():
    now = datetime.now(TW_TZ)
    current_minutes = now.hour * 60 + now.minute
    market_open = 9 * 60
    market_close = 13 * 60 + 30

    if current_minutes <= market_open:
        return 0.05
    if current_minutes >= market_close:
        return 1.0

    total = market_close - market_open
    passed = current_minutes - market_open
    return max(passed / total, 0.05)


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


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
            result.append({"名稱": f"{info.name} {code}", "代號": yf_code, "市場": info.market})
        if len(result) >= limit:
            break
    return result


def get_scan_list():
    if scan_mode == "全部台股":
        return get_tw_stocks(scan_limit)

    pool = THEME_POOLS.get(scan_mode, {})
    return [{"名稱": f"{name} {code}", "代號": code, "市場": scan_mode} for code, name in pool.items()]


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
    data["LOW20"] = data["Low"].rolling(20).min()
    data["LOW60"] = data["Low"].rolling(60).min()

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


def get_shioaji_snapshot(yf_code):
    if api is None:
        return None

    stock_id = clean_code(yf_code)
    try:
        contract = api.Contracts.Stocks[stock_id]
        snapshots = api.snapshots([contract])
        if not snapshots:
            return None

        s = snapshots[0]
        close = getattr(s, "close", None)
        total_volume = getattr(s, "total_volume", None)
        volume = getattr(s, "volume", None)
        change_rate = getattr(s, "change_rate", None)
        amount = getattr(s, "total_amount", None)

        return {
            "即時價": close,
            "即時量": total_volume if total_volume is not None else volume,
            "即時漲跌幅%": change_rate,
            "成交值": amount,
        }
    except Exception:
        return None


def calc_intraday_volume_ratio(realtime_volume, avg_volume20):
    if realtime_volume is None or avg_volume20 is None or avg_volume20 <= 0:
        return 0
    expected_volume_now = avg_volume20 * market_progress_ratio()
    if expected_volume_now <= 0:
        return 0
    return realtime_volume / expected_volume_now


def calc_buy_price(data, score, rsi_hot, weak):
    l = data.iloc[-1]
    close = l["Close"]
    ma20 = l["MA20"]
    low5 = data["Low"].tail(5).min()

    if rsi_hot or weak:
        return None
    if score >= 80:
        return max(ma20, close * 0.98)
    elif score >= 65:
        return max(low5, close * 0.975)
    return None


def judge(data, is_theme_stock=False):
    l = data.iloc[-1]
    p = data.iloc[-2]

    trend_up = l["Close"] > l["MA20"] > l["MA60"]
    macd_up = l["MACD"] > l["SIGNAL"]
    macd_cross_up = p["MACD"] <= p["SIGNAL"] and l["MACD"] > l["SIGNAL"]
    vol_up = l["Volume"] > l["VOL20"] * 1.5
    breakout20 = l["Close"] >= p["HIGH20"]
    breakout60 = l["Close"] >= p["HIGH60"]
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
    if is_theme_stock:
        score += 5
        tags.append(scan_mode)

    score = min(score, 100)

    short_stop = data["Low"].tail(5).min()
    swing_stop = l["MA20"]
    defense_line = l["MA60"]
    buy_price = calc_buy_price(data, score, rsi_hot, weak)

    if rsi_hot:
        action = "🔴 建議減碼"
        reason = "RSI 過熱"
    elif weak:
        action = "🔴 建議出場"
        reason = "跌破 MA20"
    elif score >= 80:
        action = "🟢 強買點"
        reason = "多頭 + 放量 + 突破"
    elif score >= 65:
        action = "🟡 可觀察買點"
        reason = "條件不錯"
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
        "buy_price": buy_price,
        "vol_up": vol_up,
        "rsi_hot": rsi_hot,
    }


def judge_bear(data):
    l = data.iloc[-1]
    p = data.iloc[-2]
    change_pct = ((l["Close"] - p["Close"]) / p["Close"]) * 100

    break_ma20 = p["Close"] >= p["MA20"] and l["Close"] < l["MA20"]
    below_ma20 = l["Close"] < l["MA20"]
    below_ma60 = l["Close"] < l["MA60"]
    macd_dead_cross = p["MACD"] >= p["SIGNAL"] and l["MACD"] < l["SIGNAL"]
    macd_weak = l["MACD"] < l["SIGNAL"]
    volume_ratio = l["Volume"] / l["VOL20"] if l["VOL20"] > 0 else 0
    heavy_down = volume_ratio >= 1.8 and change_pct <= -3
    rsi_break_50 = p["RSI"] >= 50 and l["RSI"] < 50
    rsi_weak = l["RSI"] < 45
    break_low20 = l["Close"] <= p["LOW20"]
    break_low60 = l["Close"] <= p["LOW60"]

    bear_score = 0
    bear_tags = []

    if break_ma20:
        bear_score += 25
        bear_tags.append("跌破MA20")
    if below_ma20:
        bear_score += 10
    if below_ma60:
        bear_score += 15
        bear_tags.append("跌破MA60")
    if macd_dead_cross:
        bear_score += 25
        bear_tags.append("MACD死亡交叉")
    elif macd_weak:
        bear_score += 10
        bear_tags.append("MACD轉弱")
    if heavy_down:
        bear_score += 30
        bear_tags.append("爆量下跌")
    if rsi_break_50:
        bear_score += 20
        bear_tags.append("RSI失守50")
    elif rsi_weak:
        bear_score += 10
        bear_tags.append("RSI偏弱")
    if break_low20:
        bear_score += 20
        bear_tags.append("跌破20日低")
    if break_low60:
        bear_score += 25
        bear_tags.append("跌破60日低")

    bear_score = min(bear_score, 100)

    if bear_score >= 80:
        bear_action = "📉 高度空方警戒"
        bear_reason = "空方訊號集中，避免摸底"
    elif bear_score >= 60:
        bear_action = "⚠️ 空方警戒"
        bear_reason = "短線轉弱，需控管風險"
    elif bear_score >= 40:
        bear_action = "🟠 轉弱觀察"
        bear_reason = "部分條件轉弱"
    else:
        bear_action = "✅ 空方風險低"
        bear_reason = "尚未出現明顯空方警訊"

    if not bear_tags:
        bear_tags.append("空方風險低")

    return {
        "bear_score": bear_score,
        "bear_action": bear_action,
        "bear_reason": bear_reason,
        "bear_tags": bear_tags,
        "volume_ratio": volume_ratio,
    }


def judge_major_force(change_pct, bull_score, bear_score, intraday_ratio, turnover, action, bear_action):
    if turnover is None:
        turnover = 0

    if intraday_ratio >= 2.5 and change_pct >= 2 and bull_score >= 70 and turnover >= major_force_amount:
        return "🟢 主力買盤疑似進場"
    if intraday_ratio >= 2.0 and change_pct >= 1 and bull_score >= 65:
        return "🟡 買盤增溫"
    if intraday_ratio >= 2.0 and change_pct <= -2 and bear_score >= 60 and turnover >= major_force_amount:
        return "🔴 主力賣壓疑似增加"
    if "空方警戒" in bear_action and intraday_ratio >= 1.8:
        return "🟠 賣壓偏重"
    if intraday_ratio >= 2.0:
        return "💥 盤中爆量"
    return "一般"


def should_alert(judgement):
    if not is_market_time():
        return False
    if judgement["score"] < alert_score:
        return False
    if only_volume_alert and not judgement["vol_up"]:
        return False
    if avoid_hot_rsi and judgement["rsi_hot"]:
        return False
    if "強買點" in judgement["action"] or "可觀察買點" in judgement["action"]:
        return True
    return False


def should_bear_alert(bear_judgement):
    if not is_market_time():
        return False
    if bear_judgement["bear_score"] < bear_alert_score:
        return False
    if "空方警戒" in bear_judgement["bear_action"]:
        return True
    return False


def market_sentiment(df):
    if df.empty:
        return "⚪ 無資料", 0

    avg_change = df["漲跌幅%"].fillna(0).mean()
    bull_count = (df["多方分數"] >= 65).sum()
    bear_count = (df["空方分數"] >= 60).sum()
    hot_count = (df["盤中量比"] >= intraday_hot_ratio).sum()

    score = 0
    score += avg_change * 5
    score += bull_count * 8
    score += hot_count * 5
    score -= bear_count * 10

    if score >= 60:
        label = "🟢 多頭強勢"
    elif score >= 30:
        label = "🟡 偏多觀察"
    elif score > -20:
        label = "⚪ 震盪整理"
    elif score > -50:
        label = "🟠 偏空警戒"
    else:
        label = "🔴 空方壓力"

    return label, round(score, 2)


def heat_class(score):
    if score >= 75:
        return "heat-green"
    if score >= 60:
        return "heat-lime"
    if score >= 45:
        return "heat-gray"
    if score >= 30:
        return "heat-orange"
    return "heat-red"


def render_dashboard_metric(label, value, sub=""):
    st.markdown(
        f"""
        <div class="dash-card">
            <div class="dash-label">{label}</div>
            <div class="dash-value">{value}</div>
            <div class="dash-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_heatmap(theme_summary):
    if not theme_summary:
        return

    html = '<div class="heat-title">🔥 類股熱力圖</div>'
    html += '<div class="mini-note">主畫面先看大方向：哪個族群熱、哪個族群轉弱。</div>'
    html += '<div class="heat-grid">'

    for item in theme_summary:
        css = heat_class(item["熱度分數"])
        html += f"""
        <div class="heat-box {css}">
            <div class="heat-name">{item['類股']}</div>
            <div class="heat-score">{item['熱度分數']}</div>
            <div class="heat-meta">
                {item['情緒']}<br>
                爆量 {item['爆量數']}｜多方 {item['多方數']}｜空方 {item['空方數']}
            </div>
        </div>
        """

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# =========================
# 掃描主流程
# =========================
stocks = get_scan_list()
st.subheader(f"📡 掃描來源：{scan_mode}｜共 {len(stocks)} 檔")

results = []
progress = st.progress(0)

for i, item in enumerate(stocks):
    name = item["名稱"]
    code = item["代號"]
    market_group = item.get("市場", scan_mode)
    is_theme_stock = scan_mode != "全部台股"

    try:
        d = get_data(code)
        if d is None:
            continue

        snap = get_shioaji_snapshot(code)
        j = judge(d, is_theme_stock=is_theme_stock)
        b = judge_bear(d)

        l = d.iloc[-1]
        p = d.iloc[-2]
        daily_change_pct = ((l["Close"] - p["Close"]) / p["Close"]) * 100

        realtime_price = None
        realtime_volume = None
        realtime_change_pct = None
        turnover = None

        if snap:
            realtime_price = snap.get("即時價")
            realtime_volume = snap.get("即時量")
            realtime_change_pct = snap.get("即時漲跌幅%")
            turnover = snap.get("成交值")

        display_price = realtime_price if realtime_price else l["Close"]
        display_change = realtime_change_pct if realtime_change_pct is not None else daily_change_pct

        intraday_ratio = calc_intraday_volume_ratio(realtime_volume, l["VOL20"])

        major_force = judge_major_force(
            display_change,
            j["score"],
            b["bear_score"],
            intraday_ratio,
            turnover,
            j["action"],
            b["bear_action"],
        )

        bull_alert_key = f"{datetime.now(TW_TZ).date()}-BULL-{code}-{j['action']}-{j['score']}"
        bear_alert_key = f"{datetime.now(TW_TZ).date()}-BEAR-{code}-{b['bear_action']}-{b['bear_score']}"

        if should_alert(j) and bull_alert_key not in st.session_state.sent_alerts:
            buy_price_text = "不建議追價" if j["buy_price"] is None else f"{j['buy_price']:.2f}"
            send_telegram(
                f"📱 AI交易雷達 v14.1\n"
                f"股票：{name}\n"
                f"代號：{code}\n"
                f"即時價：{display_price:.2f}\n"
                f"漲跌幅：{display_change:.2f}%\n"
                f"盤中量比：{intraday_ratio:.2f}\n"
                f"主力雷達：{major_force}\n"
                f"多方分數：{j['score']}\n"
                f"建議：{j['action']}\n"
                f"建議買價：{buy_price_text}\n"
                f"短線停損：{j['short_stop']:.2f}\n"
                f"波段停損：{j['swing_stop']:.2f}"
            )
            st.session_state.sent_alerts.add(bull_alert_key)

        if should_bear_alert(b) and bear_alert_key not in st.session_state.sent_alerts:
            send_telegram(
                f"📉 空方警戒雷達 v14.1\n"
                f"股票：{name}\n"
                f"代號：{code}\n"
                f"即時價：{display_price:.2f}\n"
                f"漲跌幅：{display_change:.2f}%\n"
                f"盤中量比：{intraday_ratio:.2f}\n"
                f"主力雷達：{major_force}\n"
                f"空方分數：{b['bear_score']}\n"
                f"警戒：{b['bear_action']}\n"
                f"條件：{'、'.join(b['bear_tags'])}"
            )
            st.session_state.sent_alerts.add(bear_alert_key)

        results.append(
            {
                "類股": market_group,
                "名稱": name,
                "代號": code,
                "即時價": None if realtime_price is None else round(realtime_price, 2),
                "收盤": round(l["Close"], 2),
                "漲跌幅%": round(display_change, 2),
                "即時量": realtime_volume,
                "成交值": turnover,
                "盤中量比": round(intraday_ratio, 2),
                "主力雷達": major_force,
                "RSI": round(l["RSI"], 2),
                "多方分數": j["score"],
                "空方分數": b["bear_score"],
                "分類": "、".join(j["tags"]),
                "空方條件": "、".join(b["bear_tags"]),
                "建議": j["action"],
                "空方警戒": b["bear_action"],
                "原因": j["reason"],
                "空方原因": b["bear_reason"],
                "建議買價": None if j["buy_price"] is None else round(j["buy_price"], 2),
                "短線停損": round(j["short_stop"], 2),
                "波段停損": round(j["swing_stop"], 2),
                "防守線": round(j["defense_line"], 2),
                "量比": round(b["volume_ratio"], 2),
            }
        )

    except Exception as e:
        results.append(
            {
                "類股": market_group,
                "名稱": name,
                "代號": code,
                "即時價": None,
                "收盤": None,
                "漲跌幅%": None,
                "即時量": None,
                "成交值": None,
                "盤中量比": 0,
                "主力雷達": "-",
                "RSI": None,
                "多方分數": 0,
                "空方分數": 0,
                "分類": "-",
                "空方條件": "-",
                "建議": "讀取失敗",
                "空方警戒": "-",
                "原因": str(e),
                "空方原因": "-",
                "建議買價": None,
                "短線停損": None,
                "波段停損": None,
                "防守線": None,
                "量比": None,
            }
        )

    progress.progress((i + 1) / len(stocks))

# =========================
# 資料整理與 UI 呈現
# =========================
df = pd.DataFrame(results)

if df.empty:
    st.error("沒有掃描到有效資料")
    st.stop()

df = df.sort_values(by=["多方分數", "盤中量比", "漲跌幅%"], ascending=False).reset_index(drop=True)

sentiment_label, sentiment_score = market_sentiment(df)

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_dashboard_metric("市場情緒", sentiment_label, f"分數 {sentiment_score}")
with c2:
    render_dashboard_metric("盤中爆量檔數", int((df["盤中量比"] >= intraday_hot_ratio).sum()), f"門檻 {intraday_hot_ratio} 倍")
with c3:
    render_dashboard_metric("多方強勢檔數", int((df["多方分數"] >= 65).sum()), "多方分數 ≥ 65")
with c4:
    render_dashboard_metric("空方警戒檔數", int((df["空方分數"] >= 60).sum()), "空方分數 ≥ 60")

# 類股熱力圖：目前若掃描單一主題，呈現該主題；若全部台股，依 twstock 市場或資料池標記分組。
theme_summary = []
for group_name, group_df in df.groupby("類股"):
    avg_change = group_df["漲跌幅%"].fillna(0).mean()
    bull_count = int((group_df["多方分數"] >= 65).sum())
    bear_count = int((group_df["空方分數"] >= 60).sum())
    hot_count = int((group_df["盤中量比"] >= intraday_hot_ratio).sum())

    heat_score = int(max(min(avg_change * 5 + bull_count * 15 + hot_count * 12 - bear_count * 12 + 45, 100), 0))

    if heat_score >= 75:
        mood = "🟢 多頭強勢"
    elif heat_score >= 60:
        mood = "🟡 偏多"
    elif heat_score >= 45:
        mood = "⚪ 震盪"
    elif heat_score >= 30:
        mood = "🟠 偏空"
    else:
        mood = "🔴 空方壓力"

    theme_summary.append(
        {
            "類股": group_name,
            "熱度分數": heat_score,
            "情緒": mood,
            "爆量數": hot_count,
            "多方數": bull_count,
            "空方數": bear_count,
        }
    )

theme_summary = sorted(theme_summary, key=lambda x: x["熱度分數"], reverse=True)
render_heatmap(theme_summary)

# 重要排行：維持表格，不改運算邏輯
st.subheader("🏆 今日多方 Top 5 雷達")
top5_cols = ["名稱", "代號", "即時價", "漲跌幅%", "盤中量比", "主力雷達", "多方分數", "空方分數", "建議", "建議買價", "短線停損", "波段停損"]
st.dataframe(df.head(5)[top5_cols], use_container_width=True)

st.subheader("📉 今日空方警戒 Top 5")
top5_bear = df.sort_values(by=["空方分數", "盤中量比"], ascending=False).head(5)
st.dataframe(top5_bear[top5_cols + ["空方警戒", "空方條件"]], use_container_width=True)

st.subheader("💥 盤中爆量 Top 5")
hot_volume_df = df.sort_values(by="盤中量比", ascending=False).head(5)
st.dataframe(hot_volume_df[top5_cols], use_container_width=True)

strong_df = df[df["分類"].str.contains("今日強勢", na=False)]
volume_df = df[df["盤中量比"] >= intraday_hot_ratio].sort_values(by="盤中量比", ascending=False)
major_df = df[df["主力雷達"].str.contains("主力|買盤|賣壓|爆量", na=False)]
macd_df = df[df["分類"].str.contains("MACD翻正", na=False)]
high_df = df[df["分類"].str.contains("創波段高", na=False)]
buy_df = df[df["建議"].str.contains("強買點|可觀察買點", na=False)]
risk_df = df[df["建議"].str.contains("減碼|出場", na=False)]
bear_df = df[df["空方警戒"].str.contains("空方警戒|高度空方警戒|轉弱觀察", na=False)].sort_values(by="空方分數", ascending=False)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
    [
        "🔥 今日強勢",
        "💥 盤中爆量",
        "🧲 主力雷達",
        "🟢 MACD翻正",
        "🚀 創波段高",
        "🟡 買點",
        "🔴 風險",
        "📉 空方警戒",
        "📋 全部",
    ]
)

with tab1:
    st.dataframe(strong_df, use_container_width=True)
with tab2:
    st.dataframe(volume_df, use_container_width=True)
with tab3:
    st.dataframe(major_df, use_container_width=True)
with tab4:
    st.dataframe(macd_df, use_container_width=True)
with tab5:
    st.dataframe(high_df, use_container_width=True)
with tab6:
    st.dataframe(buy_df, use_container_width=True)
with tab7:
    st.dataframe(risk_df, use_container_width=True)
with tab8:
    st.dataframe(bear_df, use_container_width=True)
with tab9:
    st.dataframe(df, use_container_width=True)

st.caption(f"最後更新：{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}｜台灣時間｜Shioaji 即時行情")

if auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()

