import { cn } from "@/lib/utils";

type BrandLogoProps = {
  className?: string;
};

export function BrandLogo({ className }: BrandLogoProps) {
  return (
    <img
      src="/qingshu-logo.png"
      alt="清数智算"
      className={cn("shrink-0 rounded-xl object-cover", className)}
    />
  );
}
