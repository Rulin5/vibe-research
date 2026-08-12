import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "@/components/auth/AuthProvider";
import { BrandLogo } from "@/components/common/BrandLogo";
import { ApiError } from "@/lib/api";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try { await login(username, password); navigate(params.get("next") || "/daily-review", { replace: true }); }
    catch (err) { setError(err instanceof ApiError ? err.message : "登录失败"); }
    finally { setBusy(false); }
  };
  return <main className="mx-auto flex min-h-screen max-w-sm items-center px-6"><form onSubmit={submit} className="glass w-full space-y-4 rounded-2xl p-6"><div className="flex items-center gap-3"><BrandLogo className="h-14 w-14 shadow-sm" /><div><h1 className="text-xl font-bold">登录清数智算</h1><p className="text-xs text-muted-foreground">智能投研工作台</p></div></div><input aria-label="用户名" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full rounded-lg border bg-background p-2" placeholder="用户名" autoComplete="username" required /><input aria-label="密码" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-lg border bg-background p-2" placeholder="密码" type="password" autoComplete="current-password" required />{error && <p className="text-sm text-destructive">{error}</p>}<button disabled={busy} className="w-full rounded-lg bg-primary p-2 text-primary-foreground disabled:opacity-50">{busy ? "登录中…" : "登录"}</button><p className="text-sm text-muted-foreground">没有账户？<Link className="text-primary" to="/register">注册</Link></p></form></main>;
}
