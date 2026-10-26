"""Late planes: does one late plane make the next trip late?"""
import pandas as pd
import streamlit as st

import common as K
import content as C

S, P = K.store(), K.store().places

K.banner("Late planes", "Does one late plane make the next trip late?")
ta = st.radio("How many minutes does a plane need on the ground to get ready again? (our guess, so we try three)", [20, 30, 45], index=1, horizontal=True)
gap = 90
if st.session_state.get("details"):
    gap = st.radio("Longest wait we still count as 'the same chain' (minutes)", [60, 90, 120], index=1, horizontal=True)
params = "G%d_T%d" % (gap, ta)
allr = S.carryover_row("ALL", "", params)
pl, pn = allr["p_b_late15_given_a_late15"], allr["p_b_late15_given_a_not_late15"]
tab_f, tab_p, tab_g = st.tabs(["The big finding", "One plane's day", "What if our guess changes?"])

with tab_f:
    K.answer("When the plane before landed late, the next trip left late <b>%s times out of 100</b>. When it landed on time, only <b>%s out of 100</b>." % (
        C.per100_value(pl), C.per100_value(pn)))
    a, b, c = st.columns(3)
    K.bignum(a, C.per100_value(pl), "next trip late, after a LATE landing (per 100)", K.RED)
    K.bignum(b, C.per100_value(pn), "next trip late, after an ON-TIME landing (per 100)", K.GREEN)
    K.bignum(c, C.big_count(allr["n_links"]), "plane-to-next-trip pairs studied")
    st.markdown("### Do spare minutes on the ground help?")
    sl = {k: S.carryover_row("SLACK", k, params) for k in C.SLACK_ORDER}
    sdf = pd.DataFrame({"Spare time": [C.SLACK_LABEL[k] for k in C.SLACK_ORDER if sl[k]],
                        "Lateness passed on (minutes, average)": [round(sl[k]["mean_carryover_min"], 1) for k in C.SLACK_ORDER if sl[k]]})
    K.hbar(sdf, "Spare time", "Lateness passed on (minutes, average)", "Average minutes of lateness passed to the next trip", K.RED, fmt=".1f", height=260)
    st.markdown("### The later the plane lands, the more it passes on")
    ar = {k: S.carryover_row("ARRDELAY_A", k, params) for k in C.ARR_ORDER}
    adf = pd.DataFrame({"How late it landed": [C.ARR_LABEL[k] for k in C.ARR_ORDER if ar[k]],
                        "Lateness passed on (minutes, average)": [round(ar[k]["mean_carryover_min"], 1) for k in C.ARR_ORDER if ar[k]]})
    K.hbar(adf, "How late it landed", "Lateness passed on (minutes, average)", "Average minutes of lateness passed to the next trip", K.RED, fmt=".1f", height=260)
    K.careful("This shows that late planes and late next trips go together. It does NOT prove one caused the other: bad weather or a busy airport can make "
              "both trips late. How much it matters also depends on our guess for the time a plane needs on the ground, which is why we show three guesses.")

with tab_p:
    rot = K.load_csv("rotation_sample.csv")
    tails = list(dict.fromkeys(rot["tail_num"]))

    def split_leg(text):
        date, flight, route = text.split(" ", 2)
        return date, flight, route

    def flight_name(flight):
        return "%s %s" % (S.airline_label(flight[:2]), flight[2:])

    def first_airline(t):
        _, flight, _ = split_leg(rot[rot["tail_num"] == t].iloc[0]["leg_a"])
        return "Plane %s (%s)" % (t, S.airline_label(flight[:2]))
    tail = st.selectbox("Pick a plane (every plane has its own number on its tail)", tails, format_func=first_airline)
    sub = rot[rot["tail_num"] == tail]
    date = split_leg(sub.iloc[0]["leg_a"])[0]
    legs = list(dict.fromkeys(list(sub["leg_a"]) + list(sub["leg_b"])))
    K.answer("On <b>%s</b>, this one plane flew <b>%d trips</b> in a row. See how each trip hands over to the next." % (date, len(legs)))
    table = []
    for i, x in enumerate(sub.to_dict("records"), start=1):
        _, fa, ra = split_leg(x["leg_a"])
        _, fb, rb = split_leg(x["leg_b"])
        ao, ad = ra.split("-")
        bo, bd = rb.split("-")
        a_late, b_late = float(x["leg_a_arr_delay_min"]), float(x["leg_b_dep_delay_min"])
        table.append({"Step": i, "Trip before": "%s: %s to %s" % (flight_name(fa), P.city(ao), P.city(ad)),
                      "It landed": ("%d min late" % a_late) if a_late > 0 else ("%d min early" % -a_late) if a_late < 0 else "on time",
                      "Time on the ground": "%d min" % int(x["ground_minutes"]),
                      "Next trip": "%s: %s to %s" % (flight_name(fb), P.city(bo), P.city(bd)),
                      "It left": ("%d min late" % b_late) if b_late > 0 else ("%d min early" % -b_late) if b_late < 0 else "on time",
                      "What we found": C.LINK_STATUS_PLAIN[x["link_status"]]})
    K.table(pd.DataFrame(table))
    st.info("Look for a trip that lands late, a short wait on the ground, then the next trip leaving late too. That is one late plane passing its lateness on.")
    K.careful("Times on the ground are only approximate: the data has no time zones, so a trip that crosses time zones can look a few hours off. "
              "These 30 planes are a small sample, picked by a fixed rule.")

with tab_g:
    st.markdown("The result depends on how many minutes we assume a plane needs on the ground. So we tried three guesses and three limits for how long a wait still counts as one chain.")
    srows = []
    for g in (60, 90, 120):
        for t in (20, 30, 45):
            x = S.carryover_row("ALL", "", "G%d_T%d" % (g, t))
            srows.append({"Longest wait counted (min)": g, "Minutes needed to get ready (min)": t,
                          "Trips where lateness could pass on (per 100)": round(x["exposed_rate"] * 100, 1)})
    K.table(pd.DataFrame(srows))
    st.info("The more time we think a plane needs, the more trips look at risk. That is why we show all of them, not one.")
K.grownup("Sources: `CarryoverAnalysisJob` (9 parameter combinations) and `AircraftRotationJob` (33,896,859 links for 7,439 aircraft; Hadoop secondary sort orders each "
          "aircraft's flights). Spare minutes = planned ground time - assumed turnaround. Exposure = max(0, max(0, arrival delay of A) - spare). Carryover = "
          "min(max(0, departure delay of B), exposure). Ground times are not time-zone corrected. Where spare time is negative, exposure is positive even for an "
          "on-time landing; that follows from the formula and affects about 1.5% of pairs at 30 minutes. The plane tab is a deterministic sample.")
