"""Home: what the project is, why it matters, what we found, how to use the dashboard."""
import streamlit as st

import common as K
import content as C

S = K.store()

K.banner("FlightPulse", "Why are US flights late, and what can we learn from it?")

K.answer("FlightPulse studies <b>almost 35 million US airplane trips</b> from 2020 to mid-2025 to find out "
         "<b>when, where and why flights run late</b>, and whether <b>one late plane makes its next trip late too</b>.")

st.markdown("### Why does it matter?")
st.markdown("Late flights waste people's time and cost airlines money. If we can see **where the trouble is**, **when it happens** "
            "and **what causes it**, travellers can choose better flights, and airlines and airports can see where to start fixing things.")

st.markdown("### What we found")
rows = lambda n: [dict(r) for r in K.load_csv(n).to_dict("records")]
f = C.findings(rows("causes.csv"), rows("temporal.csv"), rows("carryover.csv"))
colors = [K.RED, K.RED, K.RED, K.BLUE, K.AMBER, K.GREEN]
for start in (0, 3):
    cols = st.columns(3)
    for col, item, color in zip(cols, f[start:start + 3], colors[start:start + 3]):
        K.card(col, item["big"], item["title"], item["more"], color)
    st.write("")

st.markdown("### Start here")
a, b, c = st.columns(3)
a.markdown('<div class="step"><b>Ask a question</b><br>Type something like <i>"How many flights were delayed by bad weather '
           'leaving Chicago?"</i> and get an answer with a chart.</div>', unsafe_allow_html=True)
b.markdown('<div class="step"><b>Explore a city, route or airline</b><br>See how it did, <b>why</b> its flights are late, which '
           'routes add to the delay, and what could help.</div>', unsafe_allow_html=True)
c.markdown('<div class="step"><b>See how it was built</b><br>Hadoop (a team of computers sharing a big job) counted every flight. '
           'The last page shows the real code.</div>', unsafe_allow_html=True)
st.write("")
st.page_link("views/ask.py", label="Go to: Ask a question", icon=":material/chat:")

st.info(C.LATE_DEFINITION)
K.careful("This looks back at what happened. It is not a live flight tracker and cannot promise anything about one particular flight. "
          "The data has no passengers, pilots or crews, so we say nothing about them.")
K.grownup("Data: US Bureau of Transportation Statistics, Reporting Carrier On-Time Performance, Jan 2020 to Jun 2025. All figures "
          "were produced by Java MapReduce jobs and read from `dashboard/data/*.csv`. The six cards are built live from the Hadoop "
          "results `delay_cause_metrics`, `temporal_metrics_v2` and `carryover_metrics`.")
