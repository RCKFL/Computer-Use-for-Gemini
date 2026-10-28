"""Gemini API Client for Computer Use.

Communicates with Gemini 3.8 Flash via REST API
using standard library urllib (zero external pip packages required).
Supports Multimodal Vision, Function Calling, and History pruning.
"""

import os
import json
import urllib.request
import urllib.error
import ssl

DEFAULT_MODEL = "gemini-3.5-flash"
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
BUILTIN_API_KEY = ""  # Replace with your actual API key or set GEMINI_API_KEY in .env
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3-flash-preview", "gemini-flash-latest"]

SYSTEM_INSTRUCTION = """You are Gemini Computer Use Agent, an autonomous GUI agent operating a macOS computer.
Your job is to accomplish the user's task by looking at the screen, reasoning about what to do next, and controlling the mouse and keyboard using available tools.

# ENVIRONMENT & COORDINATES
- Screen coordinates are normalized between 0 and 1000:
  - (0, 0) is the top-left corner.
  - (1000, 1000) is the bottom-right corner.
  - (500, 500) is the exact center of the screen.
- macOS UI layout:
  - Menu Bar is at the top (y: 0 to 35).
  - Dock is usually at the bottom (y: 920 to 1000) with app icons.
  - Window controls (close [red], minimize [yellow], fullscreen [green]) are at top-left of each window.
  - Spotlight Search can be opened with the hotkey ["command", "space"].

# STRATEGY & GUIDELINES
1. ALWAYS think and explain your plan briefly before calling a tool.
2. If an app needs to be opened, you can either:
   - Click its icon in the Dock.
   - Or press hotkey ["command", "space"], type the app name, and press "return".
3. To type text into a field or address bar, first CLICK on the field to ensure it is focused, then call `type_text`.
4. Allow time for UI changes or web pages to load using `wait` when appropriate.
5. If a popup or cookie banner appears, dismiss or accept it.
6. Check the screen after each action to verify if your click succeeded.
7. When the user's objective is fully accomplished, call `task_done` with a brief summary.
8. If you get completely stuck or encounter an unrecoverable error, call `task_failed`.
"""

TOOLS_SPEC = [
    {
        "function_declarations": [
            {
                "name": "mouse_click",
                "description": "Click on a UI element at normalized coordinates (0-1000).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "x": {
                            "type": "INTEGER",
                            "description": "Horizontal position from 0 (left) to 1000 (right)."
                        },
                        "y": {
                            "type": "INTEGER",
                            "description": "Vertical position from 0 (top) to 1000 (bottom)."
                        },
                        "button": {
                            "type": "STRING",
                            "enum": ["left", "right"],
                            "description": "Mouse button: 'left' (default) or 'right'."
                        },
                        "clicks": {
                            "type": "INTEGER",
                            "description": "Number of clicks: 1 for single click (default), 2 for double-click."
                        }
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "mouse_move",
                "description": "Move the mouse cursor to normalized coordinates (0-1000) without clicking.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "x": {"type": "INTEGER", "description": "Horizontal position 0-1000."},
                        "y": {"type": "INTEGER", "description": "Vertical position 0-1000."}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "mouse_drag",
                "description": "Drag from start coordinates to end coordinates.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "start_x": {"type": "INTEGER", "description": "Start X (0-1000)."},
                        "start_y": {"type": "INTEGER", "description": "Start Y (0-1000)."},
                        "end_x": {"type": "INTEGER", "description": "End X (0-1000)."},
                        "end_y": {"type": "INTEGER", "description": "End Y (0-1000)."}
                    },
                    "required": ["start_x", "start_y", "end_x", "end_y"]
                }
            },
            {
                "name": "mouse_scroll",
                "description": "Scroll the screen up or down.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "direction": {
                            "type": "STRING",
                            "enum": ["down", "up"],
                            "description": "Direction to scroll: 'down' (default) or 'up'."
                        },
                        "amount": {
                            "type": "INTEGER",
                            "description": "Amount to scroll (1 to 15, default 5)."
                        }
                    }
                }
            },
            {
                "name": "type_text",
                "description": "Type a string of text into the currently focused input field.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "text": {
                            "type": "STRING",
                            "description": "The exact text to type (supports English, Russian, emojis, symbols)."
                        },
                        "press_enter": {
                            "type": "BOOLEAN",
                            "description": "Whether to press Enter / Return after typing (default false)."
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "press_key",
                "description": "Press a single special key.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "key": {
                            "type": "STRING",
                            "description": "Key name: 'return'/'enter', 'escape', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'pageup', 'pagedown'."
                        }
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "hotkey",
                "description": "Press a keyboard shortcut combination simultaneously.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "keys": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of keys, e.g. ['command', 'space'] for Spotlight, ['command', 'c'], ['command', 'v'], ['command', 't'], ['command', 'w']."
                        }
                    },
                    "required": ["keys"]
                }
            },
            {
                "name": "wait",
                "description": "Wait a specified number of seconds for page or app animation to complete.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "seconds": {
                            "type": "NUMBER",
                            "description": "Seconds to pause (e.g. 1.0, 2.0, 3.0)."
                        }
                    },
                    "required": ["seconds"]
                }
            },
            {
                "name": "task_done",
                "description": "Signal that the user's requested task has been completely and successfully achieved.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {
                            "type": "STRING",
                            "description": "Detailed description of what was accomplished."
                        }
                    },
                    "required": ["summary"]
                }
            },
            {
                "name": "task_failed",
                "description": "Signal that the task cannot be completed due to an insurmountable blocker.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "reason": {
                            "type": "STRING",
                            "description": "Explanation of why the task failed."
                        }
                    },
                    "required": ["reason"]
                }
            }
        ]
    }
]


class GeminiClient:
    """Handles communication with Gemini API."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        loaded_env = self._load_env_file()
        if not self.api_key:
            self.api_key = loaded_env.get("GEMINI_API_KEY") or BUILTIN_API_KEY

        self.model = model or os.environ.get("GEMINI_MODEL") or loaded_env.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.history = []
        self.max_kept_images = 2  # Keep last 2 screenshots in full base64 to conserve memory & bandwidth

    def _load_env_file(self):
        env_vars = {}
        candidates = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.path.dirname(__file__), ".env"),
            os.path.expanduser("~/.gemini_api_key"),
            os.path.expanduser("~/.config/gemini/api_key")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("GEMINI_API_KEY="):
                                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if key:
                                    env_vars["GEMINI_API_KEY"] = key
                            elif line.startswith("GEMINI_MODEL="):
                                m = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if m:
                                    env_vars["GEMINI_MODEL"] = m
                            elif not line.startswith("#") and len(line) > 20 and "=" not in line:
                                env_vars["GEMINI_API_KEY"] = line
                except Exception:
                    pass
        return env_vars

    def start_conversation(self, task_description, initial_screenshot_b64, screen_w, screen_h):
        """Initializes conversation with user task prompt and initial screen."""
        self.history = []

        user_content = {
            "role": "user",
            "parts": [
                {
                    "text": (
                        f"USER OBJECTIVE: {task_description}\n\n"
                        f"Screen resolution: {screen_w}x{screen_h} (use normalized 0-1000 coordinates).\n"
                        f"Here is the current screen of my computer. Analyze it carefully and call the appropriate tool."
                    )
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": initial_screenshot_b64
                    }
                }
            ]
        }
        self.history.append(user_content)

    def prune_old_images(self):
        """Replaces older screenshots with a text placeholder to keep requests fast and lean."""
        image_turns = []
        for i, turn in enumerate(self.history):
            if turn.get("role") == "user":
                for j, part in enumerate(turn.get("parts", [])):
                    if "inline_data" in part:
                        image_turns.append((i, j))

        if len(image_turns) > self.max_kept_images:
            to_prune = image_turns[:-self.max_kept_images]
            for turn_idx, part_idx in to_prune:
                self.history[turn_idx]["parts"][part_idx] = {
                    "text": "[Previous screenshot omitted from context]"
                }

    def send_action_result(self, tool_name, result_data, new_screenshot_b64=None):
        """Appends tool response and optionally new screenshot to conversation history."""
        # 1. Tool result message
        tool_content = {
            "role": "tool",
            "parts": [
                {
                    "functionResponse": {
                        "name": tool_name,
                        "response": {
                            "output": result_data
                        }
                    }
                }
            ]
        }
        self.history.append(tool_content)

        # 2. If new screenshot provided, append as follow-up user turn
        if new_screenshot_b64:
            user_followup = {
                "role": "user",
                "parts": [
                    {
                        "text": f"Action '{tool_name}' executed. Current screen after action:"
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": new_screenshot_b64
                        }
                    }
                ]
            }
            self.history.append(user_followup)

        # Prune old images to conserve payload
        self.prune_old_images()

    def step(self):
        """Calls Gemini API and returns (thought_text, function_call_dict).

        Includes automatic retry and fallback to alternative models if 503/429 occurs.
        """
        import time

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set the environment variable "
                "or create a .env file with GEMINI_API_KEY=AIzaSy..."
            )

        payload = {
            "contents": self.history,
            "system_instruction": {
                "parts": [
                    {"text": SYSTEM_INSTRUCTION}
                ]
            },
            "tools": TOOLS_SPEC,
            "tool_config": {
                "function_calling_config": {
                    "mode": "AUTO"
                }
            },
            "generation_config": {
                "temperature": 0.2,
                "max_output_tokens": 1024
            }
        }
        data_bytes = json.dumps(payload).encode('utf-8')

        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        resp_data = None
        last_error = None

        for current_model in models_to_try:
            url = f"{API_BASE_URL}/{current_model}:generateContent?key={self.api_key}"
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"}
            )
            ctx = ssl.create_default_context()

            # Try up to 2 times per model
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, context=ctx, timeout=40) as resp:
                        resp_data = json.loads(resp.read().decode('utf-8'))
                        self.model = current_model  # update active model
                        break
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode('utf-8')
                    last_error = f"HTTP {e.code} on {current_model}: {err_body}"
                    if e.code in (503, 429):
                        print(f"[WARN] Модель {current_model} временно перегружена ({e.code}). Попытка переключения...")
                        time.sleep(2)
                        continue
                    else:
                        break
                except urllib.error.URLError as e:
                    last_error = f"Network Error on {current_model}: {e.reason}"
                    time.sleep(1)
                    continue

            if resp_data:
                break

        if not resp_data:
            raise RuntimeError(f"Все доступные модели Gemini недоступны. Последняя ошибка: {last_error}")

        # Parse response
        candidates = resp_data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"No response candidates returned: {resp_data}")

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        # Store model's response turn into history
        self.history.append({
            "role": "model",
            "parts": parts
        })

        thought_parts = []
        function_call = None

        for part in parts:
            if "text" in part:
                thought_parts.append(part["text"])
            if "functionCall" in part:
                function_call = part["functionCall"]

        thought = "\n".join(thought_parts).strip()
        return thought, function_call
