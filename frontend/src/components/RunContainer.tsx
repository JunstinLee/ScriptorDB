import type { Run } from "../types";
import MarkdownRenderer from "./common/MarkdownRenderer";
import ImageArtifact from "./common/ImageArtifact";
import RateLimitNotice from "./common/RateLimitNotice";
import RunStatus from "./common/RunStatus";

interface RunContainerProps {
  run: Run;
}

export default function RunContainer({ run }: RunContainerProps) {
  const isRunning = run.status === "running";
  const runningTools = run.tool_invocations.filter((inv) => inv.status === "running");
  const hasRunningCrawl = runningTools.some((inv) => inv.tool_name === "crawl_webpage");
  const firstRunningTool = runningTools.find((inv) => inv.tool_name !== "crawl_webpage");

  console.log(
    "[RunContainer] run_id=%s status=%s isRunning=%s tools=%s",
    run.run_id,
    run.status,
    isRunning,
    run.tool_invocations
      .map((inv) => inv.call_id + ":" + inv.status + ":" + inv.tool_name)
      .join(", "),
  );

  return (
    <div>
      {run.final_output && (
        <div className="px-4 py-3">
          <MarkdownRenderer content={run.final_output} />
        </div>
      )}

      {run.tool_invocations.map((inv) => {
        const invData = inv.data;
        if (
          inv.tool_name !== "plot_chart" ||
          inv.status !== "success" ||
          typeof invData?.file !== "string"
        ) {
          return null;
        }
        const fileId = invData.file;
        const chartType =
          typeof invData.chart_type === "string"
            ? invData.chart_type
            : typeof inv.args.chart_type === "string"
              ? inv.args.chart_type
              : undefined;
        const title =
          typeof inv.args.title === "string" ? inv.args.title : undefined;
        return (
          <div key={inv.call_id} className="px-4 py-2 border-t border-grid">
            <ImageArtifact
              fileId={fileId}
              title={title}
              chartType={chartType}
            />
          </div>
        );
      })}

      {run.status === "error" &&
        run.error_message &&
        (run.error_type === "rate_limit" ? (
          <RateLimitNotice message={run.error_message} />
        ) : (
          <div className="border-l-[3px] border-l-vermilion bg-vermilion/5 px-4 py-3">
            <p className="text-sm text-vermilion">{run.error_message}</p>
          </div>
        ))}

      {isRunning && (
        <div className="px-4 py-3">
          <RunStatus
            variant={hasRunningCrawl ? "crawl" : firstRunningTool ? "tools" : "thinking"}
            toolName={firstRunningTool?.tool_name}
          />
        </div>
      )}
    </div>
  );
}
