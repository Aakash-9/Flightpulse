"""Routes: which routes run late, and a one-route view (also the 'plan my trip' helper)."""
import pandas as pd
import streamlit as st

import common as K
import content as C
from chatbot import CAUSE_SHORT, Entity
from store import CAUSE_KEYS

S, B, P = K.store(), K.bot(), K.store().places
nat = S.national()

K.banner("Routes", "Which trips run late, and what should I pick for mine?")
tab_rank, tab_one = st.tabs(["Which routes run late the most?", "Look at one route"])

with tab_rank:
    c1, c2, c3 = st.columns(3)
    by = c1.radio("Rank by", ["Number of late flights", "Share (out of every 100 flights)"])
    reasons = {"Any reason": None}
    reasons.update({CAUSE_SHORT[k].capitalize(): k for k in ("weather", "nas", "carrier", "late_aircraft", "security")})
    reason = c2.selectbox("Because of", list(reasons))
    opts = K.city_options()
    city = c3.selectbox("Only routes leaving", ["Anywhere"] + [l for l, _ in opts])
    within = None if city == "Anywhere" else Entity("place", P.city(dict(opts)[city][0]), dict(opts)[city])
    ans = B.rank_answer("route", reasons[reason], False, False, False, by.startswith("Share"), None, within=within)
    K.render_answer(ans)
    K.careful("A route is one direction: New York to Los Angeles can behave differently from Los Angeles to New York. "
              "Routes with few flights are left out of the \"share\" ranking because they can look extreme by luck.")

with tab_one:
    pairs = {}
    for (dim, val), r in S.causes.items():
        if dim == "ROUTE" and r["n_operated"] >= 1000:
            o, d = val.split("-")
            pairs.setdefault(o, {})[d] = r["n_flights_scheduled"]
    origins = sorted(pairs, key=lambda o: -sum(pairs[o].values()))
    col1, col2 = st.columns(2)
    o_def = origins.index("JFK") if "JFK" in origins else 0
    origin = col1.selectbox("Flying from", origins, index=o_def, format_func=P.label)
    dests = sorted(pairs[origin], key=lambda d: -pairs[origin][d])
    d_def = dests.index("LAX") if "LAX" in dests else 0
    dest = col2.selectbox("Flying to", dests, index=d_def, format_func=P.label)
    route = "%s-%s" % (origin, dest)
    row = S.route_row(route)
    name = P.route(origin, dest)

    diff = row["delayed_15plus_rate"] - nat["delayed_15plus_rate"]
    verdict = "about the same as" if abs(diff) < 0.01 else ("worse than" if diff > 0 else "better than")
    K.answer("On <b>%s</b>, about <b>%s out of every 100</b> flights arrived 15 or more minutes late. That is <b>%s</b> the whole country (%s out of 100)." % (
        name, C.per100_value(row["delayed_15plus_rate"]), verdict, C.per100_value(nat["delayed_15plus_rate"])))
    a, b, c, d = st.columns(4)
    K.bignum(a, C.big_count(row["n_flights_scheduled"]), "flights planned")
    K.bignum(b, C.per100_value(row["delayed_15plus_rate"]), "late, per 100 that flew", K.RED)
    K.bignum(c, C.per100_value(row["cancellation_rate"]), "cancelled, per 100 planned", K.AMBER)
    K.bignum(d, "%d min" % round(row["mean_enroute_gain_min"]), "caught up in the air, on average", K.GREEN)

    st.markdown("### Why flights on this route are late")
    order = sorted(CAUSE_KEYS, key=lambda k: -row["share_" + k])
    df = pd.DataFrame([{"Reason": CAUSE_SHORT[k].capitalize(), "Where": "This route" if w == "r" else "Whole country",
                        "Share of all lateness (%)": round((row if w == "r" else nat)["share_" + k] * 100, 1)} for k in order for w in ("r", "c")])
    K.grouped_hbar(df, "Reason", "Share of all lateness (%)", "Where", {"This route": K.RED, "Whole country": K.GREY},
                   "Share of all minutes of lateness (%)")
    st.caption("Late planes arriving from earlier trips and busy skies at either end are the usual reasons. Weather means extreme weather only.")

    st.markdown("### Which airline, and what time of day?")
    rc = sorted([r for r in S.route_carrier if r["kind"] == "RC" and r["route"] == route and r["total_flights"] >= 300], key=lambda r: r["arr_delay_rate"])
    bands = sorted([r for r in S.route_carrier if r["kind"] == "RCB" and r["route"] == route and r["total_flights"] >= 1000], key=lambda r: r["arr_delay_rate"])
    if rc:
        solid = [r for r in rc if r["total_flights"] >= 1000] or rc
        best = solid[0]
        x, y, z = st.columns(3)
        K.card(x, "%s in 100" % C.per100_value(best["arr_delay_rate"]), "late, with %s" % S.airline_label(best["carrier"]),
               "Best airline here, from %s flights." % C.big_count(best["total_flights"]), K.GREEN)
        if bands:
            g, w = bands[0], bands[-1]
            K.card(y, "%s in 100" % C.per100_value(g["arr_delay_rate"]), "late: %s, %s" % (S.airline_label(g["carrier"]), C.BAND_LABEL[g["band"]].split(" (")[0].lower()),
                   "Best airline-and-time combination (%s flights)." % C.big_count(g["total_flights"]), K.GREEN)
            K.card(z, "%s in 100" % C.per100_value(w["arr_delay_rate"]), "late: %s, %s" % (S.airline_label(w["carrier"]), C.BAND_LABEL[w["band"]].split(" (")[0].lower()),
                   "Combination to avoid (%s flights)." % C.big_count(w["total_flights"]), K.RED)
        adf = pd.DataFrame({"Airline": [S.airline_label(r["carrier"]) for r in rc],
                            "Late per 100": [round(r["arr_delay_rate"] * 100, 1) for r in rc],
                            "Cancelled per 100": [round(r["cancellation_rate"] * 100, 1) for r in rc],
                            "Flights we saw": [int(r["total_flights"]) for r in rc]})
        st.write("")
        K.hbar(adf, "Airline", "Late per 100", "Late per 100 flights that flew", K.RED, fmt=".1f", height=max(160, 40 * len(adf)))
        K.table(adf)
        allb = [r for r in S.route_carrier if r["kind"] == "RCB" and r["route"] == route and r["total_flights"] >= 300]
        if allb:
            import altair as alt
            bdf = pd.DataFrame({"Airline": [S.airline_label(r["carrier"]) for r in allb], "Time of day": [C.BAND_LABEL[r["band"]].split(" (")[0] for r in allb],
                                "Late per 100": [round(r["arr_delay_rate"] * 100, 1) for r in allb], "Flights we saw": [int(r["total_flights"]) for r in allb]})
            chart = (alt.Chart(bdf).mark_bar(cornerRadiusEnd=3)
                     .encode(x=alt.X("Time of day:N", sort=[C.BAND_LABEL[x_].split(" (")[0] for x_ in C.BAND_ORDER], title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13)),
                             y=alt.Y("Late per 100:Q", axis=alt.Axis(grid=False)),
                             color=alt.Color("Airline:N", scale=alt.Scale(range=K.AIRLINE_COLORS)), xOffset="Airline:N",
                             tooltip=list(bdf.columns)).properties(height=320))
            st.markdown("**Late flights per 100, by airline and time of day**")
            st.altair_chart(chart, width="stretch")
            st.caption("Morning = 5am to noon, Afternoon = noon to 5pm, Evening = 5pm to 10pm, Night = 10pm to 5am (planned take-off time).")
    else:
        st.info("Not enough flights on this route to compare airlines fairly (we need at least 300 per airline).")
    K.careful("This is how the route went from 2020 to mid-2025. It is a hint, not a promise about your flight. Picks need at least 1,000 flights.")
    K.grownup("Sources: `DelayCauseMetricsJob` (row ROUTE) and `RouteCarrierMetricsJob` (rows RC / RCB). Time-of-day bands use the planned take-off hour, "
              "a derived field. Cancellation rates are not shown by time of day because cancelled flights have no recorded times.")
