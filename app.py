# app.py — Беловежские сыры · аналитика. Навигация в сайдбаре, без загрузчика, без сверки.
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_echarts import st_echarts

st.set_page_config(page_title="Беловежские сыры · аналитика", page_icon="🌿", layout="wide")

PINE, PANEL, CREAM, MUTED = "#0d1f18", "#132a21", "#f2ede3", "#93a69b"
GOLD, AMBER, SAGE, TERRA, SKY = "#d8b45a", "#e0a43c", "#7fa88f", "#c4574e", "#8fb6c9"
GRID, PAL = "rgba(242,237,227,.06)", ["#d8b45a", "#7fa88f", "#e0a43c", "#8fb6c9", "#c4574e", "#93a69b"]
RU_DAYS = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]  # индекс 0 = воскресенье
RU_MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь",
             "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&family=Playfair+Display:ital,wght@0,600;0,800;1,500&display=swap');
html,body,[class*="css"]{font-family:'Manrope',sans-serif}
header[data-testid="stHeader"],#MainMenu,footer{display:none}
.block-container{padding-top:1.6rem;max-width:1500px}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,rgba(216,180,90,.07),transparent 60%),
  radial-gradient(900px 420px at -10% 110%,rgba(127,168,143,.06),transparent 60%),#0d1f18}
.brand{font-family:'Playfair Display',serif;font-weight:800;letter-spacing:.22em;font-size:26px;
  color:#f2ede3;text-transform:uppercase;line-height:1.1}
.brand em{color:#d8b45a;font-style:normal}
.tag{font-family:'Playfair Display',serif;font-style:italic;color:#93a69b;font-size:14px;margin-top:2px}
.rule{height:1px;background:linear-gradient(90deg,#d8b45a,rgba(216,180,90,0));margin:10px 0 18px}
.chip{display:inline-block;padding:6px 14px;border:1px solid rgba(216,180,90,.35);border-radius:999px;
  color:#d8b45a;font-size:12px;letter-spacing:.08em}
section[data-testid="stSidebar"]{background:#0a1a14;border-right:1px solid rgba(216,180,90,.15)}
section[data-testid="stSidebar"] .stButton>button{border-radius:999px;border:1px solid rgba(242,237,227,.14);
  background:rgba(242,237,227,.04);color:#cfd8cf;font-weight:600;letter-spacing:.05em;padding:10px 18px}
section[data-testid="stSidebar"] button[kind="primary"]{background:linear-gradient(135deg,#e6c476,#b98f2e);
  color:#10231b;border-color:transparent;box-shadow:0 8px 28px rgba(216,180,90,.25)}
.card{background:linear-gradient(160deg,rgba(242,237,227,.055),rgba(242,237,227,.015));
  border:1px solid rgba(216,180,90,.16);border-radius:18px;padding:16px 18px;transition:transform .25s,box-shadow .25s}
.card:hover{transform:translateY(-4px);border-color:rgba(216,180,90,.45);box-shadow:0 14px 44px rgba(0,0,0,.35)}
.kt{font-size:11px;color:#93a69b;text-transform:uppercase;letter-spacing:.14em}
.kv{font-size:36px;font-weight:800;color:#f2ede3;line-height:1.15;margin-top:2px}
.ku{font-family:'Playfair Display',serif;font-style:italic;font-size:16px;color:#d8b45a;margin-left:4px}
.pos{color:#7fa88f;font-weight:700;font-size:12px}.neg{color:#c4574e;font-weight:700;font-size:12px}
.src{color:#6d8074;font-size:10px;margin-top:6px}
.hd{min-height:70px}
.sec{font-family:'Playfair Display',serif;font-weight:600;font-size:20px;color:#f2ede3;margin:0}
.sub{color:#93a69b;font-size:12.5px;margin:2px 0 10px}
.ins{border-left:2px solid #d8b45a;padding:6px 12px;margin:6px 0;color:#cfd8cf;font-size:13px;
  background:rgba(216,180,90,.05);border-radius:0 10px 10px 0}
</style>""", unsafe_allow_html=True)

# ---------- парсер: секции + имена строк ----------
DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def norm(s): return re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip().lower().replace(", ", ",")


def clean_num(v):
    if pd.isna(v): return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(v).replace("\xa0", " ")).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def fmt(x, d=0): return f"{float(x):,.{d}f}".replace(",", " ")


def to_py(obj):
    """numpy-типы -> стандартные Python-типы для JSON-сериализации ECharts."""
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return [to_py(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {k: to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_py(v) for v in obj]
    return obj


@st.cache_data
def load(path):
    raw = pd.read_excel(path, header=None)
    hdr = next((i for i in range(len(raw))
                if sum(bool(DATE_RE.fullmatch(str(c).strip())) for c in raw.iloc[i]) >= 5), None)
    if hdr is None: raise ValueError("Не найдена строка с датами")
    cols = [j for j, c in enumerate(raw.iloc[hdr]) if DATE_RE.fullmatch(str(c).strip())]
    dates = pd.to_datetime([str(raw.iloc[hdr, j]).strip() for j in cols], format="%d.%m.%Y")
    section, recs = "сырье", []
    for i in range(hdr + 1, len(raw)):
        name = norm(raw.iloc[i, 0])
        if not name or name == "nan": continue
        if name.startswith("произведено,"):
            section = "производство"
        elif name.startswith("остатки на конец дня"):
            section = "остатки"
        elif name.startswith("продажи,"):
            section = "продажи"
        elif name.startswith("рентабельность"):
            section = "финансы"
        for j, d in zip(cols, dates):
            recs.append((d, section, name, clean_num(raw.iloc[i, j])))
    return pd.DataFrame(recs, columns=["date", "section", "metric", "value"]), dates


M = {
    "milk": ("сырье", "молоко: зачетный вес,тн"), "price": ("сырье", "цена"),
    "extra": ("сырье", "% экстра"), "first": ("сырье", "% первый сорт"),
    "high": ("сырье", "% высший сорт"), "protein": ("сырье", "белок"),
    "p_rub": ("производство", "произведено,руб"),
    "p_cheese": ("производство", "сыр,тн"), "p_pack": ("производство", "сыр фасованный,тн"),
    "p_feta": ("производство", "фета,тн"), "p_butter": ("производство", "масло,тн"),
    "p_ghi": ("производство", "масло гхи,тн"), "p_whey": ("производство", "сыворотка подсырная,тн"),
    "p_buth": ("производство", "пахта,тн"), "p_skim": ("производство", "обрат,тн"),
    "s_cheese": ("остатки", "сыр весовой,тн"), "s_pack": ("остатки", "сыр фасованный,тн"),
    "s_feta": ("остатки", "фета,тн"), "s_butter": ("остатки", "масло,тн"), "s_ghi": ("остатки", "масло гхи,тн"),
    "rev": ("продажи", "продажи,руб"), "v_cheese": ("продажи", "сыр,тн"),
    "v_pack": ("продажи", "в т.ч. фасованный,тн"), "v_feta": ("продажи", "фета,тн"),
    "v_butter": ("продажи", "масло,тн"), "v_ghi": ("продажи", "в т.ч. масло гхи,тн"),
    "profit": ("финансы", "прибыль от продаж,руб"), "margin": ("финансы", "рентабельность продаж,%"),
}


def ser(tidy, dates, k):
    sec, met = M[k]
    return tidy[(tidy.section == sec) & (tidy.metric == met)].groupby("date")["value"].sum().reindex(dates,
                                                                                                     fill_value=0.0)


try:
    tidy, dates = load("отчет в 1с.xlsx")
except Exception as e:
    st.error(f"Не удалось прочитать «отчет в 1с.xlsx»: {e}. Положите файл рядом с app.py.")
    st.stop()
S = {k: ser(tidy, dates, k) for k in M}
full = S["milk"] > 0.5 * S["milk"][S["milk"] > 0].median()

# ---------- сайдбар ----------
with st.sidebar:
    st.markdown('<div class="brand" style="font-size:17px">Беловежские <em>сыры</em></div>'
                '<div class="tag" style="font-size:12px">панель аналитики</div>', unsafe_allow_html=True)
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    if "nav" not in st.session_state: st.session_state.nav = "Производство"
    for name in ["Производство", "Продажи", "Сырье"]:
        if st.button(name, use_container_width=True,
                     type="primary" if st.session_state.nav == name else "secondary"):
            st.session_state.nav = name
            st.rerun()
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    lo, hi = st.slider("Дни периода", 1, len(dates), (1, len(dates)))
    use_partial = st.checkbox("Учитывать неполный последний день", True)
    st.download_button("Экспорт данных CSV", tidy.to_csv(index=False).encode("utf-8-sig"), "belcheese_data.csv")

nav = st.session_state.nav
sel = dates[lo - 1:hi]
if not use_partial: sel = sel[full.reindex(sel, fill_value=True)]
if len(sel) == 0:
    st.warning("В периоде нет учитываемых дней: включите «Учитывать неполный последний день» или расширьте период.")
    st.stop()
W = {k: v.reindex(sel, fill_value=0.0) for k, v in S.items()}
lbl = [d.strftime("%d.%m") for d in sel]
rate_days = max(1, int(full.reindex(sel, fill_value=False).sum()))


def delta(k):
    v = S[k][full.reindex(S[k].index, fill_value=False)]
    v = v[v.index.isin(sel)]
    if len(v) < 2 or v.iloc[-2] == 0: return 0.0
    return float(100 * (v.iloc[-1] - v.iloc[-2]) / abs(v.iloc[-2]))


def card(col, title, val, unit, src, dkey=None, dec=0):
    with col:
        d = delta(dkey) if dkey else None
        dh = (f'<div class="{"pos" if d >= 0 else "neg"}">{"+" if d >= 0 else ""}{d:.1f}% к пред. полному дню</div>'
              if d is not None else '<div class="src">за период</div>')
        st.markdown(f'<div class="card"><div class="kt">{title}</div>'
                    f'<div class="kv">{fmt(val, dec)}<span class="ku">{unit}</span></div>{dh}'
                    f'<div class="src">строка: {src}</div></div>', unsafe_allow_html=True)
        if dkey:
            sp = go.Figure(go.Scatter(y=W[dkey], mode="lines", line=dict(color=GOLD, width=2),
                                      fill="tozeroy", fillcolor="rgba(216,180,90,.12)"))
            sp.update_layout(height=44, margin=dict(l=0, r=0, t=4, b=0), paper_bgcolor="rgba(0,0,0,0)",
                             plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(visible=False), yaxis=dict(visible=False))
            st.plotly_chart(sp, use_container_width=True, config={"displayModeBar": False})


def head(t, s):
    st.markdown(f'<div class="hd"><p class="sec">{t}</p><p class="sub">{s}</p></div>', unsafe_allow_html=True)


def ins(items):
    st.markdown("".join(f'<div class="ins">{t}</div>' for t in items), unsafe_allow_html=True)


def base(h=300, **over):
    d = dict(height=h, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
             plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Manrope", color=CREAM, size=12),
             hoverlabel=dict(bgcolor=PANEL, bordercolor=GOLD, font=dict(color=CREAM)),
             xaxis=dict(gridcolor=GRID, zeroline=False), yaxis=dict(gridcolor=GRID, zeroline=False),
             legend=dict(orientation="h", y=-0.18, font=dict(size=11)))
    for k, v in over.items():
        d[k] = {**d[k], **v} if isinstance(v, dict) and isinstance(d.get(k), dict) else v
    return d


def ech(o, h="320px"):
    st_echarts(options=to_py(o), height=h)


def calendar_opt(vals, mx, label):
    """Календарь: месяц по-русски, в клетке число дня; количество — при наведении ({@[1]}) и цветом."""
    data = []
    for d, v in vals.items():
        d = pd.to_datetime(d)
        data.append({"name": str(d.day),
                     "value": [d.strftime("%Y-%m-%d"), round(float(v), 1), d.strftime("%d.%m")]})
    return {
        "backgroundColor": "transparent",
        "tooltip": {"trigger": "item", "confine": True,
                    "formatter": "{@[2]} · {@[1]} " + label,
                    "backgroundColor": PANEL, "borderColor": GOLD,
                    "textStyle": {"color": CREAM, "fontSize": 12}},
        "visualMap": {
            "min": 0, "max": max(float(mx), 1.0),
            "dimension": 1,
            "seriesIndex": 0,
            "calculable": False,
            "orient": "horizontal", "left": "center", "bottom": 10,
            "inRange": {"color": ["#132a21", SAGE, GOLD]},
            "textStyle": {"color": MUTED}
        },
        "calendar": {
            "top": 40, "left": 40, "right": 20, "bottom": 60,
            "cellSize": ["auto", 32],
            "range": sel[0].strftime("%Y-%m"),
            "firstDay": 1,
            "itemStyle": {"borderWidth": 2, "borderColor": PINE, "color": "#132a21"},
            "dayLabel": {"color": MUTED, "nameMap": RU_DAYS, "fontSize": 11},
            "monthLabel": {"color": GOLD, "nameMap": RU_MONTHS, "fontSize": 13, "margin": 6},
            "yearLabel": {"show": False}
        },
        "series": {
            "type": "heatmap",
            "coordinateSystem": "calendar",
            "data": data,
            "label": {"show": True, "formatter": "{b}",
                      "fontSize": 10, "fontWeight": 700,
                      "color": CREAM, "textBorderColor": PINE, "textBorderWidth": 2},
            "itemStyle": {"borderRadius": 4},
            "emphasis": {"itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(216,180,90,.5)"}}
        }
    }


# ---------- шапка ----------
h1, h2 = st.columns([0.72, 0.28])
with h1:
    st.markdown('<div class="brand">Беловежские <em>сыры</em></div>'
                '<div class="tag">мастерство, проверенное временем · ежедневная аналитика</div>',
                unsafe_allow_html=True)
with h2:
    st.markdown(f'<div style="text-align:right"><span class="chip">{sel[0]:%d.%m} – {sel[-1]:%d.%m.%Y}</span></div>',
                unsafe_allow_html=True)
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

# ================= ПРОИЗВОДСТВО =================
if nav == "Производство":
    cheese = W["p_cheese"] + W["p_pack"]
    c = st.columns(5)
    card(c[0], "Выпуск сыра", cheese.sum(), "тн", "сыр,тн + сыр фасованный (пр-во)", "p_cheese", 1)
    card(c[1], "Фета", W["p_feta"].sum(), "тн", "фета, тн (пр-во)", "p_feta", 1)
    card(c[2], "Масло + ГХИ", W["p_butter"].sum() + W["p_ghi"].sum(), "тн", "масло + масло гхи (пр-во)", "p_butter", 1)
    card(c[3], "Произведено", W["p_rub"].sum() / 1e6, "млн ₽", "Произведено, руб", "p_rub", 2)
    card(c[4], "Выход сыра", 100 * cheese.sum() / W["milk"].sum(), "%", "расчёт: сыр / молоко")
    a, b = st.columns([1.5, 1])
    with a:
        head("Баланс молока, тн", "Реальные строки отчёта; невязка — потери и остаток сырья (расчёт)")
        flows = [("Сыр весовой", float(W["p_cheese"].sum()), GOLD),
                 ("Сыр фасованный", float(W["p_pack"].sum()), AMBER),
                 ("Фета", float(W["p_feta"].sum()), SAGE),
                 ("Масло", float(W["p_butter"].sum()), SKY),
                 ("ГХИ", float(W["p_ghi"].sum()), "#b98f2e"),
                 ("Сыворотка подсырная", float(W["p_whey"].sum()), "#5f8f7a"),
                 ("Пахта", float(W["p_buth"].sum()), "#c98ba0"),
                 ("Обрат", float(W["p_skim"].sum()), MUTED)]
        gap = float(W["milk"].sum()) - sum(v for _, v, _ in flows)
        flows.append(("Потери / невязка", gap, "#41564c"))
        ech({"backgroundColor": "transparent", "tooltip": {"trigger": "item", "formatter": "{b}: {c} тн"},
             "series": [{"type": "sankey", "emphasis": {"focus": "adjacency"},
                         "data": [{"name": "Молоко", "itemStyle": {"color": GOLD}}] +
                                 [{"name": n, "itemStyle": {"color": cl}} for n, _, cl in flows],
                         "links": [{"source": "Молоко", "target": n, "value": round(float(v), 1)} for n, v, _ in flows if
                                   v > 0],
                         "lineStyle": {"color": "gradient", "curveness": .5, "opacity": .4},
                         "label": {"color": CREAM, "fontSize": 12}, "itemStyle": {"borderWidth": 0}}]}, "340px")
    with b:
        head("Календарь выпуска сыра", "Цвет и наведение = сыр весовой + фасованный, тн/день")
        ech(calendar_opt(cheese, cheese.max(), "тн"), "340px")

    head("Ритм выпуска по дням", "Структура товарной продукции, тн/день — именно выпуск, не остатки")
    pmap = {"Сыр": cheese, "Фета": W["p_feta"], "Масло": W["p_butter"], "ГХИ": W["p_ghi"]}
    prods_all = ["Сыр", "Фета", "Масло", "ГХИ"]
    ech({"backgroundColor": "transparent", "tooltip": {"trigger": "axis"},
         "legend": {"data": prods_all, "textStyle": {"color": MUTED}, "bottom": 0},
         "singleAxis": {"top": 20, "bottom": 40, "type": "category", "boundaryGap": False, "data": lbl,
                        "axisLabel": {"color": MUTED}, "axisLine": {"lineStyle": {"color": "#2c4437"}}},
         "color": PAL,
         "series": [{"type": "themeRiver", "label": {"show": False},
                     "data": [[d.strftime("%d.%m"), round(float(pmap[n].loc[d]), 2), n] for n in prods_all for d in
                              sel],
                     "emphasis": {"itemStyle": {"shadowBlur": 20, "shadowColor": "rgba(0,0,0,.8)"}}}]}, "300px")

    for col, (nm, k) in zip(st.columns(4), [("Сыр весовой", "p_cheese"), ("Фета", "p_feta"),
                                            ("Масло", "p_butter"), ("ГХИ", "p_ghi")]):
        with col:
            v = W[k]
            fig = go.Figure(go.Scatter(x=lbl, y=v, mode="lines", line=dict(color=GOLD, width=2),
                                       fill="tozeroy", fillcolor="rgba(216,180,90,.10)"))
            fig.update_layout(**base(130, showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False)))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption(f"{nm} · рекорд {v.max():.1f} тн ({v.idxmax():%d.%m})")
    ins([f"Выход сыра на 1 тн молока: {100 * cheese.sum() / W['milk'].sum():.2f}% — стабильность рецептуры.",
         "22.11 — неполный день: молоко 51 тн и сыр −1.3 тн (корректировка), исключён из дельт."])

# ================= ПРОДАЖИ =================
elif nav == "Продажи":
    loss = [d for d in sel if W["profit"].loc[d] < 0]
    c = st.columns(5)
    card(c[0], "Выручка", W["rev"].sum() / 1e6, "млн ₽", "Продажи, руб", "rev", 2)
    card(c[1], "Прибыль", W["profit"].sum() / 1e6, "млн ₽", "Прибыль от продаж, руб", "profit", 2)
    card(c[2], "Рентабельность", 100 * W["profit"].sum() / W["rev"].sum(), "%", "расчёт: прибыль / выручка")
    card(c[3], "Отгружено сыра", W["v_cheese"].sum(), "тн", "сыр, тн (продажи)", "v_cheese", 1)
    card(c[4], "Убыточных дней", len(loss), "дн.", "прибыль < 0")
    a, b = st.columns([1.5, 1])
    with a:
        head("Отгрузки по продуктам, тн/день", "«в т.ч.» вычтено: сыр весовой = сыр − фасованный, масло = масло − ГХИ")
        fig = go.Figure()
        for nm, y, cl in [("Сыр весовой", (W["v_cheese"] - W["v_pack"]).clip(lower=0), GOLD),
                          ("Сыр фасованный", W["v_pack"], AMBER), ("Фета", W["v_feta"], SAGE),
                          ("Масло сливочное", (W["v_butter"] - W["v_ghi"]).clip(lower=0), SKY),
                          ("ГХИ", W["v_ghi"], "#b98f2e")]:
            fig.add_trace(go.Bar(x=lbl, y=y, name=nm, marker_color=cl,
                                 hovertemplate="%{y:.1f} тн<extra>" + nm + "</extra>"))
        fig.update_layout(**base(320, barmode="stack"))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        head("Прибыль и рентабельность", f"Убыточные дни: {', '.join(d.strftime('%d.%m') for d in loss) or 'нет'}")
        fig = go.Figure()
        pos_profit = W["profit"].copy()
        neg_profit = W["profit"].copy()
        pos_profit[pos_profit < 0] = 0
        neg_profit[neg_profit >= 0] = 0
        fig.add_trace(go.Bar(x=lbl, y=pos_profit / 1000, name="Прибыль", marker_color=SAGE,
                             hovertemplate="%{y:.1f} тыс ₽<extra></extra>"))
        fig.add_trace(go.Bar(x=lbl, y=neg_profit / 1000, name="Убыток", marker_color=TERRA,
                             hovertemplate="%{y:.1f} тыс ₽<extra></extra>"))
        fig.add_trace(go.Scatter(x=lbl, y=W["margin"], name="Рентабельность, %", yaxis="y2",
                                 mode="lines+markers", line=dict(color=GOLD, width=2),
                                 hovertemplate="%{y:.1f}%<extra></extra>"))
        fig.update_layout(**base(
            320, hovermode="x unified", barmode="relative",
            margin=dict(l=8, r=8, t=8, b=46),
            legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
                        font=dict(size=11, color=CREAM)),
            yaxis2=dict(overlaying="y", side="right", showgrid=False, ticksuffix="%")))
        st.plotly_chart(fig, use_container_width=True)

    a, b = st.columns([1.5, 1])
    with a:
        head("Остатки на конец дня, тн", "Сыр весовой ~400 тн, фета растёт до 102.1 тн")
        fig = go.Figure()
        for nm, k, cl in [("Сыр весовой", "s_cheese", GOLD), ("Сыр фасованный", "s_pack", AMBER),
                          ("Фета", "s_feta", SAGE), ("Масло", "s_butter", SKY), ("ГХИ", "s_ghi", "#b98f2e")]:
            fig.add_trace(go.Scatter(x=lbl, y=W[k], name=nm, mode="lines", stackgroup="one",
                                     line=dict(width=1.5, color=cl),
                                     hovertemplate="%{y:.1f} тн<extra>" + nm + "</extra>"))
        fig.update_layout(**base(300, hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        head("Покрытие запасом, дней", f"Остаток на конец периода / средний отгруз за полный день ({rate_days} дн.)")
        cov = [("Сыр весовой", W["s_cheese"].iloc[-1], (W["v_cheese"] - W["v_pack"]).sum()),
               ("Фета", W["s_feta"].iloc[-1], W["v_feta"].sum()),
               ("Масло", W["s_butter"].iloc[-1], (W["v_butter"] - W["v_ghi"]).sum()),
               ("ГХИ", W["s_ghi"].iloc[-1], W["v_ghi"].sum())]
        names = [n for n, _, _ in cov]
        days = [round(float(s / (v / rate_days)), 1) if v > 0 else 0 for _, s, v in cov]
        max_day = max(days) if days else 10
        fig = go.Figure(go.Bar(
            x=days, y=names, orientation="h", marker_color=GOLD,
            text=[f"<b>{d} дн.</b>" for d in days], textposition="outside",
            textfont=dict(color=CREAM, size=12), cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f} дней<extra></extra>"))
        fig.update_layout(**base(
            300, showlegend=False,
            xaxis=dict(range=[0, max_day * 1.28]),
            yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)")))
        st.plotly_chart(fig, use_container_width=True)
    ins([f"Запас феты {W['s_feta'].iloc[-1]:.1f} тн при отгрузке {W['v_feta'].sum():.1f} тн — покрытие ≈ {days[1]} дней: сезон феты требует плана отгрузок.",
         "Все убыточные дни — отгрузки < 100 тыс ₽: постоянные затраты не покрываются в дни без отгрузок."])

# ================= СЫРЬЕ =================
else:
    wprice = (W["price"] * W["milk"]).sum() / W["milk"].sum()
    wprot = (W["protein"] * W["milk"]).sum() / W["milk"].sum()
    extra_t = W["milk"] * W["extra"] / 100
    c = st.columns(5)
    card(c[0], "Приёмка молока", W["milk"].sum(), "тн", "Молоко: зачетный вес, тн", "milk")
    card(c[1], "Цена средневзв.", wprice, "₽", "цена × вес / вес", "price", 2)
    card(c[2], "Доля Экстра", 100 * extra_t.sum() / W["milk"].sum(), "%", "% экстра, взвешенно по весу")
    card(c[3], "Белок средневзв.", wprot, "%", "белок × вес / вес", "protein", 2)
    card(c[4], "Не-Экстра", W["milk"].sum() - extra_t.sum(), "тн", "вес − Экстра")
    a, b = st.columns([1.5, 1])
    with a:
        head("Сортность в тоннах, тн/день", "Проценты × зачетный вес; «высший» заполнен в отчёте только 01–07.11")
        fig = go.Figure()
        for nm, y, cl in [("Экстра", extra_t, GOLD), ("Высший", W["milk"] * W["high"] / 100, SAGE),
                          ("Первый", W["milk"] * W["first"] / 100, TERRA)]:
            fig.add_trace(go.Scatter(x=lbl, y=y, name=nm, mode="lines", stackgroup="one",
                                     line=dict(width=1.5, color=cl),
                                     hovertemplate="%{y:.1f} тн<extra>" + nm + "</extra>"))
        fig.update_layout(**base(320, hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        head("Календарь приёмки", "Цвет и наведение = зачетный вес, тн/день")
        ech(calendar_opt(W["milk"], W["milk"].max(), "тн"), "320px")
    a, b = st.columns([1.5, 1])
    with a:
        head("Цена сырья зависит от сортности",
             f"corr(цена, %экстра) = {W['price'].corr(W['extra']):.2f}; размер пузыря = объём приёмки")
        fig = go.Figure(go.Scatter(x=W["extra"], y=W["price"], mode="markers", text=lbl,
                                   marker=dict(size=W["milk"], sizemode="area", sizeref=2 * W["milk"].max() / 38 ** 2,
                                               sizemin=5,
                                               color=W["extra"], colorscale=[[0, TERRA], [.5, AMBER], [1, GOLD]],
                                               opacity=.9, showscale=False),
                                   hovertemplate="<b>%{text}</b><br>Экстра: %{x:.2f}%<br>Цена: %{y:.2f} ₽<extra></extra>"))
        fig.update_layout(**base(300, xaxis=dict(title="% экстра"), yaxis=dict(title="Цена, ₽")))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        head("Цена приёмки, ₽/тн", "Минимумы совпадают с днями низкой сортности")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=lbl, y=W["price"], mode="lines", line=dict(color=GOLD, width=2), name="Цена",
            hovertemplate="%{y:.2f} ₽<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=lbl, y=W["price"], mode="markers", marker=dict(size=4, color=CREAM),
            showlegend=False, hoverinfo="skip"))
        mn, mx = W["price"].idxmin(), W["price"].idxmax()
        p_lo, p_hi = float(W["price"].min()), float(W["price"].max())
        spread = (p_hi - p_lo) or 1.0
        fig.add_trace(go.Scatter(
            x=[mn.strftime("%d.%m")], y=[W["price"].loc[mn]], mode="markers+text",
            marker=dict(size=10, color=TERRA, line=dict(color=CREAM, width=1)),
            text=[f"<b>мин {W['price'].loc[mn]:.0f}</b>"],
            textposition="bottom left" if mn == sel[0] else "bottom center",
            textfont=dict(color=TERRA, size=11), cliponaxis=False,
            showlegend=False, hovertemplate="Мин: %{y:.2f} ₽<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=[mx.strftime("%d.%m")], y=[W["price"].loc[mx]], mode="markers+text",
            marker=dict(size=10, color=SAGE, line=dict(color=CREAM, width=1)),
            text=[f"<b>макс {W['price'].loc[mx]:.0f}</b>"],
            textposition="top left" if mx == sel[-1] else "top center",
            textfont=dict(color=SAGE, size=11), cliponaxis=False,
            showlegend=False, hovertemplate="Макс: %{y:.2f} ₽<extra></extra>"))
        fig.update_layout(**base(
            300, showlegend=False,
            margin=dict(l=20, r=64, t=34, b=20),
            yaxis=dict(range=[p_lo - spread * 0.35, p_hi + spread * 0.45], gridcolor=GRID)))
        st.plotly_chart(fig, use_container_width=True)
    ins([f"Доля Экстра взвешенно по весу: {100 * extra_t.sum() / W['milk'].sum():.2f}% (сумма процентов ≠ тонны).",
         f"Минимальная цена {W['price'].min():.2f} ₽ {mn:%d.%m} — день с экстра {W['extra'].loc[mn]:.2f}%.",
         f"Белок стабилен: {W['protein'].min():.2f}–{W['protein'].max():.2f}% — сигнала не несёт, поэтому только KPI."])
