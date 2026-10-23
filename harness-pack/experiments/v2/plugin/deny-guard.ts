/**
 * deny-guard: refuses a short list of irreversible shell commands before they execute.
 *
 * This is the only component that acts inside the tool loop, so it holds the rules the
 * model cannot talk itself out of. The list is deliberately narrow: it targets commands
 * whose damage is unrecoverable, not ordinary workspace edits.
 *
 * Override for one session (the user must ask): HARNESS2_ALLOW_DANGER=1
 */
import type { Plugin } from "@opencode-ai/plugin"

type Rule = { name: string; re: RegExp }

const BLOCKED: Rule[] = [
  { name: "recursive delete of root or home", re: /\brm\s+(?:-[A-Za-z]*[rf][A-Za-z]*\s+)+(?:\/|~|\$HOME)(?:\s|$)/ },
  { name: "hard reset or forced checkout", re: /\bgit\s+(?:reset\s+--hard|checkout\s+--\s|clean\s+-[A-Za-z]*f)/ },
  { name: "force push", re: /\bgit\s+push\b[^\n]*(?:--force\b|--force-with-lease\b|\s-f\b)/ },
  { name: "world-writable root", re: /\bchmod\s+(?:-R\s+)?777\s+\/(?:\s|$)/ },
  { name: "remote script piped to a shell", re: /\b(?:curl|wget)\b[^|\n]*\|\s*(?:ba|z|k)?sh\b/ },
  { name: "database or table destruction", re: /\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b/i },
  { name: "raw write to a block device", re: /\b(?:mkfs(?:\.\w+)?|dd\s+[^\n]*of=\/dev\/)\b/ },
]

export const DenyGuard: Plugin = async () => ({
  "tool.execute.before": async (_input: unknown, output: unknown) => {
    if (process.env.HARNESS2_ALLOW_DANGER === "1") return
    if (!output || typeof output !== "object") return

    const args = (output as { args?: Record<string, unknown> }).args
    const command = typeof args?.command === "string" ? args.command : ""
    if (!command) return

    for (const rule of BLOCKED) {
      if (!rule.re.test(command)) continue
      throw new Error(
        "deny-guard blocked this command (" +
          rule.name +
          "). It is irreversible. Ask the user first; to override for one session set " +
          "HARNESS2_ALLOW_DANGER=1. Command: " +
          command.slice(0, 160),
      )
    }
  },
})
