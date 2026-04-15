interface SourceCitationProps {
  source: string;
}

export function SourceCitation({ source }: SourceCitationProps) {
  return (
    <span className="inline-flex items-center text-xs text-text-subtle border border-white/10 px-3 py-1">
      {source}
    </span>
  );
}
