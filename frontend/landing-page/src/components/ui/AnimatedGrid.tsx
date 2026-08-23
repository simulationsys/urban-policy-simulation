"use client";

import { cn } from "@/lib/utils";
import { motion } from "motion/react";

export function AnimatedGrid({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-0 -z-20 h-full w-full",
        className
      )}
      style={{
        backgroundImage: `radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px)`,
        backgroundSize: "32px 32px",
      }}
    >
      {/* Moving gradient overlay to create a scanning/shifting effect on the grid */}
      <div
        className="absolute inset-0 h-full w-full bg-background"
        style={{
          maskImage: "radial-gradient(ellipse at center, transparent 20%, black 80%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, transparent 20%, black 80%)",
        }}
      />
      <motion.div
        className="absolute inset-0 h-full w-full opacity-50"
        style={{
          background: "radial-gradient(circle 800px at 50% 50%, rgba(204, 128, 102, 0.05), transparent 100%)",
        }}
        animate={{
          x: [0, -150, 150, 0],
          y: [0, 150, -150, 0],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "linear",
        }}
      />
    </div>
  );
}
