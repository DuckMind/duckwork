import { spawn } from "node:child_process"

/**
 * OpenCode adapter for Spectator Mode.
 *
 * Copy this file to `.opencode/plugins/spectator.ts`. Raw hook payloads stay
 * on the local machine; spectator-hook projects them to privacy-safe events.
 */
export const SpectatorPlugin = async ({ directory }) => {
  const watchedEvents = new Set([
    "session.created",
    "session.idle",
    "session.deleted",
  ])
  const forward = (payload) =>
    new Promise((resolve) => {
      const child = spawn("spectator-hook", ["--harness", "opencode"], {
        stdio: ["pipe", "ignore", "ignore"],
        env: process.env,
      })
      child.once("error", () => resolve(undefined))
      child.once("close", () => resolve(undefined))
      child.stdin.once("error", () => resolve(undefined))
      child.stdin.end(JSON.stringify({ ...payload, directory }))
    })

  return {
    event: async ({ event }) => {
      if (!watchedEvents.has(event.type)) return
      const properties = event.properties || {}
      const info = properties.info || {}
      const sessionID =
        properties.sessionID ||
        info.sessionID ||
        (event.type === "session.created" ? info.id : undefined)
      if (sessionID) {
        await forward({
          ...event,
          sessionID,
          id: `${event.type}:${sessionID}`,
        })
      }
    },
    "chat.message": async (input, output) => {
      const contentSize = Buffer.byteLength(
        JSON.stringify(output.parts || []),
        "utf8",
      )
      await forward({
        type: "input",
        sessionID: input.sessionID,
        messageID: input.messageID,
        content_size: contentSize,
      })
    },
    "tool.execute.before": async (input, output) => {
      await forward({
        type: "tool.execute.before",
        sessionID: input.sessionID,
        properties: {
          callID: input.callID,
          tool: input.tool,
          input: output.args,
        },
      })
    },
    "tool.execute.after": async (input, output) => {
      await forward({
        type: "tool.execute.after",
        sessionID: input.sessionID,
        properties: {
          callID: input.callID,
          tool: input.tool,
          output,
        },
      })
    },
  }
}
