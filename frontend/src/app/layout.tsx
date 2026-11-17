import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "./globals.css";
import { Providers } from "./providers";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "ClipGen — Personal AI Video Assistant",
  description: "Auto-generate short clips dari video panjang",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="min-h-screen bg-canvas font-sans text-ink antialiased">
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("clipgen-theme")||"dark";document.documentElement.classList.toggle("dark",t==="dark")}catch(e){}`,
          }}
        />
        <Providers>
          <AuthGate>
            <AppShell>{children}</AppShell>
          </AuthGate>
        </Providers>
      </body>
    </html>
  );
}
