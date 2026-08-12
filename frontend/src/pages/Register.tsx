import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/components/auth/AuthProvider";
import { BrandLogo } from "@/components/common/BrandLogo";
import { ApiError } from "@/lib/api";

export function Register() {
  const { register } = useAuth(); const navigate = useNavigate();
  const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [phone, setPhone] = useState(""); const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); setError(null); try { await register(username, password, phone); navigate("/daily-review", { replace: true }); } catch (cause) { setError(cause instanceof ApiError ? cause.message : "注册失败"); } finally { setBusy(false); } };
  return <main className="mx-auto flex min-h-screen max-w-sm items-center px-6"><form onSubmit={submit} className="glass w-full space-y-4 rounded-2xl p-6"><div className="flex items-center gap-3"><BrandLogo className="h-14 w-14 shadow-sm" /><div><h1 className="text-xl font-bold">创建账户</h1><p className="text-xs text-muted-foreground">清数智算 · 智能投研工作台</p></div></div><p className="text-sm text-muted-foreground">请填写用户名、密码和手机号。</p><input aria-label="用户名" value={username} onChange={(event) => setUsername(event.target.value)} className="w-full rounded-lg border bg-background p-2" placeholder="用户名" autoComplete="username" required /><input aria-label="密码" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-lg border bg-background p-2" placeholder="密码" type="password" autoComplete="new-password" required /><input aria-label="手机号" value={phone} onChange={(event) => setPhone(event.target.value)} className="w-full rounded-lg border bg-background p-2" placeholder="手机号" type="tel" autoComplete="tel" required />{error && <p className="text-sm text-destructive">{error}</p>}<button disabled={busy} className="w-full rounded-lg bg-primary p-2 text-primary-foreground disabled:opacity-50">{busy ? "注册中…" : "注册"}</button><p className="text-sm text-muted-foreground">已有账户？<Link className="text-primary" to="/login">登录</Link></p></form></main>;
}
