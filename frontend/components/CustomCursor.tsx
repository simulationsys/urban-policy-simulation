"use client";

import { useEffect, useRef } from "react";

export default function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    let mouseX = -100;
    let mouseY = -100;
    let isHovering = false;
    let animationFrameId: number;

    const moveCursor = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    };

    const handleHoverStart = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const computedStyle = window.getComputedStyle(target);
      if (
        computedStyle.cursor === "pointer" ||
        target.closest("button") ||
        target.closest("a")
      ) {
        isHovering = true;
      } else {
        isHovering = false;
      }
    };

    const render = () => {
      if (cursorRef.current) {
        // Zero latency direct transform mapping
        cursorRef.current.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0) scale(${isHovering ? 2.5 : 1})`;
        
        // Use mix blend mode to make it visible across dark and light backgrounds
        cursorRef.current.style.mixBlendMode = "difference";
        cursorRef.current.style.backgroundColor = isHovering ? "#DCD6CC" : "#ffffff";
      }
      animationFrameId = requestAnimationFrame(render);
    };

    window.addEventListener("mousemove", moveCursor, { passive: true });
    window.addEventListener("mouseover", handleHoverStart, { passive: true });
    
    // Start the render loop
    render();

    document.body.style.cursor = "none";

    return () => {
      window.removeEventListener("mousemove", moveCursor);
      window.removeEventListener("mouseover", handleHoverStart);
      cancelAnimationFrame(animationFrameId);
      document.body.style.cursor = "auto";
    };
  }, []);

  return (
    <div
      ref={cursorRef}
      className="pointer-events-none fixed top-0 left-0 z-[9999] rounded-full transition-transform duration-100 ease-out"
      style={{
        width: "12px",
        height: "12px",
        marginLeft: "-6px", // Center the dot
        marginTop: "-6px", // Center the dot
        willChange: "transform",
        opacity: 1
      }}
    />
  );
}
