interface AlertBannerProps {
  variant: "error" | "success";
  message: string;
}

export default function AlertBanner({ variant, message }: AlertBannerProps) {
  const borderColor = variant === "error" ? "border-danger/40" : "border-success/40";
  const bgColor = variant === "error" ? "bg-danger/10" : "bg-success/10";
  const textColor = variant === "error" ? "text-danger" : "text-success";

  return (
    <div className={`rounded-lg border ${borderColor} ${bgColor} p-2 text-sm ${textColor}`}>
      {message}
    </div>
  );
}
