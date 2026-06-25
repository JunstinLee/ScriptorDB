import { useTheme } from "./useTheme";

export function useIsDark() {
  const { isDark } = useTheme();
  return isDark;
}
