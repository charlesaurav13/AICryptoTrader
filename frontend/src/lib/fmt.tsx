export function fmt$(v: number) {
  return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

export function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString();
}

const BADGE: Record<string, string> = {
  long: "bg-gr/10 text-gr border border-gr/20", short: "bg-re/10 text-re border border-re/20",
  buy: "bg-gr/10 text-gr border border-gr/20", sell: "bg-re/10 text-re border border-re/20",
  hold: "bg-bl/10 text-bl border border-bl/20",
  tp: "bg-gr/10 text-gr", sl: "bg-re/10 text-re", manual: "bg-pu/10 text-pu",
  volatile: "bg-ye/10 text-ye border border-ye/20",
  trending_up: "bg-gr/10 text-gr border border-gr/20",
  trending_down: "bg-re/10 text-re border border-re/20",
  ranging: "bg-t3/10 text-t2", up: "bg-gr/10 text-gr", down: "bg-re/10 text-re",
  scale_up: "bg-gr/10 text-gr", scale_down: "bg-re/10 text-re",
};

export function badge(text: string) {
  const cls = BADGE[text.toLowerCase()] ?? "bg-t3/10 text-t2";
  return <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${cls}`}>{text}</span>;
}
