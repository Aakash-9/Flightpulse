package com.flightpulse.util;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

import java.io.IOException;
import java.io.StringReader;
import java.util.Iterator;

/**
 * Parses a single CSV line with correct quote handling, e.g.
 * ORIGIN_CITY_NAME values like "Dallas/Fort Worth, TX" which contain a
 * comma inside quotes. A naive String.split(",") corrupts these rows by
 * shifting every subsequent column.
 *
 * Safe to parse one line at a time here because this dataset's quoted
 * fields (city names) never contain embedded newlines - verified against
 * the actual data. A multi-line-quoted-field dataset would need a
 * record-spanning InputFormat instead of per-line TextInputFormat.
 */
public final class CsvLineParser {

    private static final CSVFormat FORMAT = CSVFormat.DEFAULT.builder()
            .setSkipHeaderRecord(false)
            .build();

    private CsvLineParser() {
    }

    /**
     * @return parsed fields, or null if the line could not be parsed as CSV at all.
     */
    public static String[] parse(String line) {
        try (CSVParser parser = CSVParser.parse(new StringReader(line), FORMAT)) {
            Iterator<CSVRecord> it = parser.iterator();
            if (!it.hasNext()) {
                return null;
            }
            CSVRecord record = it.next();
            String[] fields = new String[record.size()];
            for (int i = 0; i < record.size(); i++) {
                fields[i] = record.get(i);
            }
            return fields;
        } catch (IOException | RuntimeException e) {
            return null;
        }
    }
}
