"""Shared pieces for every FlightPulse page: cached data, styling and chart helpers."""
import os

import altair as alt
import pandas as pd
import streamlit as st

import content as C
from chatbot import Bot, Chart
from store import Store

HERE = os.path.dirname(os.path.abspath(__file__))
RED, GREEN, BLUE, GREY, AMBER, NAVY = "#d64545", "#2e9d5b", "#2f6fd0", "#8a8f98", "#e09a2b", "#16315f"

CSS = """
<style>
.block-container {padding-top: 3.2rem; max-width: 1280px;}
#MainMenu, footer {visibility: hidden;}
[data-testid="stSidebar"] {background: #eef3fc;}
[data-testid="stSidebarNav"] a span {font-size: 1.04rem;}
.banner {background: linear-gradient(120deg, #16315f 0%, #2b5cb8 62%, #3b8fd9 100%); color: #fff;
         padding: 22px 28px; border-radius: 16px; margin-bottom: 16px;}
.banner .bt {font-size: 2.1rem; font-weight: 800; letter-spacing: .3px; line-height: 1.15;}
.banner .bs {font-size: 1.15rem; opacity: .96; margin-top: 6px;}
.answer {font-size: 1.32rem; line-height: 1.5; padding: .95rem 1.2rem; margin: .25rem 0 1rem 0;
         border-left: 8px solid #2f6fd0; background: #f1f6ff; border-radius: 10px; color: #111;}
.fcard {background: #fff; border: 1px solid #dfe6f3; border-radius: 14px; padding: 16px 18px; min-height: 205px;
        box-shadow: 0 2px 8px rgba(20,40,90,.07);}
h3 {padding-top: 1.2rem !important;}
.fnum {font-size: 2.2rem; font-weight: 800; line-height: 1.05;}
.ftitle {font-size: 1.08rem; font-weight: 650; margin: .35rem 0 .3rem 0; color: #16315f;}
.fmore {font-size: .96rem; color: #43506a; line-height: 1.45;}
.step {background: #fff; border: 1px solid #dfe6f3; border-radius: 14px; padding: 14px 16px; height: 100%;}
.step b {color: #2f6fd0;}
.tip {background: #fff; border: 1px solid #dfe6f3; border-left: 6px solid #2e9d5b; border-radius: 12px;
      padding: 12px 16px; margin-bottom: 10px;}
.tip .tt {font-weight: 700; color: #16315f; font-size: 1.05rem;}
.tip .tw {color: #43506a; margin-top: 4px;}
.tip .ti {margin-top: 6px;}
.badge {display: inline-block; font-size: .78rem; font-weight: 700; padding: 2px 9px; border-radius: 999px;
        color: #fff; margin-left: 8px; vertical-align: middle;}
.bignum {font-size: 2.3rem; font-weight: 800; line-height: 1.1;}
.bigcap {font-size: 1.0rem; color: #43506a;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def store():
    return Store()


@st.cache_resource
def bot():
    return Bot(store())


@st.cache_data
def load_csv(name):
    return pd.read_csv(os.path.join(C.DATA_DIR, name), keep_default_na=False)


# ---------------------------------------------------------------- text blocks
def banner(title, sub=""):
    st.markdown('<div class="banner"><div class="bt">%s</div><div class="bs">%s</div></div>' % (title, sub), unsafe_allow_html=True)


def answer(text):
    st.markdown('<div class="answer">%s</div>' % text, unsafe_allow_html=True)


def careful(text):
    st.warning("Be careful: " + text)


def bignum(col, number, caption, color=BLUE):
    col.markdown('<div class="bignum" style="color:%s">%s</div><div class="bigcap">%s</div>' % (color, number, caption),
                 unsafe_allow_html=True)


def card(col, big, title, more, color=RED):
    col.markdown('<div class="fcard"><div class="fnum" style="color:%s">%s</div><div class="ftitle">%s</div>'
                 '<div class="fmore">%s</div></div>' % (color, big, title, more), unsafe_allow_html=True)


def grownup(md):
    if st.session_state.get("details"):
        with st.expander("Grown-up details", expanded=True):
            st.markdown(md)


EVIDENCE_COLOR = {"RESEARCH": GREEN, "MIXED": AMBER, "PRACTICE": GREY}


def ideas_block(ideas, what):
    """Render the 'what could help' cards produced by advice.py."""
    import advice
    st.markdown("### What could help %s" % what)
    if not ideas:
        st.info("Nothing stands out as clearly worse than the national pattern, so the numbers do not point to one thing to fix.")
        return
    for i in ideas:
        st.markdown(
            '<div class="tip"><div class="tt">%s<span class="badge" style="background:%s">%s</span></div>'
            '<div class="tw"><b>What the numbers show:</b> %s</div><div class="ti"><b>An idea:</b> %s</div></div>'
            % (i["title"], EVIDENCE_COLOR[i["evidence"]], advice.EVIDENCE[i["evidence"]], i["why"], i["idea"]),
            unsafe_allow_html=True)
    st.caption("These are ideas to look into, not proven fixes. This data shows where and why delays happen; it cannot show what would work.")
    with st.expander("Where these ideas come from"):
        for what_, title, url in advice.SOURCES:
            st.markdown("- %s: [%s](%s)" % (what_, title, url))


# ---------------------------------------------------------------- charts
def _soft(hex_color, amount=0.55):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: int(c + (255 - c) * (1 - amount))
    return "#%02x%02x%02x" % (mix(r), mix(g), mix(b))


def hbar(df, label, value, title, color=RED, fmt=".0f", height=None, highlight=None):
    """Horizontal bars with the number written on each bar; `highlight` = row positions drawn in full colour."""
    df = df.copy()
    df["_hl"] = [1 if (highlight is None or i in highlight or not highlight) else 0 for i in range(len(df))]
    h = height or max(190, 38 * len(df) + 40)
    base = alt.Chart(df).encode(y=alt.Y(label + ":N", sort="-x", title=None,
                                        axis=alt.Axis(labelFontSize=13, labelLimit=420, domain=False, ticks=False)))
    bars = base.mark_bar(cornerRadiusEnd=4, size=22).encode(
        x=alt.X(value + ":Q", title=title, axis=alt.Axis(grid=False)),
        color=alt.condition(alt.datum._hl == 1, alt.value(color), alt.value(_soft(color))),
        tooltip=[c for c in df.columns if c != "_hl"])
    text = base.mark_text(align="left", dx=5, fontSize=13, fontWeight="bold").encode(
        x=alt.X(value + ":Q"), text=alt.Text(value + ":Q", format=fmt))
    st.altair_chart((bars + text).properties(height=h), width="stretch")


def vbar(df, label, value, title, color=RED, order=None, fmt=".0f", height=300, highlight=None):
    df = df.copy()
    df["_hl"] = [1 if (highlight is None or i in highlight or not highlight) else 0 for i in range(len(df))]
    base = alt.Chart(df).encode(x=alt.X(label + ":N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13, labelLimit=140)))
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y(value + ":Q", title=title, axis=alt.Axis(grid=False)),
        color=alt.condition(alt.datum._hl == 1, alt.value(color), alt.value(_soft(color))),
        tooltip=[c for c in df.columns if c != "_hl"])
    text = base.mark_text(dy=-8, fontSize=13, fontWeight="bold").encode(y=alt.Y(value + ":Q"), text=alt.Text(value + ":Q", format=fmt))
    st.altair_chart((bars + text).properties(height=height), width="stretch")


def render_chart(ch: Chart):
    df = pd.DataFrame({"Name": ch.labels, ch.value_title: ch.values})
    if ch.title:
        st.markdown("**%s**" % ch.title)
    if ch.kind == "vbar":
        vbar(df, "Name", ch.value_title, ch.value_title, ch.color, order=list(ch.labels), fmt=ch.fmt, highlight=ch.highlight)
    else:
        hbar(df, "Name", ch.value_title, ch.value_title, ch.color, fmt=ch.fmt, highlight=ch.highlight)


def render_answer(ans):
    """Answer sentences first, then the chart, then the small print (paragraphs written in italics)."""
    paras = ans.text.split("\n\n")
    main = [p for p in paras if not p.startswith("_")]
    notes = [p for p in paras if p.startswith("_")]
    st.markdown("\n\n".join(main))
    if ans.chart:
        render_chart(ans.chart)
    for n in notes:
        st.caption(n.strip("_"))
    if ans.sources:
        st.caption("Where this comes from: " + "; ".join(ans.sources))


# ---------------------------------------------------------------- lists and grouped charts
@st.cache_data
def city_options(min_total=3000):
    """[(label, [airport codes])] for every city with enough flights, busiest first. Cities with several
    airports are combined (Chicago = O'Hare + Midway) and labelled so."""
    S = store()
    P = S.places
    opts = []
    for key, codes in P.groups.items():
        use = [c for c in codes if P.info[c]["departures"] >= 1000] or codes[:1]
        total = sum(P.info[c]["departures"] for c in codes)
        if total < min_total:
            continue
        label = P.city(use[0]) + (" (all %d airports)" % len(use) if len(use) > 1 else "")
        opts.append((total, label, use))
    opts.sort(reverse=True)
    return [(label, use) for _, label, use in opts]


def grouped_hbar(df, label, value, series, colors, title, height=None, fmt=".0f"):
    """Side-by-side horizontal bars: `series` column picks the colour (e.g. this city vs the whole country)."""
    h = height or max(220, 30 * len(df) + 50)
    order = list(dict.fromkeys(df[label]))
    base = alt.Chart(df).encode(y=alt.Y(label + ":N", sort=order, title=None, axis=alt.Axis(labelFontSize=13, labelLimit=420)),
                                yOffset=alt.YOffset(series + ":N"))
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X(value + ":Q", title=title, axis=alt.Axis(grid=False)),
        color=alt.Color(series + ":N", scale=alt.Scale(domain=list(colors), range=list(colors.values())), legend=alt.Legend(title=None, orient="top")),
        tooltip=list(df.columns))
    text = base.mark_text(align="left", dx=4, fontSize=12).encode(x=alt.X(value + ":Q"), text=alt.Text(value + ":Q", format=fmt))
    st.altair_chart((bars + text).properties(height=h), width="stretch")


AIRLINE_COLORS = ["#2f6fd0", "#8e6cd1", "#1aa6a6", "#e09a2b", "#7a8699", "#c2578a", "#4c9f38"]


def table(df, **kw):
    """Show a result table with thousands separators on whole-number columns."""
    cfg = {c: st.column_config.NumberColumn(format="localized") for c in df.columns if pd.api.types.is_integer_dtype(df[c])}
    cfg.update({c: st.column_config.NumberColumn(format="%.1f") for c in df.columns if pd.api.types.is_float_dtype(df[c])})
    kw.setdefault("height", min(35 * (len(df) + 1) + 3, 740))
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg, **kw)
