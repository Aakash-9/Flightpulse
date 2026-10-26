package com.flightpulse.audit;

/**
 * Hadoop Counters collected by DatasetAuditJob. Values are read back by the
 * driver after job completion to print/record the audit summary.
 */
public enum AuditCounters {
    TOTAL_LINES,
    HEADER_ROWS,
    SCHEMA_MISMATCH,
    MALFORMED_ROWS,
    WRONG_COLUMN_COUNT,
    VALID_RECORDS,
    MISSING_TAIL_NUM,
    CANCELLED_RECORDS,
    DIVERTED_RECORDS,
    MISSING_DEP_TIME_UNEXPECTED,
    MISSING_ARR_TIME_UNEXPECTED
}
