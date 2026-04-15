import aiArchitect from "../../assets/ai-architect.png";

export function Architect() {
  return (
    <section className="border-t border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-16">
        <div className="flex items-center gap-6">
          <div
            className="w-16 h-16 rounded-full bg-cover bg-center shrink-0 select-none pointer-events-none"
            style={{ backgroundImage: `url(${aiArchitect})` }}
            role="img"
            aria-label="Conor Gilmartin"
          />
          <div>
            <p className="text-sm font-medium text-white">Conor Gilmartin</p>
            <p className="text-xs text-text-muted mt-1">
              AI Architect &mdash; Expert in multi-agent systems. MSc in Artificial Intelligence. Using machine learning to pay it forward to the next generation of founders.
            </p>
            <div className="flex gap-4 mt-2">
              <a href="https://conorgilmartin.com/" target="_blank" rel="noopener noreferrer" className="text-xs text-text-subtle hover:text-white transition-colors">conorgilmartin.com</a>
              <a href="https://www.linkedin.com/in/conorgilmartinn/" target="_blank" rel="noopener noreferrer" className="text-xs text-text-subtle hover:text-white transition-colors">LinkedIn</a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
