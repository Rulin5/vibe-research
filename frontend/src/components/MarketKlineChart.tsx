import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import type { IndexSeries } from "@/lib/api";

interface Props { series: IndexSeries; height?: number }

export function MarketKlineChart({ series, height = 330 }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const option = useMemo(() => {
    const dates = series.candles.map((row) => row.trade_date.slice(5));
    return {
      animation: false,
      grid: { left: 58, right: 22, top: 22, bottom: 42 },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" }, backgroundColor: "rgba(20,28,42,.92)", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12 } },
      xAxis: { type: "category", data: dates, boundaryGap: true, axisLine: { lineStyle: { color: "#aeb8c6" } }, axisLabel: { color: "#758195" }, splitLine: { show: false } },
      yAxis: { scale: true, splitLine: { lineStyle: { color: "rgba(130,145,165,.16)" } }, axisLabel: { color: "#758195" } },
      series: [
        { name: series.name, type: "candlestick", data: series.candles.map((row) => [row.open, row.close, row.low, row.high]), itemStyle: { color: "#e34d59", color0: "#25a36f", borderColor: "#e34d59", borderColor0: "#25a36f" } },
      ],
    };
  }, [series]);

  useEffect(() => {
    if (!host.current) return;
    const chart = echarts.init(host.current);
    chart.setOption(option);
    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(host.current);
    return () => { resizeObserver.disconnect(); chart.dispose(); };
  }, [option]);

  return <div ref={host} style={{ height }} role="img" aria-label={`${series.name}日K线与成交量`} />;
}
