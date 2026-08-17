import { BotMessageSquare, FlaskConical } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { to: "/ai-research/analysis", label: "AI分析", icon: FlaskConical },
  { to: "/ai-research/debate", label: "AI辩论", icon: BotMessageSquare },
];

export function AIResearchLayout() {
  const { search } = useLocation();
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-border/60 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-glow">AI研究</h1>
          <p className="mt-1 text-sm text-muted-foreground">在AI分析与AI辩论之间切换，标的代码会随页面保留。</p>
        </div>
        <nav className="flex rounded-xl border border-border bg-card/60 p-1" aria-label="AI研究子页面">
          {TABS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={`${to}${search}`}
              className={({ isActive }) => cn(
                "inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm transition-colors",
                isActive ? "bg-primary/15 font-medium text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
      </div>
      <Outlet />
    </div>
  );
}
