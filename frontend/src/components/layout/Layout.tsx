import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Bookmark, ChevronsLeft, ChevronsRight, CloudMoon, Landmark, LayoutGrid,
  BotMessageSquare, CircleUser, LogOut, MoonStar, Radar, Search, Settings, Sun, type LucideIcon,
} from "lucide-react";
import { Toaster } from "sonner";

import { BrandLogo } from "@/components/common/BrandLogo";
import { type ThemeName, useDarkMode } from "@/hooks/useDarkMode";
import { storageGet, storageSet } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/auth/AuthProvider";

const NAV = [
  { to: "/daily-review", icon: Activity, label: "每日复盘" },
  { to: "/intel", icon: Radar, label: "资讯雷达" },
  { to: "/sectors", icon: LayoutGrid, label: "板块中心" },
  { to: "/stock-data", icon: Search, label: "个股数据" },
  { to: "/ai-research/analysis", icon: BotMessageSquare, label: "AI研究" },
  { to: "/asset-allocation", icon: Landmark, label: "资产配置" },
  { to: "/watch", icon: Bookmark, label: "我的关注" },
  { to: "/settings", icon: Settings, label: "接入 AI" },
];

const THEME_OPTIONS: Array<{ value: ThemeName; label: string; icon: LucideIcon }> = [
  { value: "light", label: "亮色", icon: Sun },
  { value: "soft", label: "浅灰", icon: CloudMoon },
  { value: "deep", label: "夜蓝", icon: MoonStar },
];

export function Layout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { theme, setTheme, isDark } = useDarkMode();
  const [collapsed, setCollapsed] = useState(() => storageGet("vr-sidebar") === "collapsed");

  useEffect(() => {
    storageSet("vr-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  return (
    <div className="flex h-screen">
      <aside className={cn(
        "glass z-10 m-2 flex shrink-0 flex-col rounded-2xl transition-all duration-200",
        collapsed ? "w-14" : "w-60",
      )}>
        <div className={cn("border-b border-border/50", collapsed ? "flex justify-center p-3" : "p-4")}>
          <Link to="/daily-review" className={cn("flex items-center", collapsed ? "justify-center" : "gap-2")}>
            <BrandLogo className={collapsed ? "h-8 w-8" : "h-10 w-10"} />
            {!collapsed && <span className="text-lg font-extrabold tracking-tight">清数智算</span>}
          </Link>
          {!collapsed && <p className="mt-1 text-[11px] text-muted-foreground">个人 AI 投研系统 · A股/美股/港股</p>}
        </div>

        <nav className={cn("flex-1 space-y-1 overflow-auto", collapsed ? "p-1.5" : "p-2.5")}>
          {NAV.map(({ to, icon: Icon, label }) => {
            const active = to === "/watch"
              ? pathname.startsWith("/watch")
              : to.startsWith("/ai-research") ? pathname.startsWith("/ai-research") : pathname === to;
            return (
              <div key={to}>
                <Link
                  to={to}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "flex items-center rounded-lg text-sm transition-colors",
                    collapsed ? "justify-center p-2.5" : "gap-2.5 px-3 py-2.5",
                    active
                      ? "bg-primary/15 font-medium text-primary shadow-glow"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!collapsed && label}
                </Link>
              </div>
            );
          })}
        </nav>

        <div className={cn("border-t border-border/50", collapsed ? "flex flex-col items-center gap-2 p-2" : "space-y-2 p-3")}>
          <div className={cn("rounded-lg bg-muted/45", collapsed ? "p-1.5" : "p-2")}>
            <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-2")} title={user?.username || "当前账号"}>
              <CircleUser className="h-4 w-4 shrink-0 text-muted-foreground" />
              {!collapsed && <span className="min-w-0 flex-1 truncate text-xs font-medium">{user?.username || "当前账号"}</span>}
            </div>
            <button type="button" onClick={() => { void logout().finally(() => navigate("/login", { replace: true })); }} title="切换账号" className={cn("mt-1 flex items-center rounded-md text-xs text-muted-foreground hover:bg-background hover:text-foreground", collapsed ? "h-8 w-8 justify-center" : "w-full gap-1.5 px-2 py-1.5")}>
              <LogOut className="h-3.5 w-3.5" />
              {!collapsed && <span>切换账号</span>}
            </button>
          </div>
          <div className={cn("flex rounded-lg bg-muted/45 p-1", collapsed ? "flex-col gap-1" : "w-full")}>
            {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                title={label}
                aria-label={`切换${label}主题`}
                className={cn(
                  "flex items-center justify-center rounded-md px-2 py-1.5 text-[11px] transition-colors",
                  collapsed ? "h-8 w-8" : "flex-1 gap-1",
                  theme === value ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {!collapsed && <span>{label}</span>}
              </button>
            ))}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn("rounded p-1.5 text-muted-foreground transition-colors hover:text-foreground", collapsed && "mx-auto")}
            title={collapsed ? "展开侧栏" : "收起侧栏"}
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <Outlet />
        </div>
      </main>
      <Toaster position="bottom-right" theme={isDark ? "dark" : "light"} richColors closeButton duration={3500} />
    </div>
  );
}
