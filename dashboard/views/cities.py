"""Cities: which cities have the most delay, and a full one-city view."""
import pandas as pd
import streamlit as st

import advice
import common as K
import content as C
from chatbot import CAUSE_SHORT, Entity
from store import CANCEL_KEYS, CAUSE_KEYS, combine

S, B, P = K.store(), K.bot(), K.store().places
nat = S.national()

K.banner("Cities", "Which cities have the most delay, and why?")
tab_rank, tab_one = st.tabs(["Which cities have the most trouble?", "Look at one city"])

# ------------------------------------------------------------------ ranking
with tab_rank:
    c1, c2, c3, c4 = st.columns(4)
    what = c1.radio("Look at", ["Late flights", "Cancelled flights", "Flights sent to another airport"])
    reasons = {"Any reason": None}
    reasons.update({CAUSE_SHORT[k].capitalize(): k for k in ("weather", "nas", "carrier", "late_aircraft", "security")})
    if what != "Late flights":
        reasons = {k: v for k, v in reasons.items() if v != "late_aircraft"}
    if what == "Flights sent to another airport":
        reasons = {"Any reason": None}
    reason = c2.selectbox("Because of", list(reasons))
    by = c3.radio("Rank by", ["Number of flights", "Share (out of every 100 flights)"])
    year = c4.selectbox("Year", ["All years"] + [str(y) for y in range(2020, 2026)])
    ans = B.rank_answer("city", reasons[reason], what == "Cancelled flights", what.startswith("Flights sent"), False,
                        by.startswith("Share"), None if year == "All years" else year)
    K.render_answer(ans)
    st.info("Big airports have the most late flights simply because they have the most flights. Switch to **Share** to see which cities "
            "are worst for their size.")

# ------------------------------------------------------------------ one city
with tab_one:
    opts = K.city_options()
    labels = [l for l, _ in opts]
    default = labels.index("Atlanta, Georgia") if "Atlanta, Georgia" in labels else 0
    choice = st.selectbox("Pick a city", labels, index=default)
    codes = dict(opts)[choice]
    name = P.city(codes[0])
    if len(codes) > 1:
        st.caption("Includes all its airports: " + ", ".join(P.airport(c) for c in codes) + ".")
    side_label = st.radio("Look at flights", ["leaving this city", "arriving at this city"], horizontal=True)
    side = "origin" if side_label.startswith("leaving") else "dest"
    row = S.place_row(codes, side)
    if not row:
        st.info("No flight data for this city.")
        st.stop()
    verb = "leaving" if side == "origin" else "arriving at"
    diff = row["delayed_15plus_rate"] - nat["delayed_15plus_rate"]
    verdict = "about the same as" if abs(diff) < 0.01 else ("worse than" if diff > 0 else "better than")
    K.answer("Of flights %s <b>%s</b>, about <b>%s out of every 100</b> arrived 15 or more minutes late. That is <b>%s</b> the whole country (%s out of 100)." % (
        verb, name, C.per100_value(row["delayed_15plus_rate"]), verdict, C.per100_value(nat["delayed_15plus_rate"])))
    a, b, c, d = st.columns(4)
    K.bignum(a, C.big_count(row["n_flights_scheduled"]), "flights planned")
    K.bignum(b, C.per100_value(row["delayed_15plus_rate"]), "late, per 100 that flew", K.RED)
    K.bignum(c, C.per100_value(row["cancellation_rate"]), "cancelled, per 100 planned", K.AMBER)
    K.bignum(d, C.per100_value(row["diversion_rate"]), "sent elsewhere, per 100", K.GREY)

    # ---- why late
    st.markdown("### Why flights %s %s are late" % (verb, name))
    order = sorted(CAUSE_KEYS, key=lambda k: -row["share_" + k])
    df = pd.DataFrame([{"Reason": CAUSE_SHORT[k].capitalize(), "Where": name if w == "city" else "Whole country",
                        "Share of all lateness (%)": round((row if w == "city" else nat)["share_" + k] * 100, 1)}
                       for k in order for w in ("city", "country")])
    K.grouped_hbar(df, "Reason", "Share of all lateness (%)", "Where", {name: K.RED, "Whole country": K.GREY},
                   "Share of all minutes of lateness (%)", fmt=".0f")
    late = row["n_delayed_15plus"]
    tbl = pd.DataFrame([{"Reason": CAUSE_SHORT[k].capitalize(),
                         "Late flights where this was a reason": int(row["flights_" + k]),
                         "Out of every 100 late flights here": round(row["flights_" + k] / late * 100, 1) if late else 0,
                         "Whole country": round(nat["flights_" + k] / nat["n_delayed_15plus"] * 100, 1)} for k in order])
    K.table(tbl)
    st.caption("A late flight can have more than one reason, so each column can add up to more than 100. About weather: the airlines list only "
               "**extreme** weather (storms, snow, hurricanes) under weather; ordinary bad weather and its knock-on effects are counted under "
               "\"busy skies and airport operations\".")

    # ---- cancellations
    st.markdown("### Why flights get cancelled here")
    cdf = pd.DataFrame({"Reason": [lab for _, lab in C.CANCEL_REASONS],
                        "Cancelled flights": [int(row["cancel_code_" + k]) for k in CANCEL_KEYS]})
    K.hbar(cdf, "Reason", "Cancelled flights", "Cancelled flights", K.AMBER, fmt=",.0f", height=220)
    st.caption(C.CANCEL_D_CAUTION)

    # ---- routes
    st.markdown("### Which routes add to the delay")
    rts = []
    for cd in codes:
        rts += S.routes_from(cd) if side == "origin" else S.routes_to(cd)
    rts = [r for r in rts if r["n_operated"] >= 500]
    for r in rts:
        r["_late"] = r["n_delayed_15plus"]
    rts.sort(key=lambda r: -r["_late"])
    top = rts[:12]
    if top:
        rdf = pd.DataFrame([{
            "Route": ("to " if side == "origin" else "from ") + P.label(r["route"].split("-")[1 if side == "origin" else 0]),
            "Main reason": CAUSE_SHORT[max(CAUSE_KEYS, key=lambda k: r["share_" + k])].capitalize(),
            "Late flights": int(r["_late"]),
            "Late per 100": round(r["delayed_15plus_rate"] * 100, 1),
            "Share of all late (%)": round(r["_late"] / late * 100, 1) if late else 0} for r in top])
        K.hbar(rdf.head(8), "Route", "Late flights", "Late flights on this route", K.RED, fmt=",.0f")
        K.table(rdf)
        st.caption("Routes are listed by how many late flights they add. A busy route can add many late flights even when most of its "
                   "flights are on time, so check the \"Late per 100\" column too. \"Share of all late\" is the part of this city's late flights that this route adds.")
    else:
        st.info("Not enough flights on individual routes to list.")

    # ---- airlines at this city (leaving only)
    if side == "origin":
        st.markdown("### Which airlines do best and worst here")
        per = {}
        for cd in codes:
            for r in S.airlines_at(cd, 2000):
                per.setdefault(r["carrier"], []).append(r)
        al = sorted(((c, combine(rs)) for c, rs in per.items()), key=lambda t: -t[1]["n_operated"])[:8]
        if al:
            adf = pd.DataFrame([{"Airline": S.airline_label(c), "Late per 100": round(r["delayed_15plus_rate"] * 100, 1),
                                 "Cancelled per 100": round(r["cancellation_rate"] * 100, 1), "Flights": int(r["n_operated"])} for c, r in al])
            K.hbar(adf, "Airline", "Late per 100", "Late per 100 flights that flew", K.RED, fmt=".1f")
            K.table(adf)

    # ---- carryover
    st.markdown("### Do late planes pass their lateness on here?")
    crow, _ = B.carryover_for(Entity("place", name, codes))
    ncar = S.carryover_row("ALL")
    if crow:
        a, b = st.columns(2)
        K.card(a, "%s in 100" % C.per100_value(crow["p_b_late15_given_a_late15"]), "next trips leave late after a plane lands LATE here",
               "Across the whole country it is %s in 100. On-time landings here: only %s in 100." % (
                   C.per100_value(ncar["p_b_late15_given_a_late15"]), C.per100_value(crow["p_b_late15_given_a_not_late15"])), K.RED)
        K.card(b, "%.1f min" % crow["mean_carryover_min"],
               "lateness passed on, on average", "Across the whole country: %.1f minutes. This counts planes that stop here between flights." % ncar["mean_carryover_min"], K.AMBER)
    else:
        st.info("Not enough planes stop here between flights to say.")

    # ---- year by year (leaving only)
    if side == "origin":
        st.markdown("### Year by year")
        yrs = []
        for y in range(2020, 2026):
            r = S.place_row(codes, "origin", str(y))
            if r:
                yrs.append({"Year": str(y), "Late per 100 flights that flew": round(r["delayed_15plus_rate"] * 100, 1),
                            "Cancelled per 100 planned": round(r["cancellation_rate"] * 100, 1)})
        if yrs:
            ydf = pd.DataFrame(yrs)
            l, r_ = st.columns(2)
            with l:
                K.vbar(ydf, "Year", "Late per 100 flights that flew", "Late per 100", K.RED, fmt=".1f")
            with r_:
                K.vbar(ydf, "Year", "Cancelled per 100 planned", "Cancelled per 100", K.AMBER, fmt=".1f")
            st.caption("2020 was the COVID year, and 2025 only covers January to June.")

    # ---- ideas
    K.ideas_block(advice.city_ideas(S, codes, row), "this city")
    K.grownup("Sources: `DelayCauseMetricsJob` (rows ORIGIN, DEST, ORIGINYEAR, ROUTE, CARRIERORIGIN) and `CarryoverAnalysisJob` (row AIRPORT = the airport where "
              "a late plane lands before its next trip). Cities with several airports add up the Hadoop counts and recompute the ratios. "
              "Route lists need at least 500 flights flown.")
