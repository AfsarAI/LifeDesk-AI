import { Brain, CheckCircle2, Circle, PanelRightClose } from "lucide-react";
import type { Memory, Task } from "../types/api";

interface ContextPanelProps {
  tasks: Task[];
  memories: Memory[];
  onClose: () => void;
  onOpenTasks: () => void;
  onOpenMemory: () => void;
}

export function ContextPanel({
  tasks,
  memories,
  onClose,
  onOpenTasks,
  onOpenMemory,
}: ContextPanelProps) {
  const pendingTasks = tasks.filter((t) => t.status === "pending").slice(0, 6);
  const recentMemories = memories.slice(0, 5);

  return (
    <aside className="hidden h-full w-80 flex-col border-l border-slate-800 bg-slate-900/60 xl:flex">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Workspace Context
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          title="Hide context panel"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-4">
        <section>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Pending Tasks</span>
            <button
              type="button"
              onClick={onOpenTasks}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              View all
            </button>
          </div>
          {pendingTasks.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-800 p-3 text-xs text-slate-500">
              No pending tasks.
            </p>
          ) : (
            <ul className="space-y-2">
              {pendingTasks.map((task) => (
                <li
                  key={task.id}
                  className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-2.5"
                >
                  {task.status === "completed" ? (
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                  ) : (
                    <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-200">{task.title}</p>
                    <p className="text-[11px] text-slate-500">
                      #{task.id}
                      {task.due_date ? ` • Due ${task.due_date}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Brain className="h-3.5 w-3.5 text-indigo-400" />
              Saved Memories
            </span>
            <button
              type="button"
              onClick={onOpenMemory}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              Manage
            </button>
          </div>
          {recentMemories.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-800 p-3 text-xs text-slate-500">
              No memories stored yet.
            </p>
          ) : (
            <ul className="space-y-2">
              {recentMemories.map((mem) => (
                <li
                  key={mem.id}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-2.5 text-xs"
                >
                  <p className="font-mono text-[11px] text-indigo-300">{mem.key}</p>
                  <p className="mt-0.5 text-slate-300">{mem.value}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
  );
}
