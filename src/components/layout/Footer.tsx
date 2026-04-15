import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-16">
        <div className="grid md:grid-cols-3 gap-12 mb-16">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-4">
              The Overlooked Founders
            </p>
            <p className="text-text-muted text-sm leading-relaxed">
              On a mission to back 10,000 high-potential
              founders from lower socioeconomic backgrounds.
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-4">
              Navigate
            </p>
            <div className="flex flex-col gap-3">
              <Link to="/" className="text-sm text-text-muted hover:text-white transition-colors duration-300">Home</Link>
              <Link to="/ask" className="text-sm text-text-muted hover:text-white transition-colors duration-300">Ask a Mentor</Link>
              <Link to="/apply" className="text-sm text-text-muted hover:text-white transition-colors duration-300">Apply</Link>
              <Link to="/dashboard" className="text-sm text-text-muted hover:text-white transition-colors duration-300">Dashboard</Link>
            </div>
          </div>
          <div />
        </div>
        <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-text-subtle text-xs uppercase tracking-[0.15em]">
            &copy; {new Date().getFullYear()} The Overlooked Founders. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
