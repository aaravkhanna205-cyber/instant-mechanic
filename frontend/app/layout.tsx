import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import {DemoProvider} from "@/lib/demo/store";
export const metadata: Metadata = { title: "Instant Mechanic Hire", description: "Internal recruitment workspace" };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {return <html lang="en" suppressHydrationWarning><body><ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange><DemoProvider>{children}</DemoProvider></ThemeProvider></body></html>}
