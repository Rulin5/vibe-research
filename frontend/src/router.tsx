import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { DailyReview } from "@/pages/DailyReview";
import { Intel } from "@/pages/Intel";
import { Sectors } from "@/pages/Sectors";
import { SectorDetail } from "@/pages/SectorDetail";
import { Debate } from "@/pages/Debate";
import { StockData } from "@/pages/StockData";
import { MyFocus } from "@/pages/MyFocus";
import { Watchlist } from "@/pages/Watchlist";
import { Portfolio } from "@/pages/Portfolio";
import { MyReports } from "@/pages/MyReports";
import { Notes } from "@/pages/Notes";
import { Settings } from "@/pages/Settings";
import { Login } from "@/pages/Login";
import { Register } from "@/pages/Register";
import { RequireAuth } from "@/components/auth/RequireAuth";

const AssetAllocation = lazy(() => import("@/pages/AssetAllocation"));

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Navigate to="/daily-review" replace /> },
      { path: "/daily-review", element: <DailyReview /> },
      { path: "/intel", element: <Intel /> },
      { path: "/sectors", element: <Sectors /> },
      { path: "/sectors/:kind/:code", element: <SectorDetail /> },
      { path: "/stock-data", element: <StockData /> },
      { path: "/debate", element: <Debate /> },
      { path: "/asset-allocation", element: <Suspense fallback={null}><AssetAllocation /></Suspense> },
      { path: "/settings", element: <RequireAuth><Settings /></RequireAuth> },

      // 我的关注（一级入口）
      {
        path: "/watch",
        element: <RequireAuth><MyFocus /></RequireAuth>,
        children: [
          { index: true, element: <Navigate to="watchlist" replace /> },
          { path: "watchlist", element: <Watchlist /> },
          { path: "portfolio", element: <Portfolio /> },
          { path: "reports", element: <MyReports /> },
          { path: "notes", element: <Notes /> },
        ],
      },

      // 旧路由 → 兼容 redirect
      { path: "/watchlist", element: <Navigate to="/watch/watchlist" replace /> },
      { path: "/portfolio", element: <Navigate to="/watch/portfolio" replace /> },
      { path: "/my-reports", element: <Navigate to="/watch/reports" replace /> },
      { path: "/notes", element: <Navigate to="/watch/notes" replace /> },
    ],
  },
]);
