import { Skeleton } from "./ui/Skeleton";

export function ScreenSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading job">
      <Skeleton className="h-32 w-full" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <div className="lg:col-span-3">
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    </div>
  );
}
