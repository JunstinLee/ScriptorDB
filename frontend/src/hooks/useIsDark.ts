import { useEffect, useState } from "react";

export function useIsDark() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof document === "undefined") return false;
    return (
      document.documentElement.classList.contains("dark") ||
      document.documentElement.getAttribute("data-theme") === "dark"
    );
  });

  useEffect(() => {
    const el = document.documentElement;

    const check = () => {
      setIsDark(
        el.classList.contains("dark") ||
          el.getAttribute("data-theme") === "dark",
      );
    };

    const observer = new MutationObserver(check);
    observer.observe(el, { attributes: true, attributeFilter: ["class", "data-theme"] });

    check();

    return () => observer.disconnect();
  }, []);

  return isDark;
}
