"""Airlines: all airlines compared, and a one-airline view with ideas."""
import pandas as pd
import streamlit as st

import advice
import common as K
import content as C
from chatbot import CAUSE_SHORT
from store import CAUSE_KEYS

S, P = K.store(), K.store().places
nat = S.national()
ncar = S.carryover_row("ALL")

K.banner("Airlines", "Which airline does what, why, and what could they do about it?")
tab_all, tab_one = st.tabs(["All airlines compared", "Look at one airline"])

with tab_all:
    rows = [S.airline_row(c) | {"carrier": c} for c in S.carriers_in_data()]
    rows = [r for r in rows if r["n_operated"] >= 20000]
    big = sorted([r for r in rows if r["n_operated"] >= 250000], key=lambda r: r["delayed_15plus_rate"])
    K.answer("Among the big airlines (at least 250,000 flights), <b>%s</b> was late least often (about %s in 100) and <b>%s</b> most often (about %s in 100)." % (
        S.airline_label(big[0]["carrier"]), C.per100_value(big[0]["delayed_15plus_rate"]),
        S.airline_label(big[-1]["carrier"]), C.per100_value(big[-1]["delayed_15plus_rate"])))
    df = pd.DataFrame({
        "Airline": [S.airline_label(r["carrier"]) for r in rows],
        "Late per 100": [round(r["delayed_15plus_rate"] * 100, 1) for r in rows],
        "Cancelled per 100": [round(r["cancellation_rate"] * 100, 1) for r in rows],
        "Next trip late after a late landing (per 100)": [
            round((S.carryover_row("CARRIER", r["carrier"]) or {"p_b_late15_given_a_late15": float("nan")})["p_b_late15_given_a_late15"] * 100, 1) for r in rows],
        "Biggest reason for lateness": [CAUSE_SHORT[max(CAUSE_KEYS, key=lambda k: r["share_" + k])].capitalize() for r in rows],
        "Flights": [int(r["n_operated"]) for r in rows]}).sort_values("Late per 100")
    K.hbar(df[df["Flights"] >= 250000], "Airline", "Late per 100", "Late per 100 flights that flew (airlines with at least 250,000 flights)", K.RED, fmt=".1f")
    st.markdown("**Every airline in the data**, smallest-trouble first. Airlines with fewer than 250,000 flights are in the table only, because a short or quiet history makes them look better or worse than they were.")
    K.table(df)
    K.careful("Airlines fly different routes in different weather, so this is not a fair contest. Some airlines flew for only part of this time "
              "(for example in 2020, when skies were almost empty), which flatters them. That is why the headline only compares big airlines.")

with tab_one:
    codes = [r["carrier"] for r in rows]
    names = {S.airline_label(c): c for c in codes}
    labels = list(names)
    default = labels.index("Delta Air Lines") if "Delta Air Lines" in labels else 0
    pick = st.selectbox("Pick an airline", labels, index=default)
    code = names[pick]
    row = S.airline_row(code)
    diff = row["delayed_15plus_rate"] - nat["delayed_15plus_rate"]
    verdict = "about the same as" if abs(diff) < 0.01 else ("worse than" if diff > 0 else "better than")
    K.answer("Of flights flown by <b>%s</b>, about <b>%s out of every 100</b> arrived 15 or more minutes late. That is <b>%s</b> the whole country (%s out of 100)." % (
        pick, C.per100_value(row["delayed_15plus_rate"]), verdict, C.per100_value(nat["delayed_15plus_rate"])))
    a, b, c, d = st.columns(4)
    K.bignum(a, C.big_count(row["n_operated"]), "flights flown")
    K.bignum(b, C.per100_value(row["delayed_15plus_rate"]), "late, per 100 that flew", K.RED)
    K.bignum(c, C.per100_value(row["cancellation_rate"]), "cancelled, per 100 planned", K.AMBER)
    K.bignum(d, "%d min" % round(row["mean_enroute_gain_min"]), "caught up in the air, on average", K.GREEN)

    st.markdown("### Why %s flights are late" % pick)
    order = sorted(CAUSE_KEYS, key=lambda k: -row["share_" + k])
    gdf = pd.DataFrame([{"Reason": CAUSE_SHORT[k].capitalize(), "Where": pick if w == "a" else "Whole country",
                         "Share of all lateness (%)": round((row if w == "a" else nat)["share_" + k] * 100, 1)} for k in order for w in ("a", "c")])
    K.grouped_hbar(gdf, "Reason", "Share of all lateness (%)", "Where", {pick: K.RED, "Whole country": K.GREY}, "Share of all minutes of lateness (%)")

    st.markdown("### Does a late plane pass its lateness on?")
    cr = S.carryover_row("CARRIER", code)
    if cr:
        x, y = st.columns(2)
        K.card(x, "%s in 100" % C.per100_value(cr["p_b_late15_given_a_late15"]), "next trips leave late after a LATE landing",
               "Whole country: %s in 100. After an on-time landing: only %s in 100." % (
                   C.per100_value(ncar["p_b_late15_given_a_late15"]), C.per100_value(cr["p_b_late15_given_a_not_late15"])), K.RED)
        K.card(y, "%.1f min" % cr["mean_carryover_min"], "of lateness passed on, on average",
               "Whole country: %.1f minutes. Counted over %s plane-to-next-trip pairs." % (ncar["mean_carryover_min"], C.big_count(cr["n_links"])), K.AMBER)

    st.markdown("### Year by year")
    yrs = []
    for y_ in range(2020, 2026):
        r = S.airline_row(code, str(y_))
        if r:
            yrs.append({"Year": str(y_), "Late per 100 flights that flew": round(r["delayed_15plus_rate"] * 100, 1),
                        "Cancelled per 100 planned": round(r["cancellation_rate"] * 100, 1)})
    if yrs:
        ydf = pd.DataFrame(yrs)
        l, r_ = st.columns(2)
        with l:
            K.vbar(ydf, "Year", "Late per 100 flights that flew", "Late per 100", K.RED, fmt=".1f")
        with r_:
            K.vbar(ydf, "Year", "Cancelled per 100 planned", "Cancelled per 100", K.AMBER, fmt=".1f")

    st.markdown("### Where %s struggles most, and where it does best" % pick)
    cities = [r for r in S.cities_for_airline(code, 5000)]
    if len(cities) >= 6:
        by_rate = sorted(cities, key=lambda r: r["delayed_15plus_rate"], reverse=True)
        worst, best = by_rate[:8], by_rate[::-1][:5]
        w, bst = st.columns(2)
        with w:
            st.markdown("**Most often late (flights leaving the city)**")
            K.hbar(pd.DataFrame({"City": [P.label(r["airport"]) for r in worst], "Late per 100": [round(r["delayed_15plus_rate"] * 100, 1) for r in worst]}),
                   "City", "Late per 100", "Late per 100", K.RED, fmt=".1f")
        with bst:
            st.markdown("**Least often late**")
            K.hbar(pd.DataFrame({"City": [P.label(r["airport"]) for r in best], "Late per 100": [round(r["delayed_15plus_rate"] * 100, 1) for r in best]}),
                   "City", "Late per 100", "Late per 100", K.GREEN, fmt=".1f")
        st.caption("Only cities where this airline flew at least 5,000 flights.")
    else:
        st.info("This airline does not fly enough from enough cities for a fair comparison.")
    K.ideas_block(advice.airline_ideas(S, code), "this airline")
    K.grownup("Sources: `DelayCauseMetricsJob` (rows CARRIER, CARRIERYEAR, CARRIERORIGIN) and `CarryoverAnalysisJob` (row CARRIER = airline of the plane that landed "
              "late). The carryover figures assume a plane needs about 30 minutes on the ground between flights.")
