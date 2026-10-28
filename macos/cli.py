"""Command-Line Interface for Gemini Computer Use on macOS.
"""

import sys
import os
import argparse
import getpass
from agent import GeminiComputerUseAgent, FailsafeTriggered


def print_banner():
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                 GEMINI COMPUTER USE FOR MACOS                 ║
║      Autonomous OS Agent powered by Google Gemini Vision      ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gemini Computer Use: Autonomous AI desktop assistant for macOS."
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task prompt for Gemini (e.g. 'Open Safari and find news about space')."
    )
    parser.add_argument(
        "--model",
        default="gemini-3.8-flash",
        help="Gemini model name (default: gemini-3.8-flash). Options: gemini-3.8-flash, gemini-2.0-flash, etc."
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Google AI Studio Gemini API Key (defaults to GEMINI_API_KEY environment variable)."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Ask user confirmation before executing each mouse/keyboard action."
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=25,
        help="Maximum number of steps before terminating (default: 25)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between steps to allow UI settling (default: 0.5)."
    )
    parser.add_argument(
        "--no-failsafe",
        action="store_true",
        help="Disable corner emergency stop failsafe (NOT recommended)."
    )
    return parser.parse_args()


def get_api_key(provided_key=None):
    if provided_key:
        return provided_key
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key

    # Check local .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if k:
                        return k

    # Prompt user interactively
    print("\n[!] GEMINI_API_KEY is not set.")
    print("    Get your API key at: https://aistudio.google.com/app/apikey")
    key = getpass.getpass("    Enter your Gemini API Key: ").strip()
    if not key:
        print("[ERROR] API key cannot be empty.")
        sys.exit(1)

    # Offer to save into .env
    save = input("    Save this key to local .env for future runs? [Y/n]: ").strip().lower()
    if save in ('', 'y', 'yes'):
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"GEMINI_API_KEY={key}\n")
        print(f"    Saved API key to {env_path}")

    return key


def main():
    print_banner()
    args = parse_args()

    # Obtain API key
    api_key = get_api_key(args.api_key)

    # Obtain task
    task = args.task
    if not task:
        print("💡 Examples of tasks you can give:")
        print("   - 'Открой Калькулятор и посчитай 25 * 48'")
        print("   - 'Открой Safari, перейди на youtube.com и найди lofi hip hop'")
        print("   - 'Создай новую заметку в Notes с заголовком Идеи'")
        print("   - 'Открой терминал и выведи текущую дату'\n")
        try:
            task = input("Введите задачу для Gemini: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            sys.exit(0)

    if not task:
        print("[ERROR] Task description is required.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"🚀 Model:     {args.model}")
    print(f"🎯 Task:      {task}")
    print(f"🛡️  Failsafe:  {'OFF (Warning!)' if args.no_failsafe else 'ON (Move mouse to corner to abort)'}")
    print(f"🤝 Mode:      {'Step-by-step confirmation' if args.confirm else 'Autonomous'}")
    print(f"⏱️  Max Steps: {args.max_steps}")
    print("=" * 60 + "\n")

    agent = GeminiComputerUseAgent(
        api_key=api_key,
        model=args.model,
        failsafe=not args.no_failsafe
    )

    try:
        result = agent.run(
            task=task,
            max_steps=args.max_steps,
            confirm=args.confirm,
            delay_between_steps=args.delay
        )
        print("\n" + "=" * 60)
        status = result.get("status")
        if status == "success":
            print(f"🎉 TASK COMPLETED in {result.get('steps')} steps!")
            print(f"Summary: {result.get('summary')}")
        elif status == "failed":
            print(f"❌ TASK FAILED: {result.get('reason')}")
        elif status == "aborted":
            print(f"🛑 TASK ABORTED: {result.get('reason')}")
        elif status == "max_steps_reached":
            print(f"⚠️ REACHED STEP LIMIT ({result.get('steps')}).")
        else:
            print(f"Result: {result}")
        print("=" * 60)
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
