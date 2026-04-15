import { programWeeks } from "../../data/program-weeks";

export function ProgramStructure() {
  return (
    <section className="border-t border-white/5 bg-dark-card">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-32">
        <div className="mb-20">
          <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
            The Programme
          </p>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-[-0.04em] text-white max-w-4xl leading-[1.05]">
            Eight weeks from idea
            <br />
            <span className="text-text-muted">to investable founder</span>
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/5">
          {programWeeks.map((week) => (
            <div
              key={week.week}
              className="bg-dark-card p-8 group hover:bg-white/[0.03] transition-colors duration-500"
            >
              <span className="text-text-subtle text-xs uppercase tracking-[0.15em]">
                Week {week.week}
              </span>
              <h3 className="text-lg font-medium text-white mt-3 mb-3 tracking-[-0.02em]">
                {week.title}
              </h3>
              <p className="text-text-muted text-sm leading-relaxed mb-4">
                {week.description}
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {week.topics.map((topic) => (
                  <span
                    key={topic}
                    className="text-xs text-text-subtle"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
