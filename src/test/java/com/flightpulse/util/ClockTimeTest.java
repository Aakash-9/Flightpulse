package com.flightpulse.util;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ClockTimeTest {

    @Test
    void parsesOrdinaryTime() {
        ClockTime t = ClockTime.parse("1347");
        assertNotNull(t);
        assertEquals(13 * 60 + 47, t.minutesSinceMidnight);
        assertEquals(0, t.dayOffset);
    }

    @Test
    void parsesTimeWithoutLeadingZeros() {
        ClockTime t = ClockTime.parse("5"); // 00:05
        assertNotNull(t);
        assertEquals(5, t.minutesSinceMidnight);
    }

    @Test
    void parsesMidnightMarker2400AsNextDay() {
        ClockTime t = ClockTime.parse("2400");
        assertNotNull(t);
        assertEquals(0, t.minutesSinceMidnight);
        assertEquals(1, t.dayOffset);
    }

    @Test
    void blankReturnsNull() {
        assertNull(ClockTime.parse(""));
        assertNull(ClockTime.parse(null));
    }

    @Test
    void invalidHourOrMinuteReturnsNull() {
        assertNull(ClockTime.parse("2567")); // minute 67 invalid
        assertNull(ClockTime.parse("9999"));
    }

    @Test
    void deriveScheduledHandlesOrdinaryDelay() {
        // Actual departure 13:47 (827 min), 32 min late -> scheduled 13:15 (795 min)
        ClockTime actual = ClockTime.parse("1347");
        int[] sched = ClockTime.deriveScheduled(actual, 32.0);
        assertEquals(0, sched[0]);
        assertEquals(795, sched[1]);
    }

    @Test
    void deriveScheduledHandlesEarlyDeparture() {
        // Negative delay = early departure. Actual 00:05, 10 min early (delay = -10)
        // -> scheduled = 00:05 - (-10) = 00:15
        ClockTime actual = ClockTime.parse("5");
        int[] sched = ClockTime.deriveScheduled(actual, -10.0);
        assertEquals(0, sched[0]);
        assertEquals(15, sched[1]);
    }

    @Test
    void deriveScheduledCrossesMidnightBackward() {
        // Actual 00:05, delay 10 min late -> scheduled was 23:55 the PREVIOUS day.
        ClockTime actual = ClockTime.parse("5");
        int[] sched = ClockTime.deriveScheduled(actual, 10.0);
        assertEquals(-1, sched[0]);
        assertEquals(23 * 60 + 55, sched[1]);
    }

    @Test
    void deriveScheduledCrossesMidnightForwardFrom2400Marker() {
        // Actual time recorded as 2400 (dayOffset +1, minute 0), 5 min late
        // -> scheduled = day+1 00:00 - 5 = day+0 23:55.
        ClockTime actual = ClockTime.parse("2400");
        int[] sched = ClockTime.deriveScheduled(actual, 5.0);
        assertEquals(0, sched[0]);
        assertEquals(23 * 60 + 55, sched[1]);
    }
}
