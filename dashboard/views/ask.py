"""Ask FlightPulse: a plain-English question box that answers from the Hadoop numbers."""
import streamlit as st

import common as K

B = K.bot()

K.banner("Ask FlightPulse", "Ask a question in plain English and get an answer with a chart")
st.markdown("I read your question, work out which **city, airline, route, reason and year** you mean, and answer **only from the numbers "
            "Hadoop counted**. I am not a general AI, so I may not understand every wording. If I do not, I will say so.")

if "chat" not in st.session_state:
    st.session_state["chat"] = []          # list of {"role": "user"|"assistant", "text": str, "answer": Answer}
if "pending" not in st.session_state:
    st.session_state["pending"] = None


def pick(q):
    st.session_state["pending"] = q


def clear():
    st.session_state["chat"] = []
    st.session_state["pending"] = None


typed = st.chat_input("Try: How many flights were delayed by bad weather leaving Chicago?")
question = typed or st.session_state["pending"]
if question:
    st.session_state["pending"] = None
    ans = B.ask(question)
    st.session_state["chat"].append({"role": "user", "text": question})
    st.session_state["chat"].append({"role": "assistant", "answer": ans})

if not st.session_state["chat"]:
    st.markdown("#### Not sure what to ask? Click one:")
    cols = st.columns(2)
    for i, q in enumerate(B.starter_questions()):
        cols[i % 2].button(q, key="starter_%d" % i, on_click=pick, args=(q,), width="stretch")
    with st.expander("What can I ask?"):
        st.markdown("- **How many:** *How many flights were cancelled because of weather in Denver in 2022?*\n"
                    "- **Which is worst:** *Which city has the most late flights? Which airline is late most often? Which route runs late the most?*\n"
                    "- **Why:** *Why are flights late in Atlanta?*\n"
                    "- **Late planes:** *Does a late plane make the next flight late for Southwest?*\n"
                    "- **Best choice:** *What is the best time to fly from New York to Los Angeles?*\n"
                    "- **Compare:** *Compare Delta and United.*\n\n"
                    "You can name a city (*Chicago*, *NYC*, *O'Hare*), an airline (*Delta*, *JetBlue*), a year (2020 to 2025), and a reason "
                    "(*weather*, *air traffic*, *the airline itself*, *a late plane*).")
else:
    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["text"])
            else:
                K.render_answer(msg["answer"])
    last = st.session_state["chat"][-1]
    if last["role"] == "assistant" and last["answer"].followups:
        st.markdown("**You could also ask:**")
        cols = st.columns(2)
        for i, q in enumerate(last["answer"].followups[:4]):
            cols[i % 2].button(q, key="follow_%d_%d" % (len(st.session_state["chat"]), i), on_click=pick, args=(q,), width="stretch")
    st.button("Clear the conversation", on_click=clear)
