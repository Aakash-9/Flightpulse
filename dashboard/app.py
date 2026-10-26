"""FlightPulse dashboard (Streamlit).  Run:  streamlit run app.py   (from inside the dashboard folder)

Every number shown was computed by Java MapReduce jobs on Hadoop and exported to dashboard/data/*.csv.
Nothing is recalculated here: this app only reads those result files and presents them in plain words.
"""
import streamlit as st

import common as K

st.set_page_config(page_title="FlightPulse", page_icon=":material/flight:", layout="wide")
K.inject_css()

pages = {
    "Start": [st.Page("views/home.py", title="About this project", icon=":material/home:", default=True)],
    "Ask": [st.Page("views/ask.py", title="Ask a question", icon=":material/chat:")],
    "Explore": [
        st.Page("views/cities.py", title="Cities", icon=":material/location_city:"),
        st.Page("views/routes.py", title="Routes", icon=":material/route:"),
        st.Page("views/airlines.py", title="Airlines", icon=":material/flight:"),
        st.Page("views/when_why.py", title="When and why", icon=":material/schedule:"),
        st.Page("views/chain.py", title="Late planes", icon=":material/link:"),
    ],
    "Behind the scenes": [st.Page("views/built.py", title="How we built this", icon=":material/code:")],
}
page = st.navigation(pages)
st.sidebar.toggle("Show grown-up details", key="details")
st.sidebar.caption("US flights, 2020 to mid-2025. Every number was counted by Hadoop.")
page.run()
