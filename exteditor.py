import os
import sys
import shutil
import json
import uuid
import zipfile
import time
from datetime import datetime
from pathlib import Path

# Catégories de fichiers et leurs extensions reconnues + extension cible par défaut
DEFAULT_MEDIA_MAPPING = {
    'IMG': {
        'label': 'Images',
        'target_ext': '.png',
        'exts': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.raw', '.heic'}
    },
    'VID': {
        'label': 'Vidéos',
        'target_ext': '.mp4',
        'exts': {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    },
    'AUD': {
        'label': 'Audios',
        'target_ext': '.mp3',
        'exts': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
    },
    'DOC': {
        'label': 'Documents',
        'target_ext': '.pdf',
        'exts': {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.csv', '.md'}
    },
    'ARC': {
        'label': 'Archives',
        'target_ext': '.zip',
        'exts': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}
    }
}

DEFAULT_EXCLUDED_DIRS = {
    '.venv', 'venv', 'env', '.env', 
    'temp', 'tmp', '.temp', '.tmp', 
    'node_modules', '.git', '__pycache__', '.idea', '.vscode'
}

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_progress_bar(current: int, total: int, filename: str, step_name: str = "Progression", bar_length: int = 25):
    percent = (current / total) * 100 if total > 0 else 100
    filled_length = int(bar_length * current // total) if total > 0 else bar_length
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    display_name = filename if len(filename) <= 25 else filename[:22] + '...'
    sys.stdout.write(f'\r[{bar}] {percent:5.1f}% ({current}/{total}) | {step_name:<18} : {display_name:<25}')
    sys.stdout.flush()
    if current == total:
        print()

def configure_target_extensions() -> dict:
    """Permet à l'utilisateur de choisir quelle extension attribuer à chaque catégorie."""
    print("\n--- 🎯 Choix des Extensions Cibles ---")
    print("Choisissez l'extension à appliquer pour chaque type de fichier.")
    print("(Appuyez sur Entrée pour conserver la valeur par défaut)\n")

    custom_mapping = {}
    for cat_key, info in DEFAULT_MEDIA_MAPPING.items():
        default_ext = info['target_ext']
        user_input = input(f"Ext. pour {info['label']:<10} (ex: .png, .jpg) [Défaut: {default_ext}] : ").strip().lower()
        
        if user_input:
            if not user_input.startswith('.'):
                user_input = f".{user_input}"
            target = user_input
        else:
            target = default_ext

        custom_mapping[cat_key] = {
            'label': info['label'],
            'target_ext': target,
            'exts': info['exts']
        }

    return custom_mapping

def get_target_extension(current_ext: str, media_mapping: dict) -> str:
    ext = current_ext.lower()
    for cat, data in media_mapping.items():
        if ext in data['exts']:
            return data['target_ext']
    return ext  # Conserve l'extension d'origine si non reconnue

def select_target_directory() -> Path:
    current_dir = Path.cwd()
    print(f"Dossier actuel : {current_dir}")
    choice = input("Voulez-vous traiter ce dossier ? (O/n) : ").strip().lower()
    if choice in ('', 'o', 'oui', 'y', 'yes'):
        return current_dir

    while True:
        custom_path = input("Entrez le chemin absolu du dossier : ").strip().strip('"\'')
        target = Path(custom_path)
        if target.is_dir():
            return target
        print("❌ Dossier invalide. Veuillez réessayer.\n")

def collect_files(target_dir: Path) -> tuple[list[Path], bool, set[str], int]:
    script_name = Path(__file__).name if '__file__' in globals() else None
    
    recursive = input("\nInclure les fichiers des sous-dossiers ? (o/N) : ").strip().lower() in ('o', 'oui', 'y', 'yes')
    excluded_dirs = set()

    if recursive:
        print("\n💡 Note : Par défaut, les dossiers dev/temp (.venv, node_modules, etc.) sont ignorés.")
        print("   - Tapez 'TAKE ALL' pour tout inclure.")
        print("   - Ou saisissez des dossiers à exclure séparés par des virgules.")
        
        excl_input = input("\nExclusions sous-dossiers (Entrée = Par défaut | 'TAKE ALL' = Aucun) : ").strip()

        if excl_input.upper() == "TAKE ALL":
            excluded_dirs = set()
        else:
            excluded_dirs = DEFAULT_EXCLUDED_DIRS.copy()
            if excl_input:
                user_dirs = {d.strip() for d in excl_input.split(',') if d.strip()}
                excluded_dirs.update(user_dirs)

    files = []
    subfolder_count = 0

    if recursive:
        for root, dirs, filenames in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            if root != str(target_dir):
                subfolder_count += 1
            for fn in filenames:
                fp = Path(root) / fn
                if fp.name != script_name and not fp.name.startswith("undo_"):
                    files.append(fp)
    else:
        files = [f for f in target_dir.iterdir() if f.is_file() and f.name != script_name and not f.name.startswith("undo_")]

    return files, recursive, excluded_dirs, subfolder_count

def handle_backups(target_dir: Path) -> tuple[Path, dict, list[str]]:
    print("\n--- 💾 Configuration de la Sauvegarde ---")
    print("Options disponibles :")
    print("  1. Copie intégrale des fichiers (Reconstruction complète)")
    print("  2. Archive (.ZIP)")
    print("  3. Log de restauration JSON (Recommandé pour undo_exteditor.py)")
    
    choices = input("Choix (ex: 1,3) [Entrée = Log JSON uniquement] : ").strip().split(',')
    selected = [c.strip() for c in choices if c.strip() in ('1', '2', '3')]
    if not choices or choices == ['']:
        selected = ['3']

    desktop = Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Chemin exact : Desktop\FilesEditor\Exteditor\Backup\TIME
    backup_dir = desktop / "FilesEditor" / "Exteditor" / "Backup" / timestamp

    backup_info = {"dir": None, "has_log": False, "zip_method": zipfile.ZIP_DEFLATED}
    labels = []

    if '1' in selected: labels.append("Copie intégrale")
    if '2' in selected:
        backup_info["zip_method"] = zipfile.ZIP_DEFLATED
        labels.append("Archive ZIP")
    if '3' in selected:
        labels.append("Log JSON (undo_exteditor)")
        backup_info["has_log"] = True

    if selected:
        backup_info["dir"] = backup_dir

    return backup_dir, backup_info, labels

def execute_backup_files(backup_dir: Path, selected_labels: list[str], files: list[Path], target_dir: Path, backup_info: dict):
    if not backup_dir: return
    backup_dir.mkdir(parents=True, exist_ok=True)
    total_files = len(files)
    target_root_name = target_dir.name

    if any("Copie intégrale" in l for l in selected_labels):
        orig_dir = backup_dir / "Full_Copy"
        for idx, f in enumerate(files, start=1):
            rel_path = f.relative_to(target_dir)
            dest = orig_dir / target_root_name / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print_progress_bar(idx, total_files, f.name, step_name="Copie Dossier")

    if any("Archive ZIP" in l for l in selected_labels):
        zip_path = backup_dir / f"{target_root_name}_backup.zip"
        with zipfile.ZipFile(zip_path, 'w', backup_info.get("zip_method", zipfile.ZIP_DEFLATED)) as zipf:
            for idx, f in enumerate(files, start=1):
                rel_path = f.relative_to(target_dir)
                arcname = Path(target_root_name) / rel_path
                zipf.write(f, arcname=str(arcname))
                print_progress_bar(idx, total_files, f.name, step_name="Création ZIP")

def main():
    while True:
        clear_terminal()
        print("=" * 65)
        print("         🖥️ EXTEDITOR - MODIFICATEUR D'EXTENSIONS")
        print("=" * 65)

        target_dir = select_target_directory()
        media_mapping = configure_target_extensions()
        all_files, recursive, excluded_dirs, subfolder_count = collect_files(target_dir)

        if not all_files:
            print("\n⚠️ Aucun fichier à traiter. Appuyez sur Entrée pour relancer...")
            input()
            continue

        backup_dir, backup_info, backup_labels = handle_backups(target_dir)

        clear_terminal()
        print("=" * 65)
        print("          📋 RÉCAPITULATIF DE LA CONFIGURATION          ")
        print("=" * 65)
        print(f"📁 Dossier cible       : {target_dir}")
        print(f"📂 Sous-dossiers       : {'Oui (' + str(subfolder_count) + ' scannés)' if recursive else 'Non'}")
        if recursive:
            print(f"🛡️  Exclusions         : {', '.join(sorted(excluded_dirs)) if excluded_dirs else 'Aucune (TAKE ALL)'}")
        
        print("\n🎯 Extensions choisies :")
        for info in media_mapping.values():
            print(f"   - {info['label']:<10} ➔ {info['target_ext']}")

        print(f"\n📊 Fichiers détectés   : {len(all_files)}")
        print(f"💾 Sauvegardes         : {', '.join(backup_labels) if backup_labels else 'Aucune'}")
        if backup_dir:
            print(f"📂 Chemin Backup       : {backup_dir}")
        print("=" * 65)

        confirm = input("\nLancer le changement d'extensions ? (O/n) : ").strip().lower()
        if confirm in ('', 'o', 'oui', 'y', 'yes'):
            break
        else:
            print("\n🔄 Réinitialisation...")
            time.sleep(1)

    clear_terminal()
    print("=" * 65)
    print("              ⏳ TRAITEMENT EN COURS...              ")
    print("=" * 65 + "\n")

    if backup_dir and backup_labels:
        execute_backup_files(backup_dir, backup_labels, all_files, target_dir, backup_info)
        print("✅ Sauvegarde effectuée.\n")

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "target_directory": str(target_dir),
        "renamed_files": []
    }

    errors = []
    total_files = len(all_files)

    for idx, old_path in enumerate(all_files, start=1):
        try:
            target_ext = get_target_extension(old_path.suffix, media_mapping)
            
            # Si l'extension est déjà conforme, passer
            if old_path.suffix.lower() == target_ext.lower():
                print_progress_bar(idx, total_files, old_path.name, step_name="Déjà conforme")
                continue

            # Garde le nom d'origine exact et applique l'extension cible choisie
            new_path = old_path.with_suffix(target_ext)

            # Gestion des collisions si un fichier avec cette nouvelle extension existe déjà
            if new_path.exists() and new_path != old_path:
                new_path = old_path.with_name(f"{old_path.stem}_{uuid.uuid4().hex[:4]}{target_ext}")

            old_path.rename(new_path)
            
            log_data["renamed_files"].append({
                "original_path": str(old_path),
                "new_path": str(new_path),
                "original_name": old_path.name,
                "new_name": new_path.name
            })
            print_progress_bar(idx, total_files, new_path.name, step_name="Extension changée")

        except Exception as e:
            errors.append(f"Erreur sur [{old_path.name}] : {e}")

    if backup_info["has_log"] and backup_info["dir"]:
        log_file = backup_info["dir"] / "exteditor_log.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)

    clear_terminal()
    print("=" * 65)
    print("           🎉 OPÉRATION TERMINÉE AVEC SUCCÈS !          ")
    print("=" * 65)

    print("\n--- 📊 Statistiques ---")
    print(f"📂 Sous-dossiers scannés : {subfolder_count}")
    print(f"📄 Fichiers scannés      : {total_files}")
    print(f"✅ Extensions modifiées  : {len(log_data['renamed_files'])}")

    print("\n--- 🚨 Bilan des Erreurs ---")
    if errors:
        for err in errors: print(f"  - {err}")
    else:
        print("✨ Aucune erreur")

    if backup_dir and backup_info["has_log"]:
        print("\n--- 🔄 Procédure d'annulation (Rollback) ---")
        print("  1. Lancez : 'python undo_exteditor.py'")
        print(f"  2. Utilisez le fichier log : {backup_dir / 'exteditor_log.json'}")

    print("\n" + "=" * 65)

if __name__ == "__main__":
    main()