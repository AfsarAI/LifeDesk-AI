import { CheckCircle2, Wrench, XCircle } from "lucide-react";
import type { ToolExecutionRecord } from "../types/api";

interface ToolCallListProps {
  toolCalls: ToolExecutionRecord[];
}

export function ToolCallList({ toolCalls }: ToolCallListProps) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="mb-2.5 space-y-1.5">
      {toolCalls.map((call, idx) => (
        <div
          key={`${call.call_id || call.tool_name}-${idx}`}
          className={`rounded-xl border px-3 py-2 text-xs ${
            call.success
              ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-200"
              : "border-rose-500/30 bg-rose-950/30 text-rose-200"
          }`}
        >
          <div className="flex items-center gap-2 font-medium">
            <Wrench className="h-3.5 w-3.5 shrink-0 opacity-80" />
            <span className="font-mono">{call.tool_name}</span>
            <span className="ml-auto flex items-center gap-1 text-[11px]">
              {call.success ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  Executed
                </>
              ) : (
                <>
                  <XCircle className="h-3.5 w-3.5 text-rose-400" />
                  Failed
                </>
              )}
            </span>
          </div>
          {Object.keys(call.arguments).length > 0 && (
            <p className="mt-1 truncate font-mono text-[11px] opacity-80">
              args: {JSON.stringify(call.arguments)}
            </p>
          )}
          {!call.success && typeof call.result?.error === "string" && (
            <p className="mt-1 text-[11px] text-rose-300">{call.result.error}</p>
          )}
        </div>
      ))}
    </div>
  );
}
