"use client";

import { useEffect } from "react";
import { LiquidGlassCard } from "@/components/liquid-glass/LiquidGlassCard";
import { LiquidGlassButton } from "@/components/liquid-glass/LiquidGlassButton";
import { useTheme } from "@/components/liquid-glass/ThemeProvider";
import { LiquidGlassControls } from "@/components/liquid-glass/LiquidGlassControls";

export default function GlassDemo() {
  const { setMode } = useTheme();

  useEffect(() => {
    // Enable liquid-glass mode for the demo
    setMode("liquid-glass");
  }, [setMode]);

  return (
    <div 
      className="relative min-h-screen p-8 md:p-24 flex flex-col items-center justify-center space-y-12 overflow-hidden bg-cover bg-center bg-no-repeat" 
      style={{ backgroundImage: "url('https://images.unsplash.com/photo-1688494930098-e88c53c26e3a?auto=format&q=80&w=1400')" }}
    >
      {/* Colorful shapes in the background to show off the glass refraction */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-70 animate-float" />
      <div className="absolute top-1/3 right-1/4 w-[28rem] h-[28rem] bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-70 animate-float-delayed" />
      <div className="absolute bottom-1/4 left-1/3 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-70 animate-float-slow" />
      
      <LiquidGlassCard className="max-w-2xl w-full p-8 z-10" variant="default">
        <h1 className="text-4xl font-bold mb-4 text-glass">Liquid Glass Effect</h1>
        <p className="text-glass-muted mb-8 text-lg">
          This surface uses iOS-inspired SVG refractive filters and CSS backdrop-filter to dynamically warp the background. 
        </p>
        
        <div className="flex flex-wrap gap-4 mb-8">
          <LiquidGlassButton>Click Me</LiquidGlassButton>
        </div>

        <LiquidGlassCard className="p-6" variant="chrome">
          <h2 className="text-xl font-medium mb-4 text-glass">Interactive Controls</h2>
          <LiquidGlassControls />
        </LiquidGlassCard>
      </LiquidGlassCard>
    </div>
  );
}
