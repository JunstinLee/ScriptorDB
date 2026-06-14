import { useCallback, useEffect, useState } from "react";
import { Switch } from "@heroui/react";
import { Moon, Sun } from "lucide-react";

interface ThemeToggleProps {
  variant: "icon" | "switch";
}

export default function ThemeToggle({ variant }: ThemeToggleProps) {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const html = document.documentElement;
    if (isDark) {
      html.classList.add("dark");
      html.setAttribute("data-theme", "dark");
    } else {
      html.classList.remove("dark");
      html.setAttribute("data-theme", "light");
    }
  }, [isDark]);

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  if (variant === "icon") {
    return (
      <button
        className="rounded-lg p-1.5 hover:bg-default/50 text-muted hover:text-foreground transition-colors"
        onClick={toggleTheme}
        aria-label="Toggle theme"
      >
        {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    );
  }

  return (
    <Switch isSelected={isDark} onChange={toggleTheme} size="sm">
      <Switch.Control>
        <Switch.Thumb>
          <Switch.Icon>
            {isDark ? <Moon className="h-3 w-3" /> : <Sun className="h-3 w-3" />}
          </Switch.Icon>
        </Switch.Thumb>
      </Switch.Control>
      <Switch.Content>
        <span className="text-xs font-medium">
          {isDark ? "Dark Mode" : "Light Mode"}
        </span>
      </Switch.Content>
    </Switch>
  );
}
