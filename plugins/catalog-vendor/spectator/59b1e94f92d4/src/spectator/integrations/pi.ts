import { spawn } from "node:child_process"
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent"

/**
 * Pi coding-agent adapter for Spectator Mode.
 *
 * Copy this file to `~/.pi/agent/extensions/spectator.ts` or load it with
 * `pi --extension /path/to/spectator.ts`.
 */
export default function (pi: ExtensionAPI) {
  const forward = (event: object, ctx: ExtensionContext) => {
    const child = spawn("spectator-hook", ["--harness", "pi"], {
      stdio: ["pipe", "ignore", "ignore"],
      env: process.env,
    })
    child.stdin.end(
      JSON.stringify({
        ...event,
        sessionId: ctx.sessionManager.getSessionId(),
        cwd: ctx.cwd,
      }),
    )
    child.unref()
  }

  pi.on("session_start", async (event, ctx) => forward(event, ctx))
  pi.on("session_shutdown", async (event, ctx) => forward(event, ctx))
  pi.on("input", async (event, ctx) => forward(event, ctx))
  pi.on("message_end", async (event, ctx) => {
    if ((event.message as { role?: string }).role === "assistant") {
      forward(event, ctx)
    }
  })
  pi.on("tool_execution_start", async (event, ctx) => forward(event, ctx))
  pi.on("tool_execution_end", async (event, ctx) => forward(event, ctx))
}
