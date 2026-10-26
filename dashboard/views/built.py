"""How it was built: the Hadoop pipeline, measured experiments, the real code, and how the question box works."""
import os

import streamlit as st

import common as K
import content as C

K.banner("How we built this", "Hadoop counted every flight. This dashboard only shows the answers.")
K.answer("A team of computers (Hadoop) read <b>every one of the 34.8 million flights</b>, cleaned them, and counted them in many different ways. "
         "This dashboard only <b>shows</b> the answers they produced.")
dot = ('digraph { rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#f1f6ff", fontname="Helvetica"]; '
       '"Raw flight files\\n(66 monthly files, 5 GB)" -> "HDFS storage\\n(Bronze: untouched copy)" -> '
       '"Clean-up job\\n(Silver: 34.8M tidy records)" -> "Counting jobs\\n(Gold: the answers)" -> "This dashboard"; }')
st.graphviz_chart(dot)

pipe = K.load_csv("pipeline.csv")
st.markdown("### The jobs we ran (each one is a Java MapReduce program)")
K.table(pipe[["job", "what_it_does", "duration_seconds"]].rename(
    columns={"job": "Job", "what_it_does": "What it does", "duration_seconds": "Seconds it took"}))
audit = K.load_csv("audit_months.csv")
a, b, c = st.columns(3)
K.bignum(a, C.big_count(audit["records"].sum()), "flights counted in the check")
K.bignum(b, "0", "badly formed records found", K.GREEN)
K.bignum(c, str(len(audit)), "monthly files checked")

st.markdown("### Experiments we measured")
bm = K.load_csv("benchmark.csv")
off = bm[(bm["setting"] == "off") & (bm["metric"] == "seconds")].iloc[0]["value"]
on = bm[(bm["setting"] == "on") & (bm["metric"] == "seconds")].iloc[0]["value"]
offb = bm[(bm["setting"] == "off") & (bm["metric"] == "shuffle bytes")].iloc[0]["value"]
onb = bm[(bm["setting"] == "on") & (bm["metric"] == "shuffle bytes")].iloc[0]["value"]
st.markdown("**Squeezing the data while it moves between computers:** the plane-chain job went from **%s seconds to %s seconds**, and the data moved shrank "
            "from **%.1f GB to %.1f GB**, with exactly the same answers (we checked every byte)." % (off, on, float(offb) / 1e9, float(onb) / 1e9))
st.markdown("**Adding up early:** before sending anything, each computer adds up its own flights first. For airports this cut 69.6 million records down to 42,751.")
K.table(bm)

st.markdown("### How the question box works")
st.markdown("It is **not** a general AI. It reads your question, spots the **city, airline, route, reason and year** you mention, decides what kind of question it is "
            "(how many, which is worst, why, does lateness pass on...), then looks the answer up in the results Hadoop produced. It shows where each number came from "
            "and says so when it does not understand. That is why every answer can be traced back to a Hadoop job.")

st.markdown("### Look at the real Hadoop code")
files = sorted(f for f in os.listdir(os.path.join(K.HERE, "code")) if f.endswith(".java"))
pick = st.selectbox("Pick a program", files)
with open(os.path.join(K.HERE, "code", pick)) as f:
    st.code(f.read(), language="java")
K.careful("This ran on one computer pretending to be a small cluster, so it shows that the method works. It cannot show how much faster a real many-computer cluster would be.")
K.grownup("Hadoop 3.5.0, pseudo-distributed (HDFS + YARN, one node), Java 17. All metrics are produced by Java MapReduce jobs reading HDFS and writing HDFS; this app only "
          "displays exported CSV files (`scripts/export_dashboard_data.py`), whose row counts are checked against the job counters at export time. Secondary sort = "
          "`TailChronoKey` + `TailNumPartitioner` + `TailGroupComparator`.")
