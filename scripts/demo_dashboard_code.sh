#!/usr/bin/env bash
# FlightPulse - show where the DASHBOARD code is and how it works, in the terminal.
#
#   ./scripts/demo_dashboard_code.sh          walk through every step (press Enter to continue)
#   ./scripts/demo_dashboard_code.sh 4        jump to one step (1-8)
#   DEMO_NOPAUSE=1 ./scripts/demo_dashboard_code.sh   print everything without pausing
#
# Tip: zoom the terminal text with Ctrl+Plus so the room can read it.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
D="$ROOT/dashboard"

B=$'\e[1m'; C=$'\e[36m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[0m'

title() { printf '\n%s%s=== %s ===%s\n' "$B" "$C" "$1" "$R"; }
say()   { printf '%s%s%s\n' "$G" "$1" "$R"; }
note()  { printf '%s%s%s\n' "$Y" "$1" "$R"; }
pause() { [ -n "$DEMO_NOPAUSE" ] || read -r -p "  [press Enter for the next step] " _; }

# show FILE [FROM [TO]]  -> highlighted Python with the REAL line numbers of the file
show() {
  local f="$1" a="${2:-1}" b="${3:-100000}"
  printf '\n%s%s%s   (lines %s-%s)\n' "$B" "${f#$ROOT/}" "$R" "$a" "$([ "$b" = 100000 ] && wc -l < "$f" || echo "$b")"
  if command -v pygmentize >/dev/null 2>&1; then
    sed -n "${a},${b}p" "$f" | pygmentize -l python -f terminal256 -O style=monokai 2>/dev/null \
      | awk -v s="$a" '{printf "%s%4d%s  %s\n", "\033[90m", NR+s-1, "\033[0m", $0}'
  else
    sed -n "${a},${b}p" "$f" | awk -v s="$a" '{printf "%4d  %s\n", NR+s-1, $0}'
  fi
}

lines() { wc -l < "$D/$1" | tr -d ' '; }

step1() {
  title "1. Where is the dashboard code?   ~/flightpulse/dashboard/"
  say "It is a Streamlit app written in Python. It does NOT analyse flights: it shows what Hadoop counted."
  echo
  printf '  %-22s %5s  %s\n' "FILE" "LINES" "WHAT IT DOES"
  printf '  %-22s %5s  %s\n' "app.py"             "$(lines app.py)"           "starts the app and builds the menu"
  printf '  %-22s %5s  %s\n' "views/*.py (8)"     "$(cat "$D"/views/*.py | wc -l | tr -d ' ')" "one file per page: cities, routes, airlines, ..."
  printf '  %-22s %5s  %s\n' "chatbot.py"         "$(lines chatbot.py)"       "the question box: understands a question, picks the numbers"
  printf '  %-22s %5s  %s\n' "store.py"           "$(lines store.py)"         "reads the Hadoop result files, combines airports of one city"
  printf '  %-22s %5s  %s\n' "places.py"          "$(lines places.py)"        "full city and airline names instead of codes"
  printf '  %-22s %5s  %s\n' "advice.py"          "$(lines advice.py)"        "'what could help' ideas, each marked with how well supported it is"
  printf '  %-22s %5s  %s\n' "content.py"         "$(lines content.py)"       "plain-words helpers and the headline findings"
  printf '  %-22s %5s  %s\n' "common.py"          "$(lines common.py)"        "look and feel: colours, charts, tables"
  printf '  %-22s %5s  %s\n' "test_*.py"          "$(cat "$D"/test_*.py | wc -l | tr -d ' ')" "42 automated tests"
  printf '  %-22s %5s  %s\n' "data/*.csv (12)"    "-"                         "the Hadoop results, exported (not code)"
  echo
  note "  Pages (the menu): About this project | Ask a question | Cities | Routes | Airlines | When and why | Late planes | How we built this"
  pause
}

step2() {
  title "2. How Hadoop's answers reach the dashboard"
  say "Hadoop (HDFS)  -->  scripts/export_dashboard_data.py  -->  dashboard/data/*.csv  -->  the pages"
  echo
  say "The export only copies. It refuses to continue if a row count differs from what the Hadoop job reported:"
  show "$ROOT/scripts/export_dashboard_data.py" 63 76
  echo; say "The files it wrote (rows per file, header included):"
  (cd "$D/data" && wc -l *.csv | sed 's/^/  /')
  echo; say "A peek at one of them (first 3 airports):"
  head -3 "$D/data/airports.csv" | cut -c1-110 | sed 's/^/  /'
  pause
}

step3() {
  title "3. app.py - the whole entry point is 28 lines"
  say "It sets the page, builds the menu (st.navigation), and runs the page you clicked."
  show "$D/app.py" 10 28
  pause
}

step4() {
  title "4. A page: views/ask.py - the chat box"
  say "st.chat_input is the text box. The question goes to the Bot; the answer is drawn with a chart."
  show "$D/views/ask.py" 27 33
  show "$D/views/ask.py" 49 55
  pause
}

step5() {
  title "5. The chatbot - rules, not an AI model"
  say "It finds the city / airline / year / reason in the question, then picks the matching Hadoop numbers."
  show "$D/chatbot.py" 263 282
  say "Finding the reason (weather, air traffic, the airline itself, a late plane):"
  show "$D/chatbot.py" 357 364
  note "  If it cannot understand a question it says so, instead of guessing (see help_answer, line 775)."
  pause
}

step6() {
  title "6. Where the numbers come from: store.py"
  say "A city can have several airports (Chicago = O'Hare + Midway). Hadoop's COUNTS are added up and the rates"
  say "are worked out again from those counts; average delays are weighted by each airport's flights."
  show "$D/store.py" 32 47
  pause
}

step7() {
  title "7. 'What could help' - advice.py"
  say "An idea is only shown when a reason is at least 3 percentage points above the national share."
  show "$D/advice.py" 31 45
  say "Each idea carries a label: backed by research / mixed evidence / common practice, not proven here."
  show "$D/advice.py" 14 18
  pause
}

step8() {
  title "8. Proof it works: the tests, run live"
  (cd "$ROOT" && python3 -W ignore -m unittest discover -s dashboard -p "test_*.py" 2>&1 | tail -4 | sed 's/^/  /')
  echo
  say "Run the dashboard locally:"
  echo "  cd ~/flightpulse/dashboard && ../.venv/bin/streamlit run app.py        -> http://localhost:8501"
  say "Run it in Docker (needs Docker installed):"
  echo "  cd ~/flightpulse/dashboard && docker compose up --build                 -> http://localhost:8501"
  pause
}

case "${1:-all}" in
  all) for n in 1 2 3 4 5 6 7 8; do step$n; done; title "That is the whole dashboard."; ;;
  [1-8]) step$1 ;;
  *) echo "usage: $0 [1-8]"; exit 1 ;;
esac
