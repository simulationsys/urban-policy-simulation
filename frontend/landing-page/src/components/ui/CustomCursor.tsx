"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

export default function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const dotRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (!cursorRef.current || !dotRef.current) return;

    // Fix centering with GSAP to avoid Tailwind transform conflicts
    gsap.set(cursorRef.current, { xPercent: -50, yPercent: -50 });
    gsap.set(dotRef.current, { xPercent: -50, yPercent: -50 });

    // Reduce duration for snappier, less laggy response
    const xToCursor = gsap.quickTo(cursorRef.current, "x", { duration: 0.1, ease: "power3.out" });
    const yToCursor = gsap.quickTo(cursorRef.current, "y", { duration: 0.1, ease: "power3.out" });
    
    const xToDot = gsap.quickTo(dotRef.current, "x", { duration: 0.02, ease: "power3.out" });
    const yToDot = gsap.quickTo(dotRef.current, "y", { duration: 0.02, ease: "power3.out" });

    const onMouseMove = (e: MouseEvent) => {
      xToCursor(e.clientX);
      yToCursor(e.clientY);
      xToDot(e.clientX);
      yToDot(e.clientY);
    };

    const onMouseEnter = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.tagName.toLowerCase() === "a" || 
        target.tagName.toLowerCase() === "button" ||
        target.closest("a") || 
        target.closest("button")
      ) {
        gsap.to(cursorRef.current, { scale: 1.5, opacity: 0.5, duration: 0.2, ease: "power2.out" });
      }
    };

    const onMouseLeave = () => {
      gsap.to(cursorRef.current, { scale: 1, opacity: 1, duration: 0.2, ease: "power2.out" });
    };

    window.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseover", onMouseEnter, true);
    document.addEventListener("mouseout", onMouseLeave, true);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseover", onMouseEnter, true);
      document.removeEventListener("mouseout", onMouseLeave, true);
    };
  }, []);

  return (
    <>
      <div 
        ref={cursorRef} 
        style={{ willChange: "transform" }}
        className="fixed top-0 left-0 w-8 h-8 border border-white rounded-full pointer-events-none z-[9999] hidden sm:block"
      />
      <div 
        ref={dotRef} 
        style={{ willChange: "transform" }}
        className="fixed top-0 left-0 w-2 h-2 bg-white rounded-full pointer-events-none z-[9999] hidden sm:block shadow-[0_1px_3px_rgba(0,0,0,0.5)]"
      />
    </>
  );
}
