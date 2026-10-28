#!/usr/bin/env python3
"""
╔═════════════════════════════════════════════════════════════════════════╗
║                      GEMINI COMPUTER USE ДЛЯ MACOS                      ║
║       Автономное управление компьютером через Google Gemini API         ║
╚═════════════════════════════════════════════════════════════════════════╝

ИНСТРУКЦИЯ ДЛЯ IDE (VS Code, Cursor, PyCharm и др.):
1) Задайте вашу задачу в переменной TASK ниже (или оставьте пустой для ввода через окно).
2) Укажите ваш API-ключ в переменной GEMINI_API_KEY ниже, либо в файле .env.
3) Нажмите кнопку Run (Play) в IDE!
"""

import os
import sys

# ==============================================================================
# 🎯 НАСТРОЙКИ ЗАДАЧИ
# Напишите задачу в кавычках (например: "Открой Safari и найди погоду в Москве")
# Если оставить строку пустой (""), скрипт покажет всплывающее окно для ввода.
TASK = ""

# 🔑 API КЛЮЧ GEMINI (получить бесплатно: https://aistudio.google.com/app/apikey)
# Вставьте ваш ключ сюда, либо укажите в файле .env / переменной GEMINI_API_KEY
GEMINI_API_KEY = ""

# 🤖 МОДЕЛЬ GEMINI (gemini-3.5-flash с автоматическим переключением при сбоях)
GEMINI_MODEL = "gemini-3.5-flash"

# 🤝 ПОДТВЕРЖДЕНИЕ ШАГОВ
# False = автономный режим (Gemini выполняет всё самостоятельно)
# True  = запрашивать подтверждение перед каждым кликом/нажатием
CONFIRM_EACH_STEP = False

# ⏱️ МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ШАГОВ (защита от бесконечных циклов)
MAX_STEPS = 25

# 🛡️ ЗАЩИТА: аварийная остановка при резком сдвиге мыши в любой угол экрана
FAILSAFE_ENABLED = True
# ==============================================================================

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import GeminiComputerUseAgent


def get_task():
    """Определяет задачу из переменной TASK, аргументов CLI или всплывающего окна."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Использование: python3 run.py [\"Ваша задача\"]")
        print("Либо просто впишите задачу в переменную TASK внутри run.py и нажмите Run.")
        sys.exit(0)

    # 1. Если передана через аргумент командной строки (python3 run.py "задача")
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return " ".join(sys.argv[1:])

    # 2. Если задана прямо вверху этого файла в переменной TASK
    if TASK.strip():
        return TASK.strip()

    # 3. Если запущено в интерактивном терминале
    if sys.stdin and sys.stdin.isatty():
        try:
            print("\n💡 Примеры задач:")
            print("   - 'Открой Калькулятор и посчитай 25 * 48'")
            print("   - 'Открой Safari и найди новости космоса'")
            print("   - 'Создай новую заметку в Заметках с текстом Привет мир'\n")
            val = input("Введите задачу для Gemini: ").strip()
            if val:
                return val
        except (EOFError, KeyboardInterrupt):
            pass

    # 4. Если консоль в IDE read-only — открываем всплывающее окно macOS
    task_from_popup = prompt_gui_dialog()
    if task_from_popup:
        return task_from_popup

    print("\n" + "=" * 65)
    print("⚠️  Внимание: задача не указана.")
    print("Чтобы запустить задачу, выберите один из вариантов:")
    print("1) Откройте этот файл (run.py) и впишите задачу в строку:")
    print('   TASK = "Открой Safari и найди погоду"\n')
    print("2) Либо в нижней панели IDE переключитесь на вкладку «Terminal» и запустите:")
    print('   python3 run.py "Открой Safari и найди погоду"')
    print("=" * 65 + "\n")
    return None


def prompt_gui_dialog():
    """Показывает нативное всплывающее окно macOS для ввода задачи."""
    try:
        import subprocess
        applescript = '''
        tell application "System Events"
            activate
            set dialogResult to display dialog "Какую задачу выполнить Gemini на вашем компьютере?" default answer "Открой Safari и найди курс валют" with title "Gemini Computer Use" buttons {"Отмена", "Запустить"} default button "Запустить"
            return text returned of dialogResult
        end tell
        '''
        res = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    try:
        os.environ["TK_SILENCE_DEPRECATION"] = "1"
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        res = simpledialog.askstring(
            "Gemini Computer Use",
            "Какую задачу выполнить Gemini на вашем компьютере?",
            initialvalue="Открой Safari и найди новости",
            parent=root
        )
        root.destroy()
        if res and res.strip():
            return res.strip()
    except Exception:
        pass

    return None


def get_api_key():
    """Получает API-ключ из переменной, .env, окружения или диалога."""
    if GEMINI_API_KEY.strip():
        return GEMINI_API_KEY.strip()

    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if k and not k.startswith("AIzaSyВаш"):
                            return k
        except Exception:
            pass

    if sys.stdin and sys.stdin.isatty():
        try:
            print("\n[!] GEMINI_API_KEY не найден.")
            print("    Получите бесплатный ключ в Google AI Studio: https://aistudio.google.com/app/apikey")
            k = input("    Введите ваш Gemini API Key: ").strip()
            if k:
                return k
        except (EOFError, KeyboardInterrupt):
            pass

    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        k = simpledialog.askstring(
            "Gemini API Key",
            "Введите ваш Google Gemini API Key:\n(Получить: https://aistudio.google.com/app/apikey)",
            parent=root
        )
        root.destroy()
        if k and k.strip():
            return k.strip()
    except Exception:
        pass

    print("[ERROR] Не указан GEMINI_API_KEY. Впишите его в run.py или создайте .env файл.")
    sys.exit(1)


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                 GEMINI COMPUTER USE FOR MACOS                 ║
║      Autonomous OS Agent powered by Google Gemini Vision      ║
╚═══════════════════════════════════════════════════════════════╝
""")

    task = get_task()
    if not task:
        sys.exit(0)

    api_key = get_api_key()

    print("=" * 65)
    print(f"🚀 Модель:      {GEMINI_MODEL}")
    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"🔑 API Key:     {masked_key}")
    print(f"🎯 Задача:      {task}")
    print(f"🛡️  Failsafe:    {'ВКЛ (переведите курсор в угол экрана для отмены)' if FAILSAFE_ENABLED else 'ВЫКЛ'}")
    print(f"🤝 Режим:       {'Пошаговое подтверждение' if CONFIRM_EACH_STEP else 'Автономный'}")
    print("=" * 65 + "\n")

    agent = GeminiComputerUseAgent(
        api_key=api_key,
        model=GEMINI_MODEL,
        failsafe=FAILSAFE_ENABLED
    )

    try:
        result = agent.run(
            task=task,
            max_steps=MAX_STEPS,
            confirm=CONFIRM_EACH_STEP,
            delay_between_steps=0.5
        )
        print("\n" + "=" * 65)
        status = result.get("status")
        if status == "success":
            print(f"🎉 ЗАДАЧА ВЫПОЛНЕНА за {result.get('steps')} шагов!")
            print(f"Итог: {result.get('summary')}")
        elif status == "failed":
            print(f"❌ НЕ УДАЛОСЬ ВЫПОЛНИТЬ: {result.get('reason')}")
        elif status == "aborted":
            print(f"🛑 ОСТАНОВЛЕНО: {result.get('reason')}")
        elif status == "max_steps_reached":
            print(f"⚠️ ДОСТИГНУТ ЛИМИТ ШАГОВ ({result.get('steps')}).")
        else:
            print(f"Результат: {result}")
        print("=" * 65)
    except KeyboardInterrupt:
        print("\n[STOP] Остановлено пользователем (Ctrl+C).")
    except Exception as e:
        print(f"\n[ОШИБКА] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
