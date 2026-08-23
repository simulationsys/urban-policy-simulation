import * as React from "react"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function GlassCard({ children, className, ...props }: GlassCardProps) {
  return (
    <div className={cn("rounded-md gradient-border-shell", className)} {...props}>
      <div className="rounded-md glass-surface shadow-dual p-6 h-full text-white flex flex-col">
        {children}
      </div>
    </div>
  )
}
