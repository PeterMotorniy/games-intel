import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router";

import { GamePage } from "./pages/game";
import { ListPage } from "./pages/list";
import { MonitorPage } from "./pages/monitor";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <Link className="site-title" to="/">
            Games Intel
          </Link>
          <nav className="site-nav" aria-label="Main">
            <NavLink className="site-nav__link" to="/" end>
              Catalog
            </NavLink>
            <NavLink className="site-nav__link" to="/monitor">
              Monitor
            </NavLink>
          </nav>
        </header>
        <main id="main">
          <Routes>
            <Route path="/" element={<ListPage />} />
            <Route path="/games/:slug" element={<GamePage />} />
            <Route path="/monitor" element={<MonitorPage />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
