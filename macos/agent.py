"""Agent execution engine coordinating Vision, Gemini Reasoning, and Action Execution.
"""

import time
import sys
from controller import MacOSController, FailsafeTriggered
from screen import ScreenManager
from gemini_client import GeminiClient


class AgentExecutionError(Exception):
    pass


class GeminiComputerUseAgent:
    """Autonomous agent that uses Gemini Vision to control macOS."""

    def __init__(self, api_key=None, model="gemini-3.8-flash", failsafe=True):
        self.controller = MacOSController(failsafe=failsafe)
        self.screen = ScreenManager()
        self.client = GeminiClient(api_key=api_key, model=model)
        self.current_step = 0

    def execute_tool(self, name, args):
        """Translates normalized tool calls into native macOS controller actions."""
        self.controller.check_failsafe()

        if name == "mouse_click":
            norm_x = args.get("x")
            norm_y = args.get("y")
            button = args.get("button", "left")
            clicks = int(args.get("clicks", 1))

            log_x, log_y = self.screen.normalized_to_logical(norm_x, norm_y)
            self.controller.click(log_x, log_y, button=button, clicks=clicks)
            return f"Clicked {button} (x{clicks}) at screen ({int(log_x)}, {int(log_y)}) [normalized: {norm_x}, {norm_y}]"

        elif name == "mouse_move":
            norm_x = args.get("x")
            norm_y = args.get("y")
            log_x, log_y = self.screen.normalized_to_logical(norm_x, norm_y)
            self.controller.move_to(log_x, log_y)
            return f"Moved mouse to ({int(log_x)}, {int(log_y)})"

        elif name == "mouse_drag":
            s_x, s_y = self.screen.normalized_to_logical(args.get("start_x"), args.get("start_y"))
            e_x, e_y = self.screen.normalized_to_logical(args.get("end_x"), args.get("end_y"))
            self.controller.drag(s_x, s_y, e_x, e_y)
            return f"Dragged mouse from ({int(s_x)}, {int(s_y)}) to ({int(e_x)}, {int(e_y)})"

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
            # Cap wait to safe max
            secs = max(0.1, min(10.0, secs))
            time.sleep(secs)
            return f"Waited {secs:.1f} seconds"

        elif name == "task_done":
            summary = args.get("summary", "Task finished successfully.")
            return summary

        elif name == "task_failed":
            reason = args.get("reason", "Task failed.")
            return reason

        else:
            raise ValueError(f"Unknown tool called by model: {name}")

    def run(self, task, max_steps=25, confirm=False, delay_between_steps=0.5, log_callback=None):
        """Runs the agent loop until completion, failure, or max steps reached.

        Args:
            task (str): Natural language instruction.
            max_steps (int): Maximum iterations to prevent infinite loops.
            confirm (bool): If True, asks user confirmation before executing each step.
            delay_between_steps (float): Cooldown between actions.
            log_callback (callable): Optional function for UI logging.
        """
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

        log(f"Starting task: '{task}'", "info")
        screen_w, screen_h = self.screen.logical_w, self.screen.logical_h
        log(f"Screen metrics: {screen_w}x{screen_h} (Retina scale: {self.screen.scale_factor}x)", "info")

        # Step 1: Initial screen capture
        log("Capturing initial screen state...", "info")
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

            # Check corner failsafe
            try:
                self.controller.check_failsafe()
            except FailsafeTriggered as e:
                log(str(e), "error")
                return {"status": "aborted", "reason": "Failsafe triggered by user", "steps": step_idx}

            # If not first step, send tool response + new screen to model
            if step_idx > 1:
                log("Capturing updated screen...", "info")
                cap = self.screen.capture()
                self.client.send_action_result(
                    tool_name=last_tool_name,
                    result_data=last_tool_result,
                    new_screenshot_b64=cap["base64"]
                )

            # Query Gemini
            log(f"Sending screen to Gemini ({self.client.model})...", "info")
            try:
                thought, function_call = self.client.step()
            except Exception as e:
                log(f"Gemini API request failed: {e}", "error")
                return {"status": "error", "error": str(e), "steps": step_idx}

            if thought:
                log(thought, "thought")

            if not function_call:
                log("Gemini did not return an action. Requesting next step...", "warn")
                last_tool_name = "wait"
                last_tool_result = "No action provided, waited 1 second."
                time.sleep(1.0)
                continue

            fn_name = function_call.get("name")
            fn_args = function_call.get("args", {})
            log(f"Planned Action: {fn_name}({fn_args})", "action")

            # Check termination tools
            if fn_name == "task_done":
                summary = fn_args.get("summary", "Task successfully finished.")
                log(f"Task completed: {summary}", "success")
                return {"status": "success", "summary": summary, "steps": step_idx}

            if fn_name == "task_failed":
                reason = fn_args.get("reason", "Task failed.")
                log(f"Task aborted: {reason}", "error")
                return {"status": "failed", "reason": reason, "steps": step_idx}

            # Confirmation mode check
            if confirm:
                user_choice = input(f"Execute {fn_name}({fn_args})? [Y/n/q]: ").strip().lower()
                if user_choice == 'q':
                    log("Aborted by user.", "warn")
                    return {"status": "aborted", "reason": "User cancelled", "steps": step_idx}
                elif user_choice == 'n':
                    log("Step skipped by user.", "warn")
                    last_tool_name = fn_name
                    last_tool_result = "Skipped by user."
                    continue

            # Execute tool
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

        log(f"Reached maximum steps limit ({max_steps}) without finishing.", "warn")
        return {"status": "max_steps_reached", "steps": max_steps}
