#!/usr/bin/env python3
"""
JARVIS AI Guide - Personal AI Orchestrator
============================================
3 brains, 17 agents, voice control, computer use.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.config import config
from jarvis.orchestrator import JarvisOrchestrator
from jarvis.voice.listener import VoiceListener
from jarvis.utils.logger import log
from jarvis.brains.providers import OllamaProvider

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

   🆓 Gratis via Ollama • 17 Agentes • Comando de Voz
   ════════════════════════════════════════════
"""


def print_help():
    print(f"""
Commands:
  /exit              Exit JARVIS
  /agents            List all agents
  /conclave          Toggle Conclave debate (currently {config.conclave.enabled})
  /provider          Show/change AI provider (currently: {config.brain.provider})
  /memory            Show recent memory
  /profile           Show user profile
  /voice             Toggle voice mode
  /clear             Clear screen
  /help              Show this help

Providers: ollama (free/local), gemini (free tier), groq (free tier), claude (pago)
To switch: /provider ollama  or  /provider gemini  etc.

You can also type or speak any task naturally.
""")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(BANNER)

    print("Initializing JARVIS...")
    jarvis = JarvisOrchestrator()

    listener = None
    voice_mode = config.voice.enabled
    if voice_mode:
        listener = VoiceListener(
            wake_word=config.voice.wake_word,
            language=config.voice.language,
        )
        listener.start()
        print("  🎤 Voice mode active - say 'Jarvis' to wake me")
    else:
        print("  ⌨️  Text mode")

    print(f"  🧠 {len(jarvis.agents)} agents loaded")
    print(f"  🆓 Provider: {config.brain.provider.upper()} ({config.brain.ollama_model if config.brain.provider == 'ollama' else config.brain.gemini_model if config.brain.provider == 'gemini' else config.brain.groq_model if config.brain.provider == 'groq' else config.brain.claude_model})")
    print(f"  📁 Projects dir: {config.data_dir}")
    print(f"  🧠 Conclave: {'ON' if config.conclave.enabled else 'OFF'}")
    print("\n" + "=" * 55)
    print("Type /help for commands or just start asking!")
    print("=" * 55 + "\n")

    try:
        while True:
            user_input = None

            if listener:
                cmd = listener.get_command(timeout=0.3)
                if cmd:
                    typ, val = cmd
                    if typ == "wake":
                        jarvis.speak("Yes sir, I'm listening")
                        print("\n🎤 Listening...")
                        speech = listener.listen_once(timeout=8)
                        if speech:
                            print(f"  🎤 You: {speech}")
                            user_input = speech
                        else:
                            print("  (nothing heard)")
                            continue
                    else:
                        print(f"  🎤 You: {val}")
                        user_input = val

            if user_input is None:
                try:
                    user_input = input("  ⌨️  You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\nGoodbye!")
                    break

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/exit", "/quit", "/sair"):
                    print("Goodbye!")
                    break
                elif cmd == "/agents":
                    print("\n  🤖 Agents:")
                    for i, name in enumerate(jarvis.get_agent_list(), 1):
                        print(f"    {i:2d}. {name}")
                    continue
                elif cmd == "/conclave":
                    config.conclave.enabled = not config.conclave.enabled
                    print(f"  Conclave: {'ON' if config.conclave.enabled else 'OFF'}")
                    continue
                elif cmd == "/memory":
                    print(f"\n  📝 Recent Memory:\n{jarvis.memory.get_conversation_context(15)}")
                    continue
                elif cmd == "/profile":
                    print(f"\n  👤 Profile:\n{jarvis.memory.get_profile_summary()}")
                    continue
                elif cmd == "/voice":
                    voice_mode = not voice_mode
                    if voice_mode and not listener:
                        listener = VoiceListener()
                        listener.start()
                    print(f"  Voice mode: {'ON' if voice_mode else 'OFF'}")
                    continue
                elif cmd.startswith("/provider"):
                    parts = user_input.split()
                    if len(parts) >= 2:
                        new_provider = parts[1].lower()
                        valid = ("ollama", "gemini", "groq", "claude")
                        if new_provider in valid:
                            config.brain.provider = new_provider
                            jarvis.brain = None  # will be recreated
                            from jarvis.brains.claude_brain import ClaudeBrain
                            jarvis.brain = ClaudeBrain()
                            print(f"  ✅ Provider changed to: {new_provider.upper()}")
                            if new_provider == "ollama":
                                print("  ℹ️  Make sure Ollama is running (ollama serve)")
                        else:
                            print(f"  ❌ Invalid provider. Options: {', '.join(valid)}")
                    else:
                        print(f"  Current provider: {config.brain.provider.upper()}")
                        print(f"  Options: /provider ollama | /provider gemini | /provider groq | /provider claude")
                    continue
                elif cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    print(BANNER)
                    continue
                else:
                    print_help()
                    continue

            print("  🤖 JARVIS thinking...")
            response = jarvis.execute_voice_command(user_input)
            print(f"  🤖 JARVIS:\n{response}\n")
            jarvis.speak(response[:500])

    except KeyboardInterrupt:
        print("\n\nGoodbye!")

    if listener:
        listener.stop()

    print("JARVIS shutdown complete.")


if __name__ == "__main__":
    main()
