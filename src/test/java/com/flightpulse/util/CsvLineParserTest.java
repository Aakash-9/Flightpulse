package com.flightpulse.util;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class CsvLineParserTest {

    @Test
    void parsesQuotedFieldContainingComma() {
        String line = "1/1/2020 12:00:00 AM,AA,N176AA,178,DFW,\"Dallas/Fort Worth, TX\",EGE,\"Eagle, CO\","
                + ",,,,,,,,1.00,B,0.00,,721.00,,,,,";
        String[] fields = CsvLineParser.parse(line);
        assertNotNull(fields);
        assertEquals(FlightSchema.COLUMN_COUNT, fields.length);
        assertEquals("Dallas/Fort Worth, TX", fields[FlightSchema.ORIGIN_CITY_NAME]);
        assertEquals("Eagle, CO", fields[FlightSchema.DEST_CITY_NAME]);
        assertEquals("1.00", fields[FlightSchema.CANCELLED]);
    }

    @Test
    void parsesPlainUnquotedLine() {
        String line = "1/1/2020 12:00:00 AM,9E,N131EV,4867,DSM,Des Moines,MSP,Minneapolis,1347,32.00,"
                + "12.00,1359,1441,4.00,1445,6.00,0.00,,0.00,42.00,232.00,,,,,";
        String[] fields = CsvLineParser.parse(line);
        assertNotNull(fields);
        assertEquals(FlightSchema.COLUMN_COUNT, fields.length);
        assertEquals("N131EV", fields[FlightSchema.TAIL_NUM]);
        assertEquals("32.00", fields[FlightSchema.DEP_DELAY]);
    }

    @Test
    void emptyLineReturnsNull() {
        assertNull(CsvLineParser.parse(""));
    }
}
