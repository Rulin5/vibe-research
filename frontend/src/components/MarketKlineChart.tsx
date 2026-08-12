import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import type { IndexSeries } from "@/lib/api";

interface Props { series: IndexSeries; height?: number }

function movingAverage(values: number[], days: number): Array<number | null> {
  return values.map((_, index) => {
    if (index < days - 1) return null;
    const slice = values.slice(index - days + 1, index + 1);
    return Number((slice.reduce((sum, value) => sum + value, 0) / days).toFixed(3));
  });
}

export function MarketKlineChart({ series, height = 330 }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const option = useMemo(() => {
    const dates = series.candles.map((row) => row.trade_date.slice(5));
    const closes = series.candles.map((row) => row.close);
    return {
      animation: false,
      grid: [{ left: 58, right: 22, top: 22, height: "59%" }, { left: 58, right: 22, top: "76%", height: "13%" }],
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" }, backgroundColor: "rgba(20,28,42,.92)", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12 } },
      xAxis: [
        { type: "category", data: dates, boundaryGap: true, axisLine: { lineStyle: { color: "#aeb8c6" } }, axisLabel: { color: "#758195" }, splitLine: { show: false } },
        { type: "category", gridIndex: 1, data: dates, boundaryGap: true, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#d8dee7" } }, axisTick: { show: false } },
      ],
      yAxis: [
        { scale: true, splitLine: { lineStyle: { color: "rgba(130,145,165,.16)" } }, axisLabel: { color: "#758195" } },
        { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
      ],
      dataZoom: [{ type: "inside", xAxisIndex: [0, 1], start: 18, end: 100 }, { type: "slider", xAxisIndex: [0, 1], bottom: 1, height: 17, borderColor: "transparent", fillerColor: "rgba(80,130,210,.12)" }],
      series: [
        { name: series.name, type: "candlestick", data: series.candles.map((row) => [row.open, row.close, row.low, row.high]), itemStyle: { color: "#e34d59", color0: "#25a36f", borderColor: "#e34d59", borderColor0: "#25a36f" } },
        { name: "MA20", type: "line", data: movingAverage(closes, 20), smooth: true, symbol: "none", lineStyle: { width: 1.4, color: "#4c8ad5" } },
        { name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: series.candles.map((row) => ({ value: row.volume ?? 0, itemStyle: { color: row.close >= row.open ? "rgba(227,77,89,.55)" : "rgba(37,163,111,.55)" } })) },
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
