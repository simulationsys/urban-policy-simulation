"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { LiquidGlassButton } from "@/components/liquid-glass/LiquidGlassButton";
import { TextEffect } from "@/components/motion-primitives/text-effect";
import dynamic from "next/dynamic";
import { LiquidGlassDock } from "@/components/liquid-glass/LiquidGlassDock";
import { LiquidGlassFluidCard } from "@/components/liquid-glass/LiquidGlassFluidCard";
import { Activity, Map, Cpu, Sparkles } from "lucide-react";

const ParticleBackground = dynamic(
  () => import("@/components/ui/ParticleBackground").then(mod => mod.ParticleBackground),
  { ssr: false }
);

import { GlowEffect } from "@/components/motion-primitives/glow-effect";
import { InView } from "@/components/motion-primitives/in-view";
import { MapPin, BarChart3, Layers, ActivitySquare } from "lucide-react";

export default function LandingPage() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.registerPlugin(ScrollTrigger);

    gsap.from(".fade-up", {
      y: 40,
      opacity: 0,
      duration: 1.2,
      stagger: 0.2,
      ease: "power3.out",
      delay: 0.5,
    });
  }, { scope: container });

  return (
    <main ref={container} className="relative w-full min-h-screen text-white font-sans overflow-x-hidden selection:bg-purple-500/30">
      
      {/* 3D WebGL Background */}
      <ParticleBackground />

      {/* HUD Elements Removed */}

      <LiquidGlassDock 
        items={[
          {
            id: 'engine',
            icon: <Cpu className="w-5 h-5 text-white" />,
            label: 'Engine',
            onClick: () => window.scrollTo({ top: 0, behavior: 'smooth' })
          },
          {
            id: 'infrastructure',
            icon: <Map className="w-5 h-5 text-white" />,
            label: 'Infrastructure',
            onClick: () => document.getElementById('infrastructure')?.scrollIntoView({ behavior: 'smooth' })
          },
          {
            id: 'analytics',
            icon: <Activity className="w-5 h-5 text-white" />,
            label: 'Analytics',
            onClick: () => document.getElementById('analytics')?.scrollIntoView({ behavior: 'smooth' })
          },
          {
            id: 'sandbox',
            icon: <Sparkles className="w-5 h-5 text-purple-400" />,
            label: 'Sandbox Demo',
            onClick: () => window.location.href = '/demo'
          }
        ]}
      />

      {/* Scrollable Content */}
      <div className="relative z-10 w-full">
        
        {/* Hero Section */}
        <section id="engine" className="min-h-screen flex items-center px-6 md:px-12 lg:px-24 mx-auto max-w-[1600px] w-full">
          <div className="flex flex-col items-start gap-8">
            
            <h1 className="text-6xl md:text-8xl lg:text-[120px] font-light leading-[0.85] tracking-tighter">
              <span className="block fade-up">POLICY</span>
              <span className="block fade-up text-white/80">SIMULATION</span>
              <span className="block fade-up text-white/50">ENGINE</span>
            </h1>

            <p className="text-lg md:text-xl text-white/50 max-w-md font-light leading-relaxed fade-up mt-4">
              We turn massive city datasets into predictive interactive models, combining urban planning, economic forecasting, and disciplined spatial analytics.
            </p>

            <div className="fade-up mt-8 pointer-events-auto">
              <LiquidGlassButton 
                onClick={() => window.location.href = '/demo'}
                size="lg" 
                className="rounded-full px-8 py-6 text-sm tracking-widest border border-white/20"
              >
                ENTER THE SANDBOX <span className="ml-4 opacity-50">→</span>
              </LiquidGlassButton>
            </div>
          </div>
        </section>

        {/* Predictive Infrastructure Section */}
        <section id="infrastructure" className="min-h-screen flex items-center px-6 md:px-12 lg:px-24 mx-auto max-w-[1600px] pt-32 pb-32 w-full">
          <div className="flex flex-col items-start gap-16 w-full">
            <div className="text-[10px] font-mono tracking-[0.2em] text-white/50 uppercase">
              //01 PREDICTIVE INFRASTRUCTURE
            </div>

            <InView
              variants={{
                hidden: { opacity: 0, y: 50 },
                visible: { opacity: 1, y: 0 },
              }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              viewOptions={{ once: true, margin: "0px 0px -100px 0px" }}
            >
              <h2 className="text-5xl md:text-7xl font-light leading-tight tracking-tighter max-w-3xl">
                Map traffic, power, and transit over a <span className="text-purple-400">20-year horizon</span>.
              </h2>
            </InView>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 w-full max-w-5xl">
              <LiquidGlassFluidCard variant="ios26" className="h-full">
                <div className="space-y-6">
                  <div className="w-12 h-[1px] bg-white/20" />
                  <h3 className="text-xl font-light tracking-wide text-white">Compounded Effects</h3>
                  <p className="text-white/70 font-light leading-relaxed">
                    Every policy change echoes through the city's grid. Our engine calculates the exact ripple effects of new transit lines or power grids, allowing you to fast-forward decades and prevent irreversible infrastructural bottlenecks.
                  </p>
                </div>
              </LiquidGlassFluidCard>
              <LiquidGlassFluidCard variant="ios26" className="h-full">
                <div className="space-y-6">
                  <div className="w-12 h-[1px] bg-white/20" />
                  <h3 className="text-xl font-light tracking-wide text-white">Spatial Analytics</h3>
                  <p className="text-white/70 font-light leading-relaxed">
                    Test localized interventions on a high-fidelity map. Watch demographic and structural changes propagate through adjacent neighborhoods in real-time, backed by million-point datasets.
                  </p>
                </div>
              </LiquidGlassFluidCard>
            </div>
          </div>
        </section>

        {/* Spatial Canvas / Cards Section */}
        <section id="analytics" className="min-h-[150vh] flex flex-col items-start justify-center px-6 md:px-12 lg:px-24 mx-auto max-w-[1600px] py-32 pointer-events-auto w-full">
          <div className="w-full text-left space-y-4 mb-24">
            <div className="text-[10px] font-mono tracking-[0.2em] text-white/50 uppercase">
              //02 CROSS-DISCIPLINARY ANALYTICS
            </div>
            <h2 className="text-5xl font-light tracking-tighter">Unified Data Streams.</h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 w-full">
            {[
              {
                icon: <ActivitySquare className="w-8 h-8 text-white/80 mb-8 stroke-[1px]" />,
                title: "Economic Shifts",
                desc: "Forecast job growth and commercial zoning impacts across districts.",
              },
              {
                icon: <BarChart3 className="w-8 h-8 text-white/80 mb-8 stroke-[1px]" />,
                title: "Demographic Flows",
                desc: "Predict population density and housing demand before ground breaks.",
              },
              {
                icon: <Layers className="w-8 h-8 text-white/80 mb-8 stroke-[1px]" />,
                title: "Policy Testing",
                desc: "Run A/B tests on municipal policies and observe long-term outcomes.",
              }
            ].map((item, i) => (
              <LiquidGlassFluidCard key={i} variant="ios26" className="h-full w-full">
                <div className="flex h-full flex-col">
                  {item.icon}
                  <h3 className="text-xl font-light mb-4 text-white tracking-wide">{item.title}</h3>
                  <p className="text-white/70 leading-relaxed font-light">{item.desc}</p>
                </div>
              </LiquidGlassFluidCard>
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}
