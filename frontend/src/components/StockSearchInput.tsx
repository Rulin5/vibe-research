import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Search } from "lucide-react";
import { api, type StockSearchResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSelect?: (stock: StockSearchResult) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  allowGlobalCode?: boolean;
}

export function StockSearchInput({ value, onChange, onSelect, disabled, placeholder = "输入股票名称或代码", className, allowGlobalCode = false }: Props) {
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<StockSearchResult | null>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = value.trim();
    if (selected?.code === query || query.length < 2) { setResults([]); setOpen(false); return; }
    const timer = window.setTimeout(() => {
      setLoading(true);
      api.stockSearch(query, 8).then((data) => { setResults(data.results); setOpen(true); }).catch(() => { setResults([]); setOpen(false); }).finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [value, selected]);

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const choose = (stock: StockSearchResult) => {
    setSelected(stock); onChange(stock.code); onSelect?.(stock); setResults([]); setOpen(false);
  };

  return <div ref={root} className={cn("relative", className)}>
    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
    <input value={value} disabled={disabled} onChange={(event) => {
      const raw = event.target.value;
      setSelected(null);
      onChange(allowGlobalCode ? raw.replace(/[^a-zA-Z0-9.\u4e00-\u9fa5]/g, "").toUpperCase().slice(0, 24) : raw.replace(/[^a-zA-Z0-9.\u4e00-\u9fa5]/g, "").slice(0, 24));
    }} onFocus={() => results.length && setOpen(true)} placeholder={placeholder} autoComplete="off" className="w-full rounded-lg border border-border bg-background/70 py-2 pl-8 pr-8 text-sm outline-none focus:border-primary/60" />
    {loading && <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />}
    {selected && !loading && <Check className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-success" />}
    {open && <div className="absolute z-50 mt-1 max-h-72 w-full min-w-64 overflow-auto rounded-xl border border-border bg-card p-1.5 shadow-xl">
      {results.length ? results.map((stock) => <button type="button" key={stock.ts_code} onClick={() => choose(stock)} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-primary/10"><span className="min-w-0"><strong className="block truncate text-sm">{stock.name}</strong><span className="text-[11px] text-muted-foreground">{stock.market}{stock.industry ? ` · ${stock.industry}` : ""}</span></span><span className="ml-4 font-mono text-xs text-muted-foreground">{stock.code}</span></button>) : <p className="px-3 py-4 text-center text-xs text-muted-foreground">没有匹配的A股证券</p>}
    </div>}
    {selected && <p className="mt-1 text-[11px] text-muted-foreground">已选择：<b className="text-foreground">{selected.name}</b> <span className="font-mono">{selected.code}</span></p>}
  </div>;
}
