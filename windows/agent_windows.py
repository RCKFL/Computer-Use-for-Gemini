"""Autonomous agent execution engine for Windows.
"""

import time
import sys
from controller_windows import WindowsController, FailsafeTriggered
from screen_windows import WindowsScreenManager
from gemini_client_windows import GeminiWindowsClient


class GeminiWindowsAgent:
    """Autonomous agent that uses Gemini Vision to control Windows."""

    def __init__(self, api_key=None, model="gemini-3.5-flash", failsafe=True):
        self.controller = WindowsController(failsafe=failsafe)
        self.screen = WindowsScreenManager()
        self.client = GeminiWindowsClient(api_key=api_key, model=model)
        self.current_step = 0

    def execute_tool(self, name, args):
        """Translates normalized tool calls into native Windows actions."""
        self.controller.check_failsafe()

        if name == "mouse_click":
            norm_x = args.get("x")
            norm_y = args.get("y")
            button = args.get("button", "left")
            clicks = int(args.get("clicks", 1))

            px_x, px_y = self.screen.normalized_to_pixel(norm_x, norm_y)
            self.controller.click(px_x, px_y, button=button, clicks=clicks)
            return f"Clicked {button} (x{clicks}) at ({px_x}, {px_y}) [norm: {norm_x}, {norm_y}]"

        elif name == "mouse_move":
            norm_x = args.get("x")
            norm_y = args.get("y")
            px_x, px_y = self.screen.normalized_to_pixel(norm_x, norm_y)
            self.controller.move_to(px_x, px_y)
            return f"Moved mouse to ({px_x}, {px_y})"

        elif name == "mouse_drag":
            s_x, s_y = self.screen.normalized_to_pixel(args.get("start_x"), args.get("start_y"))
            e_x, e_y = self.screen.normalized_to_pixel(args.get("end_x"), args.get("end_y"))
            self.controller.drag(s_x, s_y, e_x, e_y)
            return f"Dragged mouse from ({s_x}, {s_y}) to ({e_x}, {e_y})"

        elif name == "mouse_scroll":
            direction = args.get("direction", "down")
            amount = int(args.get("amount", 5))
            self.controller.scroll(clicks=amount, direction=direction)
            return f"Scrolled {direction} by {amount} units"

        elif name == "type_text":
            text = args.get("text", "")
            press_enter = bool(args.get("press_enter", False))
            self.controller.type_text(text, press_enter_after=press_enter)
            return f"Typed text: '{text}' (enter={press_enter})"

        elif name == "press_key":
            key = args.get("key", "")
            self.controller.press_key(key)
            return f"Pressed key: '{key}'"

        elif name == "hotkey":
            keys = args.get("keys", [])
            self.controller.hotkey(keys)
            return f"Pressed hotkey: {' + '.join(keys)}"

        elif name == "wait":
            secs = float(args.get("seconds", 1.0))
            secs = max(0.1, min(10.0, secs))
            time.sleep(secs)
            return f"Waited {secs:.1f} seconds"

        elif name == "task_done":
            summary = args.get("summary", "Task completed.")
            return summary

        elif name == "task_failed":
            reason = args.get("reason", "Task failed.")
            return reason

        else:
            raise ValueError(f"Unknown tool called by model: {name}")

    def run(self, task, max_steps=25, confirm=False, delay_between_steps=0.5, log_callback=None):
        """Runs the autonomous loop on Windows."""
        def log(msg, category="info"):
            if log_callback:
                log_callback(msg, category)
            else:
                prefix = {
                    "info": "[INFO]",
                    "thought": "[THOUGHT]",
                    "action": "[ACTION]",
                    "success": "[SUCCESS]",
                    "error": "[ERROR]",
                    "warn": "[WARN]"
                }.get(category, "[LOG]")
                print(f"{prefix} {msg}")

        log(f"Starting Windows task: '{task}'", "info")
        screen_w, screen_h = self.screen.width, self.screen.height
        log(f"Screen resolution: {screen_w}x{screen_h}", "info")

        log("Capturing initial screen...", "info")
        cap = self.screen.capture()
        self.client.start_conversation(
            task_description=task,
            initial_screenshot_b64=cap["base64"],
            screen_w=screen_w,
            screen_h=screen_h
        )

        last_tool_name = None
        last_tool_result = None

        for step_idx in range(1, max_steps + 1):
            self.current_step = step_idx
            log(f"\n--- STEP {step_idx}/{max_steps} ---", "info")

            try:
                self.controller.check_failsafe()
            except FailsafeTriggered as e:
                log(str(e), "error")
                return {"status": "aborted", "reason": "Failsafe triggered by user", "steps": step_idx}

            if step_idx > 1:
                log("Capturing updated screen...", "info")
                cap = self.screen.capture()
                self.client.send_action_result(
                    tool_name=last_tool_name,
                    result_data=last_tool_result,
                    new_screenshot_b64=cap["base64"]
                )

            log(f"Sending screen to Gemini ({self.client.model})...", "info")
            try:
                thought, function_call = self.client.step()
            except Exception as e:
                log(f"Gemini API request failed: {e}", "error")
                return {"status": "error", "error": str(e), "steps": step_idx}

            if thought:
                log(thought, "thought")

            if not function_call:
                log("No action provided. Waiting 1 second...", "warn")
                last_tool_name = "wait"
                last_tool_result = "Waited 1 second."
                time.sleep(1.0)
                continue

            fn_name = function_call.get("name")
            fn_args = function_call.get("args", {})
            log(f"Planned Action: {fn_name}({fn_args})", "action")

            if fn_name == "task_done":
                summary = fn_args.get("summary", "Task successfully finished.")
                log(f"Task completed: {summary}", "success")
                return {"status": "success", "summary": summary, "steps": step_idx}

            if fn_name == "task_failed":
                reason = fn_args.get("reason", "Task failed.")
                log(f"Task aborted: {reason}", "error")
                return {"status": "failed", "reason": reason, "steps": step_idx}

            if confirm:
                try:
                    user_choice = input(f"Execute {fn_name}({fn_args})? [Y/n/q]: ").strip().lower()
                    if user_choice == 'q':
                        log("Aborted by user.", "warn")
                        return {"status": "aborted", "reason": "User cancelled", "steps": step_idx}
                    elif user_choice == 'n':
                        log("Step skipped by user.", "warn")
                        last_tool_name = fn_name
                        last_tool_result = "Skipped by user."
                        continue
                except (EOFError, KeyboardInterrupt):
                    pass

            try:
                result_str = self.execute_tool(fn_name, fn_args)
                log(f"Result: {result_str}", "info")
                last_tool_name = fn_name
                last_tool_result = result_str
            except FailsafeTriggered as e:
                log(str(e), "error")
                return {"status": "aborted", "reason": "Failsafe triggered", "steps": step_idx}
            except Exception as e:
                log(f"Tool execution failed: {e}", "error")
                last_tool_name = fn_name
                last_tool_result = f"Error executing tool: {e}"

            time.sleep(delay_between_steps)

        log(f"Reached step limit ({max_steps}).", "warn")
        return {"status": "max_steps_reached", "steps": max_steps}
