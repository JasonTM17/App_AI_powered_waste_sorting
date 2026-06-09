type TrashSorterLogoProps = {
  className?: string;
  variant?: "mark" | "lockup";
};

export function TrashSorterLogo({ className = "", variant = "mark" }: TrashSorterLogoProps) {
  const rootClass =
    variant === "lockup"
      ? `trash-sorter-logo trash-sorter-logo-lockup ${className}`.trim()
      : `trash-sorter-logo trash-sorter-logo-mark-only ${className}`.trim();
  const src =
    variant === "lockup" ? "/brand/trash-sorter-pro-stitch-logo.png" : "/brand/trash-sorter-pro-mark.png";
  return (
    <span className={rootClass} aria-label="Trash Sorter Pro">
      <img alt="" aria-hidden="true" className="trash-sorter-logo-image" draggable={false} src={src} />
    </span>
  );
}
