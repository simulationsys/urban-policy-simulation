"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface FloatingOrbsProps {
  className?: string;
}

export function FloatingOrbs({ className }: FloatingOrbsProps) {
  return (
    <div className={cn("fixed inset-0 overflow-hidden pointer-events-none -z-10", className)}>
      {/* Orb 1: Deep Copper */}
      <motion.div
        className="absolute top-[0%] left-[10%] w-[800px] h-[800px] rounded-full opacity-10 blur-[120px]"
        style={{
          background: "radial-gradient(circle, rgba(204, 128, 102, 0.8), rgba(154, 91, 69, 0.2))",
        }}
        animate={{
          x: [0, 100, -50, 0],
          y: [0, 50, -100, 0],
          scale: [1, 1.1, 0.9, 1],
        }}
        transition={{
          duration: 30,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      
      {/* Orb 2: Ambient Dark */}
      <motion.div
        className="absolute bottom-[-20%] right-[0%] w-[900px] h-[900px] rounded-full opacity-20 blur-[150px]"
        style={{
          background: "radial-gradient(circle, rgba(31, 41, 55, 0.9), transparent)",
        }}
        animate={{
          x: [0, -150, -50, 0],
          y: [0, -100, 50, 0],
          scale: [1, 0.9, 1.1, 1],
        }}
        transition={{
          duration: 35,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </div>
  );
}
