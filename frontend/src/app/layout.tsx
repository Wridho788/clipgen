import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AuthGate } from "@/components/AuthGate";

export const metadata: Metadata = {
  title: "ClipGen — Personal AI Video Assistant",
  description: "Auto-generate short clips dari video panjang",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="min-h-screen bg-slate-50 text-slate-950 antialiased dark:bg-[#05070d] dark:text-slate-100">
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("clipgen-theme")||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.classList.toggle("dark",t==="dark")}catch(e){}`,
          }}
        />
        <Providers>
          <AuthGate>
            <div className="clipgen-app min-h-screen">
              <div className="mx-auto max-w-6xl p-4 sm:p-6">{children}</div>
            </div>
          </AuthGate>
        </Providers>
      </body>
    </html>
  );
}
