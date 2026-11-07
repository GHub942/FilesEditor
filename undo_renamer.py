import os
import sys
import json
from pathlib import Path


def print_progress_bar(current: int, total: int, filename: str, bar_length: int = 30):
    """Barre de progression animée pour la restauration."""
    percent = (current / total) * 100
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    display_name = filename if len(filename) <= 30 else filename[:27] + '...'
    sys.stdout.write(f'\r[{bar}] {percent:5.1f}% ({current}/{total}) | Restauration : {display_name:<30}')
    sys.stdout.flush()
    if current == total:
        print()


def main():
    print("=" * 60)
    print("         RESTAURATION DES NOMS D'ORIGINE (UNDO)         ")
    print("=" * 60 + "\n")

    log_input = input("Entrez le chemin complet du fichier 'rename_log.json' : ").strip().strip('"\'')
    log_path = Path(log_input)

    if not log_path.is_file():
        print("❌ Fichier de log introuvable.")
        return

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier log : {e}")
        return

    entries = log_data.get("renamed_files", [])
    if not entries:
        print("⚠️ Aucune entrée trouvée dans ce journal.")
        return

    total = len(entries)
    print(f"\n🔍 {total} fichier(s) à restaurer.\n")
    print_progress_bar(0, total, "Initialisation...")

    restored = 0
    errors = 0

    for idx, entry in enumerate(entries, start=1):
        current_file = Path(entry["new_path"])
        original_file = Path(entry["original_path"])

        if current_file.exists():
            current_file.rename(original_file)
            restored += 1
            print_progress_bar(idx, total, original_file.name)
        else:
            errors += 1
            print_progress_bar(idx, total, f"Introuvable: {current_file.name}")

    print("\n" + "=" * 60)
    print(f"✅ Restauration terminée ! ({restored} réussis, {errors} erreurs)")
    print("=" * 60)


if __name__ == "__main__":
    main()