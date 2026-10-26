package com.flightpulse.route;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class RouteCarrierBandTest {

    @Test
    void bandBoundariesCoverAll24HoursExactlyOnce() {
        assertEquals("NIGHT", RouteCarrierMetricsMapper.band(0));
        assertEquals("NIGHT", RouteCarrierMetricsMapper.band(4));
        assertEquals("MORNING", RouteCarrierMetricsMapper.band(5));
        assertEquals("MORNING", RouteCarrierMetricsMapper.band(11));
        assertEquals("AFTERNOON", RouteCarrierMetricsMapper.band(12));
        assertEquals("AFTERNOON", RouteCarrierMetricsMapper.band(16));
        assertEquals("EVENING", RouteCarrierMetricsMapper.band(17));
        assertEquals("EVENING", RouteCarrierMetricsMapper.band(21));
        assertEquals("NIGHT", RouteCarrierMetricsMapper.band(22));
        assertEquals("NIGHT", RouteCarrierMetricsMapper.band(23));
    }
}
