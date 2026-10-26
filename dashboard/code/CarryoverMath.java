package com.flightpulse.carryover;

/**
 * The slack-aware carryover proxy, kept as pure functions so the exact
 * formulas are unit-testable. All quantities are minutes.
 *
 *   Slack(A,B)              = ScheduledGround(A,B) - MinimumTurnaround
 *   PotentialExposure(A,B)  = max(0, max(0, ArrDelay(A)) - Slack(A,B))
 *   EstimatedCarryover(A,B) = min(max(0, DepDelay(B)), PotentialExposure(A,B))
 *
 * MinimumTurnaround is a modelling assumption, not an operating standard.
 * The result is an observational proxy and does not establish that A's delay
 * caused B's delay.
 */
public final class CarryoverMath {

    private CarryoverMath() {
    }

    public static double slack(double scheduledGroundMin, double minTurnaroundMin) {
        return scheduledGroundMin - minTurnaroundMin;
    }

    public static double potentialExposure(double arrDelayA, double slackMin) {
        return Math.max(0.0, Math.max(0.0, arrDelayA) - slackMin);
    }

    public static double estimatedCarryover(double depDelayB, double potentialExposure) {
        return Math.min(Math.max(0.0, depDelayB), potentialExposure);
    }
}
