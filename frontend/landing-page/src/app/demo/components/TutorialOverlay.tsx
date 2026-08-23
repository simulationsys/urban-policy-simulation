"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowRight, ArrowLeft, Play, Sparkles } from "lucide-react";
import { LiquidGlassButton } from "@/components/liquid-glass/LiquidGlassButton";
import { LiquidGlassCard } from "@/components/liquid-glass/LiquidGlassCard";

interface TutorialOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  currentStep: number;
  setCurrentStep: (step: number) => void;
}

interface StepContent {
  title: string;
  description: string;
  badge: string;
  elementId?: string;
}

const STEPS: StepContent[] = [
  {
    title: "Welcome to Strata",
    description: "Strata is an urban intelligence command center modeling policy scenarios over Delhi's Connaught Place (Rajiv Chowk). Planners use it to test infrastructure decisions (zoning, transit, taxation, environmental rules) before enacting them.",
    badge: "GETTING STARTED",
  },
  {
    title: "Live City Network Grid",
    description: "The Canvas visualizes a concentric-radial representation of Rajiv Chowk roads, metro lines, and bus loops. Watch regular Citizens (cyan dots) and Delivery/Freight Agents (orange dots) commute. Heavy traffic slows them down.",
    badge: "SPATIAL TELEMETRY",
  },
  {
    title: "Key Performance Telemetry",
    description: "Keep an eye on key urban metrics in real-time. Mode Share displays the percentage of commuters choosing walking, metro, buses, or private cars. Congestion Index, Bus/Metro Load, and AQI estimate general city stress.",
    badge: "ANALYTICS & METRICS",
  },
  {
    title: "Scenario Controls & Policies",
    description: "Adjust weather and policy levers dynamically. Slide the Monsoon Rain gauge, toggle transit constraints (bus scheduling), increase fuel taxes, or shut down a metro track. The engine computes outcomes instantly.",
    badge: "POLICY STRESS-TESTS",
  },
  {
    title: "Curated Challenge Presets",
    description: "Need guidance? Try the Scenario Challenges. Run through a Monsoon Storm, orchestrate a Decarbonization Tax push, or manage a Metro Line Outage. The simulator guides you through each causal loop step-by-step.",
    badge: "GUIDED CHALLENGES",
  },
  {
    title: "AI Causal Explanations",
    description: "The AI Insights panel breaks down the cascading ripple effects of your interventions in plain English. It tracks exactly why average commute times spiked, or how policies impacted public health (AQI).",
    badge: "COGNITIVE EXPLAINER",
  },
];

export function TutorialOverlay({
  isOpen,
  onClose,
  currentStep,
  setCurrentStep,
}: TutorialOverlayProps) {
  if (!isOpen) return null;

  const step = STEPS[currentStep];

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      onClose();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm pointer-events-auto">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.4, type: "spring", stiffness: 260, damping: 25 }}
          className="relative max-w-lg w-full z-10"
        >
          <LiquidGlassCard className="p-6 md:p-8" variant="chrome">
            {/* Close Button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Badge */}
            <div className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest text-purple-400 font-semibold mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              {step.badge} — STEP {currentStep + 1} OF {STEPS.length}
            </div>

            {/* Title */}
            <h2 className="text-2xl font-light text-white tracking-tight mb-4">
              {step.title}
            </h2>

            {/* Description */}
            <p className="text-sm text-stone-300 font-light leading-relaxed mb-8">
              {step.description}
            </p>

            {/* Actions */}
            <div className="flex items-center justify-between mt-6">
              {/* Progress dots */}
              <div className="flex gap-1.5">
                {STEPS.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => setCurrentStep(idx)}
                    className={`w-2 h-2 rounded-full transition-all duration-300 ${
                      idx === currentStep ? "bg-purple-400 w-4" : "bg-white/20 hover:bg-white/35"
                    }`}
                  />
                ))}
              </div>

              {/* Navigation buttons */}
              <div className="flex gap-2">
                {currentStep > 0 && (
                  <button
                    onClick={handleBack}
                    className="flex items-center gap-1 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-stone-300 text-xs font-medium transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Back
                  </button>
                )}
                <LiquidGlassButton
                  onClick={handleNext}
                  className="rounded-lg px-5 py-2 text-xs font-semibold"
                >
                  {currentStep === STEPS.length - 1 ? (
                    <span className="flex items-center gap-1">
                      Start Sandbox <Play className="w-3 h-3 fill-current ml-1" />
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      Next Step <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </span>
                  )}
                </LiquidGlassButton>
              </div>
            </div>
          </LiquidGlassCard>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
