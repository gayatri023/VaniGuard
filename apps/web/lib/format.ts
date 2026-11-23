const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
  "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

/** ₹1,50,000: Indian digit grouping. */
export const inr = (n: number): string => `\u20b9${new Intl.NumberFormat("en-IN").format(n)}`;

const below100 = (n: number): string => (n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? ` ${ONES[n % 10]}` : ""));
const below1000 = (n: number): string =>
  n >= 100 ? `${ONES[Math.floor(n / 100)]} hundred${n % 100 ? ` ${below100(n % 100)}` : ""}` : below100(n);

/** Amount in words, Indian system: "one hundred fifty rupees", "two lakh five thousand rupees". */
export function amountInWords(n: number): string {
  if (!Number.isInteger(n) || n <= 0 || n >= 1_000_000_000) return "";
  const parts: string[] = [];
  let rest = n;
  for (const [unit, name] of [[10_000_000, "crore"], [100_000, "lakh"], [1000, "thousand"]] as const) {
    const q = Math.floor(rest / unit);
    if (q) parts.push(`${below1000(q)} ${name}`);
    rest %= unit;
  }
  if (rest) parts.push(below1000(rest));
  return `${parts.join(" ")} ${n === 1 ? "rupee" : "rupees"}`;
}

export const initials = (name: string): string =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
