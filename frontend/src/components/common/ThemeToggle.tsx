import { useCallback } from "react";
import { Switch } from "@heroui/react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";
import type { Theme } from "../../hooks/useTheme";

interface ThemeToggleProps {
  variant: "icon" | "switch";
}

export default function ThemeToggle({ variant }: ThemeToggleProps) {
  const { theme, setTheme, isDark } = useTheme();

  const resolved = theme === "system" ? "system" : isDark ? "dark" : "light";

  const toggleTheme = useCallback(() => {
    const next: Theme = isDark ? "light" : "dark";
    setTheme(next);
  }, [isDark, setTheme]);

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
          {resolved === "system" ? "System" : isDark ? "Dark Mode" : "Light Mode"}
        </span>
      </Switch.Content>
    </Switch>
  );
}
