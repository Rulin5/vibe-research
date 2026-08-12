import { NavLink, Outlet } from "react-router-dom";
import { Star, Wallet, FileText, NotebookPen } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/utils";

const TABS = [
  { to: "/watch/watchlist", icon: Star, label: "自选股" },
  { to: "/watch/portfolio", icon: Wallet, label: "我的持仓" },
  { to: "/watch/reports", icon: FileText, label: "我的研报" },
  { to: "/watch/notes", icon: NotebookPen, label: "研究记录" },
];

export function MyFocus() {
  return (
    <div>
      <PageHeader
        title="我的关注"
        subtitle="自选股 · 持仓 · 研报 · 研究记录 · 只存本地"
      />

      {/* 二级导航 */}
      <nav className="mb-5 flex flex-wrap gap-2">
        {TABS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
              "hover:bg-muted/50 hover:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
              ({ isActive }: { isActive: boolean }) =>
                isActive
                  ? "bg-primary/15 text-primary shadow-glow"
                  : "text-muted-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* 子页面出口 */}
      <Outlet />
    </div>
  );
}
