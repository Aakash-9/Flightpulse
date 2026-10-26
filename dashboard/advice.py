"""'What could help' ideas for a city or an airline, driven by the numbers.

Rules compare an entity's mix of delay reasons with the national mix and only raise an
idea when a reason is clearly above average. Every idea says how well supported it is.
These are ideas to investigate, NOT proven fixes: this data cannot show what would work.

Evidence labels (from the research behind this project):
  RESEARCH  - published studies support it (schedule buffers absorbing inbound lateness)
  MIXED     - studies disagree (spreading out busy peaks)
  PRACTICE  - common industry practice; no measured effect was found or tested here
"""
import content as C

EVIDENCE = {
    "RESEARCH": "Backed by research",
    "MIXED": "Mixed evidence",
    "PRACTICE": "Common practice, not proven here",
}

SOURCES = [
    ("What each delay reason means", "US Bureau of Transportation Statistics: Understanding the Reporting of Causes of Flight Delays and Cancellations",
     "https://www.bts.gov/topics/airlines-and-airports/airline-time-performance-and-causes-flight-delays"),
    ("Extra ground time absorbs late inbound planes", "Brueckner, Czerny & Gaggero, Schedule buffers (CESifo Working Paper 7875)",
     "https://www.cesifo.org/DocDL/cesifo1_wp7875.pdf"),
    ("Moving spare time around cut spread-out delay (one airline)", "Journal of South China University of Technology, 2019",
     "https://zrb.bjb.scut.edu.cn/EN/abstract/article/1000-565X/12919"),
    ("Hub flight banks and airport congestion", "Ater, Airport congestion and hub delay (Tel Aviv University working paper)",
     "https://en-coller.tau.ac.il/sites/coller-english.tau.ac.il/files/WP_5-2010_Ater.pdf"),
]

GAP = 0.03          # a reason must be at least 3 percentage points above the national share to be raised


def _pct(x):
    return "%d%%" % round(x * 100)


def _flagged(row, nat):
    """Reasons whose share of lateness is clearly above the national share, biggest gap first."""
    out = []
    for k, label, _ in C.CAUSES:
        gap = row["share_" + k] - nat["share_" + k]
        if gap >= GAP:
            out.append((gap, k))
    return [k for _, k in sorted(out, reverse=True)]


def _carry_tip(row_carry, nat_carry, who):
    if not row_carry or not nat_carry:
        return None
    mine, base = row_carry["p_b_late15_given_a_late15"], nat_carry["p_b_late15_given_a_late15"]
    return ("When a plane landed late %s, its next trip left late %s times out of 100 (across the country: %s). "
            "More time on the ground between flights gives a late plane room to catch up: across all airlines in this data, trips "
            "with only 0 to 14 spare minutes passed on far more lateness than trips with 30 to 59 spare minutes."
            % (who, C.per100_value(mine), C.per100_value(base)))


def airline_ideas(S, carrier):
    nat, row = S.national(), S.airline_row(carrier)
    if not row:
        return []
    name = S.airline_label(carrier)
    ideas = []
    flagged = _flagged(row, nat)
    carry = S.carryover_row("CARRIER", carrier)
    nat_carry = S.carryover_row("ALL")

    if "late_aircraft" in flagged or (carry and carry["p_b_late15_given_a_late15"] - nat_carry["p_b_late15_given_a_late15"] >= 0.02):
        ideas.append({
            "title": "Give tight turnarounds more breathing room",
            "evidence": "RESEARCH",
            "why": "%s of %s's lateness comes from planes that arrived late from their last trip (country: %s). %s" % (
                _pct(row["share_late_aircraft"]), name, _pct(nat["share_late_aircraft"]),
                _carry_tip(carry, nat_carry, "for %s" % name) or ""),
            "idea": "Add a few minutes of ground time where trips are tightest, and protect the first flight of each plane's day."})
    if "carrier" in flagged:
        ideas.append({
            "title": "Look at crews, maintenance and turnaround work",
            "evidence": "PRACTICE",
            "why": "%s of %s's lateness is listed as the airline's own problems (country: %s). The official definition of this "
                   "reason covers crews, maintenance, cleaning, baggage loading and fuelling." % (
                       _pct(row["share_carrier"]), name, _pct(nat["share_carrier"])),
            "idea": "Check which of those steps most often holds flights up, and keep spare crews and aircraft where it hurts most."})
    if "nas" in flagged:
        ideas.append({
            "title": "Avoid bunching flights into the busiest hours",
            "evidence": "MIXED",
            "why": "%s of %s's lateness is blamed on busy skies and airport operations (country: %s)." % (
                _pct(row["share_nas"]), name, _pct(nat["share_nas"])),
            "idea": "Where it flies into crowded airports, spread departures away from the peak. Studies disagree on how much this helps."})
    if "weather" in flagged or row["cancel_code_b_weather"] / max(row["n_cancelled"], 1) - nat["cancel_code_b_weather"] / max(nat["n_cancelled"], 1) >= 0.10:
        ideas.append({
            "title": "Have a storm plan ready",
            "evidence": "PRACTICE",
            "why": "Weather explains %s of %s's lateness (country: %s) and %s of its cancellations." % (
                _pct(row["share_weather"]), name, _pct(nat["share_weather"]), _pct(row["cancel_code_b_weather"] / max(row["n_cancelled"], 1))),
            "idea": "Airlines often cancel some flights early before a big storm so planes and crews are in the right place to recover. "
                    "We found no study measuring how much this helps."})
    if row["cancellation_rate"] - nat["cancellation_rate"] >= 0.01 and not any(i["title"] == "Have a storm plan ready" for i in ideas):
        top = max(zip(C.CANCEL_REASONS, [row["cancel_code_" + k] for k, _ in C.CANCEL_REASONS]), key=lambda t: t[1])[0][1]
        ideas.append({
            "title": "Find out why so many flights are cancelled",
            "evidence": "PRACTICE",
            "why": "%s out of every 100 %s flights were cancelled (country: %s). The most common recorded reason is: %s." % (
                C.per100_value(row["cancellation_rate"]), name, C.per100_value(nat["cancellation_rate"]), top.lower()),
            "idea": "Start with that reason and see which cities or seasons it is concentrated in."})
    return ideas[:3]


def city_ideas(S, codes, row):
    nat = S.national()
    flagged = _flagged(row, nat)
    carry_rows = [S.carryover_row("AIRPORT", c) for c in codes]
    carry_rows = [r for r in carry_rows if r]
    nat_carry = S.carryover_row("ALL")
    ideas = []
    if "nas" in flagged:
        ideas.append({
            "title": "Spread out the busy hours and protect runway capacity",
            "evidence": "MIXED",
            "why": "%s of the lateness here is blamed on busy skies and airport operations (country: %s)." % (
                _pct(row["share_nas"]), _pct(nat["share_nas"])),
            "idea": "Work with airlines and air traffic control on departure peaks, and keep runways and taxiways clear. "
                    "When too many flights are due at once, the FAA can hold flights at their departure airport (a ground delay program)."})
    if "weather" in flagged:
        ideas.append({
            "title": "Be ready for bad-weather days",
            "evidence": "PRACTICE",
            "why": "Weather explains %s of the lateness here (country: %s)." % (_pct(row["share_weather"]), _pct(nat["share_weather"])),
            "idea": "Snow-clearing and de-icing capacity, and low-visibility procedures, decide how fast an airport recovers. "
                    "We did not test these ideas in this data."})
    if "carrier" in flagged:
        ideas.append({
            "title": "Work with the airlines on turnaround",
            "evidence": "PRACTICE",
            "why": "%s of the lateness here is listed as the airlines' own problems (country: %s)." % (
                _pct(row["share_carrier"]), _pct(nat["share_carrier"])),
            "idea": "Gates, baggage handling and fuelling are shared between airport and airlines; look for the slowest step."})
    if "late_aircraft" in flagged or (carry_rows and nat_carry and
                                      max(r["p_b_late15_given_a_late15"] for r in carry_rows) - nat_carry["p_b_late15_given_a_late15"] >= 0.02):
        ideas.append({
            "title": "Late planes arriving here keep passing lateness on",
            "evidence": "RESEARCH",
            "why": "%s of the lateness is because the plane was already late. %s" % (
                _pct(row["share_late_aircraft"]),
                _carry_tip(max(carry_rows, key=lambda r: r["n_links"]), nat_carry, "at this airport") if carry_rows else ""),
            "idea": "This delay starts elsewhere, so the airport cannot fix it alone. The airlines here can add ground time between flights."})
    return ideas[:3]
