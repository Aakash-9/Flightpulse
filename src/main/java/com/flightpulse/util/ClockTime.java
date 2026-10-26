package com.flightpulse.util;

/**
 * A parsed BTS clock-time field (e.g. DEP_TIME, ARR_TIME).
 *
 * BTS represents local clock time as an integer like 1347 (13:47), with no
 * leading zeros guaranteed (e.g. "5" = 00:05) and a documented special case
 * of "2400" meaning midnight at the END of the operating day, i.e. the
 * instant is actually 00:00 on the NEXT calendar day.
 *
 * This class only resolves the clock reading into minutes-since-midnight
 * plus a day offset relative to FL_DATE. It does NOT resolve timezones or
 * absolute timestamps - that is deliberately deferred to the aircraft
 * rotation job (Milestone 5), which is where cross-airport, cross-timezone
 * chronology actually needs to be solved. Collapsing that here would risk
 * silently comparing unlike things.
 */
public final class ClockTime {

    public final int minutesSinceMidnight; // 0-1439
    public final int dayOffset;            // 0 normally, +1 if the raw value was "2400"

    private ClockTime(int minutesSinceMidnight, int dayOffset) {
        this.minutesSinceMidnight = minutesSinceMidnight;
        this.dayOffset = dayOffset;
    }

    /**
     * @return parsed clock time, or null if the field is blank or not a valid
     *         HHMM reading (0000-2400).
     */
    public static ClockTime parse(String raw) {
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        String digits = raw.trim();
        // Some decimal-formatted inputs could in principle show up here as
        // "1347.0" - defensively strip a trailing ".0"/".00" if present.
        int dot = digits.indexOf('.');
        if (dot >= 0) {
            digits = digits.substring(0, dot);
        }
        if (digits.isEmpty() || !digits.chars().allMatch(Character::isDigit)) {
            return null;
        }
        int value;
        try {
            value = Integer.parseInt(digits);
        } catch (NumberFormatException e) {
            return null;
        }
        if (value == 2400) {
            return new ClockTime(0, 1);
        }
        if (value < 0 || value > 2359) {
            return null;
        }
        int hh = value / 100;
        int mm = value % 100;
        if (hh > 23 || mm > 59) {
            return null;
        }
        return new ClockTime(hh * 60 + mm, 0);
    }

    /**
     * Derives the scheduled clock time from an actual clock time and a delay
     * in minutes (actual = scheduled + delay, so scheduled = actual - delay).
     * This dataset has no CRS_DEP_TIME/CRS_ARR_TIME columns; this is the
     * documented workaround (see project notes). Result is normalized back
     * into a 0-1439 minutes-since-midnight value plus a day offset relative
     * to the same FL_DATE reference the actual ClockTime used.
     *
     * @return {dayOffset, minutesSinceMidnight}
     */
    public static int[] deriveScheduled(ClockTime actual, double delayMinutes) {
        int totalActual = actual.dayOffset * 1440 + actual.minutesSinceMidnight;
        int totalScheduled = (int) Math.round(totalActual - delayMinutes);
        int dayOffset = Math.floorDiv(totalScheduled, 1440);
        int minutesSinceMidnight = Math.floorMod(totalScheduled, 1440);
        return new int[]{dayOffset, minutesSinceMidnight};
    }
}
