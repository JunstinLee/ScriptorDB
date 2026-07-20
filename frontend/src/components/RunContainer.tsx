import { Spinner } from "@heroui/react";
import { Globe, Loader2 } from "lucide-react";
import type { Run } from "../types";
import MarkdownRenderer from "./common/MarkdownRenderer";
import ImageArtifact from "./common/ImageArtifact";

interface RunContainerProps {
  run: Run;
}

export default function RunContainer({ run }: RunContainerProps) {
  const isRunning = run.status === "running";
  const hasRunningTool = run.tool_invocations.some(
    (t) => t.status === "running",
  );
  const hasRunningCrawl = run.tool_invocations.some(
    (t) => t.status === "running" && t.tool_name === "crawl_webpage",
  );
  const hasRunningOtherTool = run.tool_invocations.some(
    (t) => t.status === "running" && t.tool_name !== "crawl_webpage",
  );

  console.log(
    "[RunContainer] run_id=%s status=%s isRunning=%s hasRunningTool=%s tools=%s",
    run.run_id,
    run.status,
    isRunning,
    hasRunningTool,
    run.tool_invocations
      .map((t) => t.call_id + ":" + t.status + ":" + t.tool_name)
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

      {run.status === "error" && run.error_message && (
        <div className="border-l-[3px] border-l-vermilion bg-vermilion/5 px-4 py-3">
          <p className="text-sm text-vermilion">{run.error_message}</p>
        </div>
      )}

      {isRunning && (
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-graphite">
            {hasRunningCrawl ? (
              <>
                <Globe className="h-4 w-4 text-cobalt animate-pulse" />
                <span>Fetching web page…</span>
              </>
            ) : hasRunningOtherTool ? (
              <>
                <Loader2
                  className="h-4 w-4 text-cobalt animate-spin"
                  aria-label="Calling tools"
                />
                <span>Calling tools…</span>
              </>
            ) : (
              <>
                <Spinner
                  size="sm"
                  className="text-cobalt"
                  aria-label="Working"
                />
                <span>Assistant is working</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
