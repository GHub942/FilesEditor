import sys
import json
from pathlib import Path

def print_progress_bar(current: int, total: int, filename: str, bar_length: int = 25):
    """Barre de progression animée pour le rétablissement des extensions."""
    percent = (current / total) * 100 if total > 0 else 100
    filled_length = int(bar_length * current // total) if total > 0 else bar_length
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    display_name = filename if len(filename) <= 25 else filename[:22] + '...'
    sys.stdout.write(f'\r[{bar}] {percent:5.1f}% ({current}/{total}) | Restauration : {display_name:<25}')
    sys.stdout.flush()
    if current == total:
        print()

def main():
    print("=" * 65)
    print("       🔄 UNDO EXTEDITOR - RESTAURATION DES EXTENSIONS       ")
    print("=" * 65 + "\n")

    log_input = input("Entrez le chemin complet du fichier 'exteditor_log.json' : ").strip().strip('"\'')
    log_path = Path(log_input)

    if not log_path.is_file():
        print("\n❌ Fichier de log introuvable. Assurez-vous d'avoir indiqué le bon chemin.")
        return

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except Exception as e:
        print(f"\n❌ Erreur lors de la lecture du fichier journal : {e}")
        return

    entries = log_data.get("renamed_files", [])
    total = len(entries)
    
    if total == 0:
        print("\n⚠️ Aucune modification enregistrée dans ce fichier journal.")
        return

    print(f"\n🔍 {total} extension(s) à restaurer...\n")
    restored = 0
    errors = 0

    for idx, entry in enumerate(entries, start=1):
        current_file = Path(entry["new_path"])
        original_file = Path(entry["original_path"])

        if current_file.exists():
            try:
                current_file.rename(original_file)
                restored += 1
                print_progress_bar(idx, total, original_file.name)
            except Exception as e:
                errors += 1
                print_progress_bar(idx, total, f"Erreur: {current_file.name}")
        else:
            errors += 1
            print_progress_bar(idx, total, f"Introuvable: {current_file.name}")

    print("\n" + "=" * 65)
    print(f"🎉 Restauration terminée avec succès !")
    print(f"📊 Fichiers rétablis : {restored} / {total}")
    if errors > 0:
        print(f"⚠️ Erreurs rencontrées : {errors}")
    print("=" * 65)

if __name__ == "__main__":
    main()