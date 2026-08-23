import type { Metadata } from "next";
import { Outfit, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import LenisProvider from "@/components/layout/LenisProvider";
import CustomCursor from "@/components/ui/CustomCursor";
import { ThemeProvider } from "@/components/liquid-glass/ThemeProvider";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Simulationsys | Urban Policy Simulation",
  description: "A sophisticated urban policy simulation command center.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${outfit.variable} ${jetbrainsMono.variable} antialiased h-full`}>
      <head>
        
      </head>
      <body className="min-h-full flex flex-col relative selection:bg-primary/30">
        <ThemeProvider defaultTheme="dark">
          <LenisProvider>
            <CustomCursor />
            {children}
          </LenisProvider>
        </ThemeProvider>
        
      </body>
    </html>
  );
}
