package com.flightpulse.normalize;

/**
 * Classification applied to each Bronze record during normalization.
 * All statuses except INVALID are written to Silver; INVALID rows are
 * preserved in the quarantine output instead of being dropped, per the
 * project's "never silently discard data" requirement.
 */
public enum RecordStatus {
    /** Operated flight, has tail number, actual times present and consistent. */
    VALID,
    /** CANCELLED=1. No actual flight occurred; not eligible for rotation chaining. */
    CANCELLED,
    /** DIVERTED=1. Landed somewhere other than the scheduled destination. */
    DIVERTED,
    /** Otherwise-valid operated flight but TAIL_NUM is blank - usable for
     *  airport/route/temporal aggregates, not usable for aircraft rotation. */
    MISSING_TAIL,
    /** Row failed CSV parsing, had the wrong column count, or had an
     *  unparseable value in a field that must be numeric/well-formed.
     *  Goes to quarantine, not Silver. */
    INVALID
}
