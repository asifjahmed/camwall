"""Telling the user about an alert on this computer: a chime, the alert spoken, and a notification, by whatever the
system has (macOS: afplay, say, osascript; Windows: PowerShell; Linux: paplay or aplay, spd-say or espeak,
notify-send). Whatever isn't there is skipped."""

import os
import shutil
import subprocess
import sys

MAC_SOUND = "/System/Library/Sounds/Sosumi.aiff"
LINUX_SOUNDS = ("/usr/share/sounds/freedesktop/stereo/complete.oga", "/usr/share/sounds/freedesktop/stereo/bell.oga")


def _run(*args):
    try:
        subprocess.run(args, check=False, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       **({"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}))
    except (OSError, subprocess.TimeoutExpired):
        pass


def _powershell(script):
    _run("powershell", "-NoProfile", "-NonInteractive", "-Command", script)


def _ps_quote(text):
    return "'" + text.replace("'", "''") + "'"


def chime():
    if sys.platform == "darwin":
        _run("afplay", MAC_SOUND)
    elif sys.platform == "win32":
        _powershell("[System.Media.SystemSounds]::Exclamation.Play(); Start-Sleep -Milliseconds 700")
    else:
        player = shutil.which("paplay") or shutil.which("aplay")
        sound = next((s for s in LINUX_SOUNDS if os.path.exists(s)), None)
        if player and sound:
            _run(player, sound)


def speak(text):
    if sys.platform == "darwin":
        _run("say", text)
    elif sys.platform == "win32":
        _powershell(f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak({_ps_quote(text)})")
    else:
        tool = shutil.which("spd-say") or shutil.which("espeak-ng") or shutil.which("espeak")
        if tool:
            _run(tool, *(["--wait"] if tool.endswith("spd-say") else []), text)


def notification(title, text):
    if sys.platform == "darwin":
        quoted = text.replace("\\", "\\\\").replace('"', '\\"')
        _run("osascript", "-e", f'display notification "{quoted}" with title "{title}"')
    elif sys.platform == "win32":
        _powershell(
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
            "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            f"$x = $t.GetElementsByTagName('text'); $x.Item(0).AppendChild($t.CreateTextNode({_ps_quote(title)})) > $null; "
            f"$x.Item(1).AppendChild($t.CreateTextNode({_ps_quote(text)})) > $null; "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('camwall').Show([Windows.UI.Notifications.ToastNotification]::new($t))")
    elif shutil.which("notify-send"):
        _run("notify-send", "--app-name=camwall", title, text)


def announce(message, sound=True, voice=True, desktop=True):
    """An alert, as the user's settings have it (all three off: nothing)."""
    if sound:
        chime()
    if voice:
        speak(message)
    if desktop:
        notification("camwall", message)
