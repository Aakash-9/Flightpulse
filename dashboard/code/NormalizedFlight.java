package com.flightpulse.normalize;

import com.flightpulse.util.ClockTime;
import com.flightpulse.util.FlightSchema;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Locale;

/**
 * A normalized Silver-layer flight record.
 *
 * Schema (pipe-delimited, see {@link #SILVER_HEADER}): city-name fields are
 * dropped from Silver (they duplicate L_AIRPORT.csv, which is the proper
 * place to look up a station's city, and they're the one field in this
 * dataset that contains embedded commas - dropping them here means Silver
 * never needs CSV-style quoting). CRS_DEP/CRS_ARR are derived fields: this
 * package has no CRS_DEP_TIME/CRS_ARR_TIME columns, so scheduled time is
 * recovered as actual-time-minus-delay (documented in ClockTime). A day
 * offset is carried alongside each derived/actual time because that
 * subtraction (or a "2400" actual-time reading) can cross a calendar
 * boundary relative to FL_DATE; resolving that into an absolute timezone-
 * aware instant is deliberately left to the aircraft rotation job, not
 * decided here.
 */
public final class NormalizedFlight {

    public static final String DELIMITER = "|";

    public static final String SILVER_HEADER = String.join(DELIMITER,
            "FL_DATE", "OP_UNIQUE_CARRIER", "TAIL_NUM", "OP_CARRIER_FL_NUM",
            "ORIGIN", "DEST",
            "CRS_DEP_DAY_OFFSET", "CRS_DEP_MIN", "DEP_MIN", "DEP_DELAY_MIN",
            "TAXI_OUT_MIN", "WHEELS_OFF_MIN", "WHEELS_ON_MIN", "TAXI_IN_MIN",
            "CRS_ARR_DAY_OFFSET", "CRS_ARR_MIN", "ARR_MIN", "ARR_DELAY_MIN",
            "CANCELLED", "CANCELLATION_CODE", "DIVERTED",
            "AIR_TIME_MIN", "DISTANCE_MI",
            "CARRIER_DELAY_MIN", "WEATHER_DELAY_MIN", "NAS_DELAY_MIN",
            "SECURITY_DELAY_MIN", "LATE_AIRCRAFT_DELAY_MIN",
            "RECORD_STATUS");

    private static final DateTimeFormatter SOURCE_DATE = DateTimeFormatter.ofPattern(
            "M/d/yyyy h:mm:ss a", Locale.US);
    private static final DateTimeFormatter ISO_DATE = DateTimeFormatter.ISO_LOCAL_DATE;

    public final RecordStatus status;
    private final String line;

    private NormalizedFlight(RecordStatus status, String line) {
        this.status = status;
        this.line = line;
    }

    public String toSilverLine() {
        return line;
    }

    /**
     * Classifies and normalizes one already-CSV-parsed row. Assumes the
     * caller has already verified fields.length == FlightSchema.COLUMN_COUNT;
     * CSV-parse failures and wrong column counts are quarantined by the
     * caller before this is reached.
     */
    public static NormalizedFlight classify(String[] fields) {
        LocalDate flDate = parseDate(fields[FlightSchema.FL_DATE]);
        if (flDate == null) {
            return invalid(fields, "unparseable FL_DATE");
        }

        boolean cancelled = "1.00".equals(fields[FlightSchema.CANCELLED]);
        boolean diverted = "1.00".equals(fields[FlightSchema.DIVERTED]);
        String tailNum = fields[FlightSchema.TAIL_NUM];
        boolean missingTail = tailNum == null || tailNum.isEmpty();

        RecordStatus status;
        if (cancelled) {
            status = RecordStatus.CANCELLED;
        } else if (diverted) {
            status = RecordStatus.DIVERTED;
        } else if (missingTail) {
            status = RecordStatus.MISSING_TAIL;
        } else {
            status = RecordStatus.VALID;
        }

        ClockTime dep = ClockTime.parse(fields[FlightSchema.DEP_TIME]);
        ClockTime arr = ClockTime.parse(fields[FlightSchema.ARR_TIME]);
        Double depDelay = parseDouble(fields[FlightSchema.DEP_DELAY]);
        Double arrDelay = parseDouble(fields[FlightSchema.ARR_DELAY]);

        int[] crsDep = (dep != null && depDelay != null) ? ClockTime.deriveScheduled(dep, depDelay) : null;
        int[] crsArr = (arr != null && arrDelay != null) ? ClockTime.deriveScheduled(arr, arrDelay) : null;

        StringBuilder sb = new StringBuilder(160);
        sb.append(ISO_DATE.format(flDate)).append(DELIMITER);
        sb.append(nullToEmpty(fields[FlightSchema.OP_UNIQUE_CARRIER])).append(DELIMITER);
        sb.append(nullToEmpty(tailNum)).append(DELIMITER);
        sb.append(nullToEmpty(fields[FlightSchema.OP_CARRIER_FL_NUM])).append(DELIMITER);
        sb.append(nullToEmpty(fields[FlightSchema.ORIGIN])).append(DELIMITER);
        sb.append(nullToEmpty(fields[FlightSchema.DEST])).append(DELIMITER);
        appendDayOffset(sb, crsDep).append(DELIMITER);
        appendMinutes(sb, crsDep).append(DELIMITER);
        appendClock(sb, dep).append(DELIMITER);
        appendNum(sb, depDelay).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.TAXI_OUT])).append(DELIMITER);
        appendClock(sb, ClockTime.parse(fields[FlightSchema.WHEELS_OFF])).append(DELIMITER);
        appendClock(sb, ClockTime.parse(fields[FlightSchema.WHEELS_ON])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.TAXI_IN])).append(DELIMITER);
        appendDayOffset(sb, crsArr).append(DELIMITER);
        appendMinutes(sb, crsArr).append(DELIMITER);
        appendClock(sb, arr).append(DELIMITER);
        appendNum(sb, arrDelay).append(DELIMITER);
        sb.append(cancelled ? '1' : '0').append(DELIMITER);
        sb.append(nullToEmpty(fields[FlightSchema.CANCELLATION_CODE])).append(DELIMITER);
        sb.append(diverted ? '1' : '0').append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.AIR_TIME])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.DISTANCE])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.CARRIER_DELAY])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.WEATHER_DELAY])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.NAS_DELAY])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.SECURITY_DELAY])).append(DELIMITER);
        appendNum(sb, parseDouble(fields[FlightSchema.LATE_AIRCRAFT_DELAY])).append(DELIMITER);
        sb.append(status.name());

        return new NormalizedFlight(status, sb.toString());
    }

    private static NormalizedFlight invalid(String[] fields, String reason) {
        return new NormalizedFlight(RecordStatus.INVALID, String.join(",", fields) + " || REASON=" + reason);
    }

    private static LocalDate parseDate(String raw) {
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        try {
            return LocalDate.parse(raw, SOURCE_DATE);
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    private static Double parseDouble(String raw) {
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        try {
            return Double.parseDouble(raw);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static StringBuilder appendNum(StringBuilder sb, Double v) {
        return v == null ? sb : sb.append(v);
    }

    private static StringBuilder appendClock(StringBuilder sb, ClockTime t) {
        return t == null ? sb : sb.append(t.minutesSinceMidnight);
    }

    private static StringBuilder appendMinutes(StringBuilder sb, int[] dayOffsetAndMinutes) {
        return dayOffsetAndMinutes == null ? sb : sb.append(dayOffsetAndMinutes[1]);
    }

    private static StringBuilder appendDayOffset(StringBuilder sb, int[] dayOffsetAndMinutes) {
        return dayOffsetAndMinutes == null ? sb : sb.append(dayOffsetAndMinutes[0]);
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }
}
