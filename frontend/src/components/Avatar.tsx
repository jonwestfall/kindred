import { initials } from "../utils";

export function Avatar({
  name,
  src,
  size = "medium",
}: {
  name: string;
  src?: string;
  size?: "small" | "medium" | "large";
}) {
  return (
    <span className={`avatar avatar--${size}`} aria-label={`${name} avatar`}>
      {src ? <img src={src} alt="" /> : <span>{initials(name)}</span>}
    </span>
  );
}

