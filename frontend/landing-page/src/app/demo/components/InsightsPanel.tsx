"use client";

import { useMemo } from "react";
import { AggregateMetrics } from "../lib/localSimulator";
import { Sparkles, ArrowRight, ShieldAlert, BadgeAlert } from "lucide-react";
import { motion } from "framer-motion";

interface InsightsPanelProps {
  metrics: AggregateMetrics;
  disabledMetroLines: Set<string>;
  busCapacityPct: number;
  fuelPriceDeltaPaise: number;
}

export function InsightsPanel({
  metrics,
  disabledMetroLines,
  busCapacityPct,
  fuelPriceDeltaPaise,
}: InsightsPanelProps) {
  const causalStory = useMemo(() => {
    const lines: string[] = [];

    // Weather impact
    if (metrics.rain_intensity > 0) {
      if (metrics.rain_intensity > 0.6) {
        lines.push(
          `A severe monsoon rainstorm (${Math.round(metrics.rain_intensity * 100)}% intensity) is currently overloading the Rajiv Chowk network. Commuters have heavily abandoned active transit (walking and cycling) in favor of covered modes.`
        );
      } else {
        lines.push(
          `Light rainfall (${Math.round(metrics.rain_intensity * 100)}% intensity) is active, causing minor mode shifts away from micro-mobility toward motorized vehicles.`
        );
      }
    }

    // Metro Outage impact
    if (disabledMetroLines.size > 0) {
      lines.push(
        `Critical shutdown of Metro Line ${Array.from(disabledMetroLines).join(
          ", "
        )} is forcing transit passengers onto the road network. This has pushed Bus load factor to ${Math.round(
          metrics.bus_load_pct
        )}% and added significant delay (+${Math.round(
          metrics.avg_commute_minutes * 0.25
        )} mins) to average road commutes.`
      );
    }

    // Bus capacity policy
    if (busCapacityPct < 1.0) {
      lines.push(
        `Municipal bus transit capacity is restricted to ${Math.round(
          busCapacityPct * 100
        )}% of baseline. This constraint is choking public ridership and driving citizens back into auto-rickshaws and private cars.`
      );
    } else if (busCapacityPct > 1.0) {
      lines.push(
        `Bus capacity is elevated by +${Math.round(
          (busCapacityPct - 1.0) * 100
        )}% through auxiliary scheduling. This successfully absorbs overflow commuters and buffers road congestion.`
      );
    }

    // Fuel price tax policy
    if (fuelPriceDeltaPaise > 0) {
      const rs = (fuelPriceDeltaPaise / 100).toFixed(2);
      lines.push(
        `An active carbon levy of ₹${rs} per liter has increased the utility cost of private cars, driving a noticeable shift (+${Math.round(
          (metrics.mode_share.metro || 0) * 100
        )}% share) toward DMRC metro lines and micro-mobility.`
      );
    }

    // General state synthesis
    if (metrics.road_congestion_index > 0.65) {
      lines.push(
        `Traffic congestion has reached critical thresholds (index: ${metrics.road_congestion_index}). We observe gridlock loops in adjacent arterial streets.`
      );
    }

    if (metrics.aqi_estimate > 200) {
      lines.push(
        `Warning: Emitted PM2.5 levels from private vehicles have elevated the AQI estimate to ${metrics.aqi_estimate} (Poor/Very Poor). Clean air guidelines suggest enacting zoning congestion charges.`
      );
    } else if (metrics.aqi_estimate < 80 && metrics.agents_commuting > 1000) {
      lines.push(
        `Excellent air quality metrics (AQI: ${metrics.aqi_estimate}) sustained during peak transit, indicating successful modal shifts to electric rickshaws, metro rail, and micro-mobility.`
      );
    }

    if (lines.length === 0) {
      lines.push(
        "Rajiv Chowk is currently operating under baseline conditions. Commutes are steady, and mode shares align with target planning targets."
      );
    }

    return lines;
  }, [metrics, disabledMetroLines, busCapacityPct, fuelPriceDeltaPaise]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.2 }}
      className="relative w-full rounded-2xl p-3.5 glass-blur-xl glass-surface glass-border border-white/10 overflow-hidden shadow-xl"
    >
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-5 h-5 text-purple-400" />
        <h3 className="text-xs font-semibold tracking-wider text-white uppercase font-sans">
          AI Scenario Explanation (Strata-Insights)
        </h3>
      </div>

      <div className="space-y-2">
        {causalStory.map((paragraph, index) => {
          const isWarning = paragraph.includes("Warning:") || paragraph.includes("critical");
          const isAlert = paragraph.includes("shutdown") || paragraph.includes("restricted");

          return (
            <div
              key={index}
              className={`flex items-start gap-2 p-2 rounded-xl ${
                isWarning
                  ? "bg-red-500/10 border border-red-500/20 text-red-200"
                  : isAlert
                  ? "bg-amber-500/10 border border-amber-500/20 text-amber-200"
                  : "bg-white/5 border border-white/5 text-stone-300"
              }`}
            >
              {isWarning ? (
                <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0 text-red-400" />
              ) : isAlert ? (
                <BadgeAlert className="w-4 h-4 mt-0.5 shrink-0 text-amber-400" />
              ) : (
                <ArrowRight className="w-3.5 h-3.5 mt-0.5 shrink-0 text-purple-400" />
              )}
              <p className="text-[11px] font-light leading-relaxed font-sans">{paragraph}</p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
