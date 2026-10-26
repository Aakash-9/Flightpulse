"""When and why: time patterns and the reasons behind lateness, for the whole country."""
import calendar

import altair as alt
import pandas as pd
import streamlit as st

import common as K
import content as C
from chatbot import CAUSE_SHORT
from store import CAUSE_KEYS

S = K.store()
nat = S.national()

K.banner("When and why", "When do flights run late, and what are the reasons?")
tab_h, tab_m, tab_y, tab_r = st.tabs(["Day and hour", "Month of the year", "Year by year", "The reasons"])

with tab_h:
    cells = []
    for r in S.temporal:
        if r["dimension"] == "WEEKDAYHOUR":
            day, hour = r["value"].split("|")
            cells.append({"Day": C.WEEKDAY_SHORT[day], "Hour": int(hour), "Late per 100": round(r["arr_delay_rate"] * 100, 1), "Flights": int(r["total_flights"])})
    big = [x for x in cells if x["Flights"] >= 20000]
    calm, rough = min(big, key=lambda x: x["Late per 100"]), max(big, key=lambda x: x["Late per 100"])
    K.answer("The calmest time to fly is <b>%s at %s</b> (about %d late per 100). The roughest is <b>%s at %s</b> (about %d per 100)." % (
        calm["Day"], C.hour_label(calm["Hour"]), round(calm["Late per 100"]), rough["Day"], C.hour_label(rough["Hour"]), round(rough["Late per 100"])))
    st.markdown("**Each square is one day and hour. Red = more late flights, green = fewer.**")
    df = pd.DataFrame([x for x in cells if x["Flights"] >= 2000])
    heat = (alt.Chart(df).mark_rect(cornerRadius=3)
            .encode(x=alt.X("Hour:O", title="Planned take-off hour (0 = midnight, 13 = 1pm)", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Day:N", sort=C.WEEKDAY_ORDER, title=None),
                    color=alt.Color("Late per 100:Q", scale=alt.Scale(scheme="redyellowgreen", reverse=True), legend=alt.Legend(title="Late per 100")),
                    tooltip=["Day", "Hour", "Late per 100", "Flights"]).properties(height=300))
    st.altair_chart(heat, width="stretch")
    st.info("In this data, evening flights are late more often than morning flights. One common idea is that small delays pile up as the day goes on, "
            "but these numbers show the pattern, not the reason.")
    K.careful("Times are each airport's local clock. Squares with fewer than 2,000 flights are left blank.")

with tab_m:
    months = sorted((r for r in S.causes_rows if r["dimension"] == "MONTHOFYEAR"), key=lambda r: r["value"])
    top = max(months, key=lambda m: m["delayed_15plus_rate"])
    low = min(months, key=lambda m: m["delayed_15plus_rate"])
    K.answer("<b>%s</b> has the most late flights (about %s in 100) and <b>%s</b> the fewest (about %s in 100)." % (
        calendar.month_name[int(top["value"])], C.per100_value(top["delayed_15plus_rate"]),
        calendar.month_name[int(low["value"])], C.per100_value(low["delayed_15plus_rate"])))
    mdf = pd.DataFrame({"Month": [C.MONTH_NAMES[m["value"]] for m in months], "Late per 100": [round(m["delayed_15plus_rate"] * 100, 1) for m in months]})
    K.vbar(mdf, "Month", "Late per 100", "Late per 100 flights that flew", K.RED, order=list(C.MONTH_NAMES.values()), fmt=".1f")
    K.careful("All years are added together, and 2020's quiet spring lowers April and May a lot.")

with tab_y:
    years = sorted((r for r in S.causes_rows if r["dimension"] == "YEAR"), key=lambda r: r["value"])
    ydf = pd.DataFrame({"Year": [y["value"] for y in years],
                        "Late per 100 flights that flew": [round(y["delayed_15plus_rate"] * 100, 1) for y in years],
                        "Cancelled per 100 planned": [round(y["cancellation_rate"] * 100, 1) for y in years]})
    K.answer("2020 stands out: flights were late less often but <b>cancelled far more often</b>. After that, lateness climbed back up as air travel recovered.")
    l, r_ = st.columns(2)
    with l:
        st.markdown("**Late flights, year by year**")
        K.vbar(ydf, "Year", "Late per 100 flights that flew", "Late per 100", K.RED, fmt=".1f")
    with r_:
        st.markdown("**Cancelled flights, year by year**")
        K.vbar(ydf, "Year", "Cancelled per 100 planned", "Cancelled per 100", K.AMBER, fmt=".1f")
    K.careful("2025 only has January to June.")

with tab_r:
    scope = st.radio("Which years?", ["All years"] + [str(y) for y in range(2020, 2026)], horizontal=True)
    r = nat if scope == "All years" else S.causes[("YEAR", scope)]
    order = sorted(CAUSE_KEYS, key=lambda k: -r["share_" + k])
    K.answer("Of all the minutes of lateness, <b>%d%%</b> came from <b>%s</b> and <b>%d%%</b> from <b>%s</b>." % (
        round(r["share_" + order[0]] * 100), CAUSE_SHORT[order[0]], round(r["share_" + order[1]] * 100), CAUSE_SHORT[order[1]]))
    df = pd.DataFrame({"Reason": [CAUSE_SHORT[k].capitalize() for k in order], "Share of lateness (%)": [round(r["share_" + k] * 100, 1) for k in order]})
    K.hbar(df, "Reason", "Share of lateness (%)", "Share of all minutes of lateness (%)", K.RED, fmt=".0f", height=260)
    for k, label, text in C.CAUSES:
        st.markdown("- **%s:** %s" % (label, text))
    st.markdown("### Why do flights get cancelled?")
    cc = pd.DataFrame({"Reason": [lab for _, lab in C.CANCEL_REASONS], "Cancelled flights": [int(r["cancel_code_" + k]) for k, _ in C.CANCEL_REASONS]})
    K.hbar(cc, "Reason", "Cancelled flights", "Number of cancelled flights", K.AMBER, fmt=",.0f", height=220)
    if scope in ("All years", "2020"):
        st.info(C.CANCEL_D_CAUTION)
    K.careful("These reasons are what the airlines reported. They are not an independent check, and \"the plane arrived late\" does not say why that earlier flight was late.")
K.grownup("Sources: `TemporalMetricsJob` (key WEEKDAYHOUR, 168 cells) and `DelayCauseMetricsJob` (rows MONTHOFYEAR, YEAR, ALL). The planned departure hour is a DERIVED "
          "field: this dataset has no scheduled-time column, so the job subtracts the departure delay from the actual departure time. 'Calmest/roughest' only "
          "considers squares with at least 20,000 flights. Reasons exist only for flights arriving 15+ minutes late; shares are by minutes, not number of flights.")
