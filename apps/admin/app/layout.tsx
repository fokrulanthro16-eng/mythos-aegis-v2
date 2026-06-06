import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Mythos Aegis — Command Console",
  description: "Elite infrastructure security console for Mythos Aegis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="bg-ae-base font-sans text-ae-text antialiased">
        {children}
      </body>
    </html>
  );
}
