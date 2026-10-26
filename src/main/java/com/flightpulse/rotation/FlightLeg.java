package com.flightpulse.rotation;

import org.apache.hadoop.io.Writable;
import org.apache.hadoop.io.WritableUtils;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * One operated flight leg, as carried through the secondary-sort shuffle as
 * the map-output value. Only RECORD_STATUS=VALID legs with a resolvable
 * scheduled departure AND arrival are emitted by the mapper - cancelled/
 * diverted/missing-tail records cannot participate in a rotation chain at
 * all (no reliable tail number, or no real actual-time data to derive
 * scheduled times from).
 */
public class FlightLeg implements Writable {

    public String flDate;
    public String carrier;
    public String flightNum;
    public String origin;
    public String dest;
    public long crsDepChronoMin; // absolute ordinal: epochDay*1440 + minutesSinceMidnight
    public long crsArrChronoMin;
    public double depDelay;
    public double arrDelay;

    public FlightLeg() {
    }

    @Override
    public void write(DataOutput out) throws IOException {
        WritableUtils.writeString(out, flDate);
        WritableUtils.writeString(out, carrier);
        WritableUtils.writeString(out, flightNum);
        WritableUtils.writeString(out, origin);
        WritableUtils.writeString(out, dest);
        out.writeLong(crsDepChronoMin);
        out.writeLong(crsArrChronoMin);
        out.writeDouble(depDelay);
        out.writeDouble(arrDelay);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        flDate = WritableUtils.readString(in);
        carrier = WritableUtils.readString(in);
        flightNum = WritableUtils.readString(in);
        origin = WritableUtils.readString(in);
        dest = WritableUtils.readString(in);
        crsDepChronoMin = in.readLong();
        crsArrChronoMin = in.readLong();
        depDelay = in.readDouble();
        arrDelay = in.readDouble();
    }

    public String id() {
        return flDate + " " + carrier + flightNum + " " + origin + "-" + dest;
    }
}
