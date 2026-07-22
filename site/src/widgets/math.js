export function softmax(z, T = 1) {
  const m = Math.max(...z);
  const e = z.map((v) => Math.exp((v - m) / T));
  const s = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / s);
}

// t in [0,1] -> dark surface to accent gold (heatmap cells)
export function heatColor(t) {
  const a = [28, 31, 40];
  const b = [238, 209, 27];
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
