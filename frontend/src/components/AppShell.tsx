"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Chat" },
  { href: "/tools", label: "Tools" },
  { href: "/sessions", label: "Sessions" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-forge-glow" />
      <div className="pointer-events-none absolute inset-0 bg-forge-grid opacity-40" />

      <header className="relative z-10 border-b border-steel-700/60 bg-steel-950/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-end justify-between gap-6 px-6 py-5">
          <div>
            <p className="font-display text-3xl tracking-tight text-ember-400 md:text-4xl">
              ForgeAI
            </p>
            <p className="mt-1 max-w-md text-sm text-steel-300">
              Agent operating system console — plan, execute, inspect.
            </p>
          </div>
          <nav className="flex gap-1 pb-1">
            {links.map((link) => {
              const active =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-2 text-sm transition ${
                    active
                      ? "bg-ember-500/15 text-ember-300"
                      : "text-steel-300 hover:bg-steel-800/80 hover:text-steel-50"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
