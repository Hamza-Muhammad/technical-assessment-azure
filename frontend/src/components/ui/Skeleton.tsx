interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`relative overflow-hidden rounded-lg bg-slate-200/70 animate-shimmer ${className}`} />;
}
