import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import { useState } from "react";
import clsx from "clsx";
import { OfflineBanner } from "@/components/common/OfflineBanner";
import { FleetOverview } from "@/components/dashboard/FleetOverview";
import { DamageHistory } from "@/components/dashboard/DamageHistory";
import { AccuracyDashboard } from "@/components/dashboard/AccuracyDashboard";
import { InspectionFlow } from "@/components/inspection/InspectionFlow";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

// Placeholder pages -- these are route-level wrappers that compose the feature components.
// In a production app each would be its own file under src/pages/.

function DashboardPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">Dashboard</h1>
      <FleetOverview />
    </div>
  );
}

function AssetsPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">Fleet</h1>
      <DamageHistory />
    </div>
  );
}

function AssetDetailPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">Asset Details</h1>
      <p className="text-dock-500 text-sm">
        Asset detail view with inspection history and damage records.
      </p>
    </div>
  );
}

function NewInspectionPage() {
  return <InspectionFlow />;
}

function InspectionDetailPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">
        Inspection Details
      </h1>
      <p className="text-dock-500 text-sm">
        Full inspection detail with photos, findings, and comparison views.
      </p>
    </div>
  );
}

function InspectionReviewPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">
        Review Findings
      </h1>
      <p className="text-dock-500 text-sm">
        Damage review interface with before/after comparison and finding review
        cards.
      </p>
    </div>
  );
}

function SessionsPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">Rental Sessions</h1>
      <p className="text-dock-500 text-sm">
        List of rental sessions with status and linked inspections.
      </p>
    </div>
  );
}

function MetricsPage() {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-navy-900 mb-6">AI Accuracy</h1>
      <AccuracyDashboard />
    </div>
  );
}

// Navigation items
const NAV_ITEMS = [
  {
    to: "/",
    label: "Dashboard",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
      </svg>
    ),
  },
  {
    to: "/assets",
    label: "Fleet",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-2.671a2.25 2.25 0 01-1.342-.448L13.4 11.368a2.25 2.25 0 00-1.342-.448H6.25a2.25 2.25 0 00-2.197 1.78l-.756 3.78m0 0h10.5" />
      </svg>
    ),
  },
  {
    to: "/sessions",
    label: "Rentals",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
      </svg>
    ),
  },
  {
    to: "/metrics",
    label: "Accuracy",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
];

// Full-screen routes that hide the sidebar layout
const FULL_SCREEN_ROUTES = ["/inspections/new"];

function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Check if current route should be full-screen
  const isFullScreen = FULL_SCREEN_ROUTES.some((route) =>
    location.pathname.startsWith(route),
  );

  if (isFullScreen) {
    return (
      <>
        <OfflineBanner />
        {children}
      </>
    );
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Mobile header */}
      <header className="lg:hidden bg-navy-900 text-white sticky top-0 z-40">
        <OfflineBanner />
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-marine-500 flex items-center justify-center">
              <span className="text-sm font-bold text-white">DG</span>
            </div>
            <span className="font-semibold text-base">DockGuard</span>
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-navy-800 transition-colors"
            aria-label={sidebarOpen ? "Close menu" : "Open menu"}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {sidebarOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              )}
            </svg>
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-30 w-64 bg-navy-900 text-white transform transition-transform duration-200 ease-in-out",
          "lg:relative lg:transform-none lg:flex lg:flex-col",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        {/* Logo (desktop) */}
        <div className="hidden lg:flex items-center gap-3 px-6 py-5 border-b border-navy-800">
          <div className="w-9 h-9 rounded-lg bg-marine-500 flex items-center justify-center">
            <span className="text-sm font-bold text-white">DG</span>
          </div>
          <div>
            <span className="font-bold text-base">DockGuard</span>
            <p className="text-[10px] text-navy-300 uppercase tracking-wider">
              Marine Inspection
            </p>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1 mt-14 lg:mt-0">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-navy-800 text-white"
                    : "text-navy-300 hover:bg-navy-800 hover:text-white",
                )
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="px-3 py-4 border-t border-navy-800">
          <NavLink
            to="/inspections/new"
            onClick={() => setSidebarOpen(false)}
            className="flex items-center justify-center gap-2 px-4 py-2.5 bg-marine-500 hover:bg-marine-600 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Inspection
          </NavLink>
        </div>
      </aside>

      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="hidden lg:block">
          <OfflineBanner />
        </div>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/assets/:id" element={<AssetDetailPage />} />
        <Route path="/inspections/new" element={<NewInspectionPage />} />
        <Route path="/inspections/:id" element={<InspectionDetailPage />} />
        <Route
          path="/inspections/:id/review"
          element={<InspectionReviewPage />}
        />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
      </Routes>
    </Layout>
  );
}
