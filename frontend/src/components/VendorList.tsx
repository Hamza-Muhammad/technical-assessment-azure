import type { RankedCandidate, VendorProfile } from "../types/contracts";
import { VendorCard } from "./VendorCard";

interface VendorListProps {
  ranked: RankedCandidate[];
  vendors: Record<string, VendorProfile>;
  selectedVendorId: string;
  onSelect: (vendorId: string) => void;
}

export function VendorList({ ranked, vendors, selectedVendorId, onSelect }: VendorListProps) {
  return (
    <div role="radiogroup" aria-label="Ranked vendor recommendations" className="space-y-3">
      {ranked.map((candidate) => (
        <VendorCard
          key={candidate.vendorId}
          candidate={candidate}
          vendor={vendors[candidate.vendorId]}
          selected={candidate.vendorId === selectedVendorId}
          isTopPick={candidate.rank === 1}
          onSelect={() => onSelect(candidate.vendorId)}
        />
      ))}
    </div>
  );
}
