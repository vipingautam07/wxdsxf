import {
  ArrowUpRight,
  CalendarDays,
  ChartNoAxesCombined,
  Compass,
  Database,
  LayoutDashboard,
  ShieldCheck,
  Wind,
} from "lucide-react";
import { NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import { Dashboard } from "@/pages/Dashboard";
import { Accuracy } from "@/pages/Accuracy";
import { Explorer } from "@/pages/Explorer";
import { useLocation } from "react-router-dom";

const navigation = [
  { path: "/", title: "Day-ahead dashboard", icon: LayoutDashboard },
  { path: "/accuracy", title: "Forecast accuracy", icon: ChartNoAxesCombined },
  { path: "/explorer", title: "Forecast explorer", icon: Compass },
];
const headings: Record<string, [string, string]> = {
  "/": [
    "The next day, in clearer view.",
    "Reconstruct the wind forecast behind a day-ahead purchasing decision.",
  ],
  "/accuracy": [
    "Understand the forecast error.",
    "Measure historical performance, directional bias and the days that mattered.",
  ],
  "/explorer": [
    "Go back to the decision.",
    "Follow every retained revision and see exactly what was available at the cutoff.",
  ],
};

export default function App() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const decision = /^2026-01-(0[1-9]|[12]\d|3[01])$/.test(
    params.get("date") || "",
  )
    ? params.get("date")!
    : "2026-01-15";
  const cutoff = /^([01]\d|2[0-3]):[0-5]\d$/.test(params.get("cutoff") || "")
    ? params.get("cutoff")!
    : "11:00";
  const hour = /^([01]\d|2[0-3])$/.test(params.get("hour") || "")
    ? params.get("hour")!
    : "12";
  const update = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set(key, value);
      return next;
    });
  const title = headings[location.pathname] || [
    "Page not found",
    "Return to one of the WindScope analysis pages.",
  ];
  const search = new URLSearchParams({
    date: decision,
    cutoff,
    hour,
  }).toString();
  return (
    <div className="min-h-screen lg:pl-[224px]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded focus:bg-white focus:p-3"
      >
        Skip to content
      </a>
      <aside className="border-b border-[#dce5df] bg-[#f0f4ef] lg:fixed lg:inset-y-0 lg:left-0 lg:z-10 lg:flex lg:w-[224px] lg:flex-col lg:border-r lg:border-b-0">
        <NavLink to="/" className="flex items-center gap-2.5 px-6 py-6">
          <span className="flex size-9 items-center justify-center rounded-xl bg-[#173e43] text-[#c1f2ce]">
            <Wind size={22} />
          </span>
          <span className="text-[22px] font-semibold tracking-[-.07em]">
            WindScope<span className="text-primary">.</span>
          </span>
        </NavLink>
        <div className="hidden px-6 pb-6 lg:block">
          <div className="rounded-lg border border-[#dce5df] bg-[#e8eee6] px-3 py-2.5">
            <div className="eyebrow text-[9px]">Workspace</div>
            <div className="mt-1 flex items-center justify-between text-xs font-medium">
              GB wind intelligence{" "}
              <span className="rounded border border-[#cbd9cd] px-1 py-0.5 text-[8px] tracking-wide text-[#63796b]">
                PILOT
              </span>
            </div>
          </div>
        </div>
        <div className="hidden px-6 pb-3 text-[10px] font-medium tracking-[.13em] text-[#5a6d61] lg:block">
          ANALYSIS
        </div>
        <nav
          aria-label="Main navigation"
          className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:px-3"
        >
          {navigation.map((item) => (
            <NavLink
              key={item.path}
              to={`${item.path}?${search}`}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-3 text-[12px] transition-colors ${isActive ? "bg-white font-semibold text-[#1c5b45] shadow-[0_1px_3px_#1932380a]" : "text-[#697c70] hover:bg-[#e7eee5]"}`
              }
            >
              <item.icon size={16} strokeWidth={1.7} />
              {item.title}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-4 px-6 py-6 lg:block">
          <div className="rounded-xl border border-[#d8e3d6] bg-[#e9f0e5] p-4">
            <ShieldCheck size={20} className="text-[#6c8d6f]" />
            <p className="mt-2 text-xs font-semibold">Built on official data</p>
            <p className="mt-1 text-[10px] leading-relaxed text-[#5e7165]">
              Elexon forecast publications and reported generation. Preserved
              for historical analysis.
            </p>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-[#5e7165]">
            <Database size={13} />
            January 2026 study
          </div>
        </div>
      </aside>
      <header className="flex min-h-[65px] flex-wrap items-center justify-between gap-3 border-b border-[#e1e8e3] bg-white/80 px-5 py-3 sm:px-8">
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-[#78a68b]" />
          UK Wind Forecast Intelligence{" "}
          <span className="mx-1 text-[#cad5ce]">/</span>
          <span className="font-medium text-[#536b5e]">
            {navigation.find((item) => item.path === location.pathname)
              ?.title || "Analysis"}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <CalendarDays size={13} />
          1–31 Jan 2026
          <span className="rounded border border-[#dbe4dd] px-2 py-1 text-[9px] tracking-wider">
            HISTORICAL STUDY
          </span>
        </div>
      </header>
      <main
        id="main"
        className="mx-auto max-w-[1600px] px-5 py-7 sm:px-8 sm:py-8"
      >
        <div className="mb-7 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow mb-2">
              {location.pathname === "/explorer"
                ? "POINT-IN-TIME EXPLORER"
                : location.pathname === "/accuracy"
                  ? "PERFORMANCE ANALYSIS"
                  : "DAY-AHEAD INTELLIGENCE"}
            </p>
            <h1 className="text-[27px] font-semibold leading-tight tracking-[-.055em] sm:text-[32px]">
              {title[0]}
            </h1>
            <p className="mt-2 max-w-xl text-[12px] leading-relaxed text-muted-foreground">
              {title[1]}
            </p>
          </div>
          <label className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <span>
              Purchasing cutoff
              <br />
              <span className="text-[9px]">UK local · pilot assumption</span>
            </span>
            <input
              aria-label="Purchasing cutoff"
              type="time"
              value={cutoff}
              onChange={(e) =>
                e.target.value && update("cutoff", e.target.value)
              }
            />
          </label>
        </div>
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                decision={decision}
                cutoff={cutoff}
                setDecision={(value) => update("date", value)}
                search={search}
              />
            }
          />
          <Route path="/accuracy" element={<Accuracy cutoff={cutoff} />} />
          <Route
            path="/explorer"
            element={
              <Explorer
                decision={decision}
                cutoff={cutoff}
                hour={hour}
                setDecision={(value) => update("date", value)}
                setHour={(value) => update("hour", value)}
              />
            }
          />
          <Route
            path="*"
            element={
              <NavLink className="text-primary underline" to="/">
                Return to dashboard
              </NavLink>
            }
          />
        </Routes>
        <footer className="mt-5 flex flex-wrap justify-between gap-3 text-[10px] leading-relaxed text-[#61746a]">
          <span>
            Great Britain system-operator-visible wind · Hourly evaluation ·
            Retrospective actuals
          </span>
          <a
            href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 hover:text-primary"
          >
            Data methodology <ArrowUpRight size={11} />
          </a>
        </footer>
      </main>
    </div>
  );
}
