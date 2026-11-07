import os
import sys
import shutil
import json
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

# Mapping par défaut des catégories
EXTENSION_PREFIXES = {
    'IMG': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.raw', '.heic'},
    'VID': {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'},
    'ARC': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'},
    'AUD': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'},
    'DOC': {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.csv', '.md'}
}
DEFAULT_PREFIX = 'FILE'

# Dossiers ignorés par défaut (sauf si "TAKE ALL" est saisi)
DEFAULT_EXCLUDED_DIRS = {
    '.venv', 'venv', 'env', '.env', 
    'temp', 'tmp', '.temp', '.tmp', 
    'node_modules', '.git', '__pycache__', '.idea', '.vscode'
}


def clear_terminal():
    """Nettoie le terminal selon l'OS."""
    os.system('cls' if os.name == 'nt' else 'clear')


def sanitize_filename(name: str, replacement: str = "-") -> str:
    """Remplace les caractères interdits sous Windows (\\ / : * ? " < > |) par un caractère sûr."""
    sanitized = re.sub(r'[\\/:*?"<>|]', replacement, name)
    return sanitized.strip()


def print_progress_bar(current: int, total: int, filename: str, step_name: str = "Progression", bar_length: int = 25):
    """Affiche une barre de progression animée avec pourcentage, étape et nom de fichier."""
    percent = (current / total) * 100 if total > 0 else 100
    filled_length = int(bar_length * current // total) if total > 0 else bar_length
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    
    display_name = filename if len(filename) <= 25 else filename[:22] + '...'
    # Format fixe pour éviter les sauts de ligne ou le décalage visuel
    sys.stdout.write(f'\r[{bar}] {percent:5.1f}% ({current}/{total}) | {step_name:<16} : {display_name:<25}')
    sys.stdout.flush()
    if current == total:
        print()


def get_file_prefix(extension: str, prefix_mapping: dict) -> str:
    ext = extension.lower()
    for prefix, ext_set in prefix_mapping.items():
        if ext in ext_set:
            return prefix
    return DEFAULT_PREFIX


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


def configure_prefixes_and_separator() -> tuple[str, str, dict]:
    print("\n--- ⚙️ Personnalisation du Format & Préfixes ---")
    
    print("Préfixe global :")
    print("  - Laissez VIDE pour utiliser le nom du dossier où se trouve chaque fichier (DYNAMIQUE).")
    print("  - Ou entrez un texte fixe pour l'appliquer à TOUS les fichiers.")
    custom_global = input("Saisie préfixe global [Défaut: Nom du dossier parent] : ").strip()
    
    if custom_global:
        global_prefix = sanitize_filename(custom_global)
    else:
        global_prefix = "AUTO"

    custom_sep = input("\nSéparateur entre le préfixe et la catégorie [Défaut: '__'] : ").strip()
    separator = sanitize_filename(custom_sep) if custom_sep else "__"

    mapping = EXTENSION_PREFIXES.copy()
    change_cat = input("\nSouhaitez-vous modifier les préfixes de catégorie (IMG, VID, etc.) ? (o/N) : ").strip().lower()
    
    if change_cat in ('o', 'oui', 'y', 'yes'):
        new_mapping = {}
        for old_prefix, extensions in mapping.items():
            user_pref = input(f"Préfixe pour {old_prefix} (extensions {tuple(extensions)[:3]}...) [Défaut: {old_prefix}] : ").strip().upper()
            chosen_prefix = sanitize_filename(user_pref) if user_pref else old_prefix
            new_mapping[chosen_prefix] = extensions
        mapping = new_mapping

    return global_prefix, separator, mapping


def filter_categories(prefix_mapping: dict) -> set[str]:
    available = list(prefix_mapping.keys()) + [DEFAULT_PREFIX]
    print("\n--- 🎯 Filtrage par Catégorie ---")
    print(f"Catégories disponibles : {', '.join(available)}")
    choice = input("Quelles catégories traiter ? (ex: IMG,VID) [Entrée = TOUTES] : ").strip()

    if not choice:
        return set(available)

    selected = {c.strip().upper() for c in choice.split(',') if c.strip()}
    valid_selected = selected.intersection(set(available))

    if not valid_selected:
        return set(available)

    return valid_selected


def collect_files(target_dir: Path) -> tuple[list[Path], bool, set[str], int]:
    script_name = Path(__file__).name if '__file__' in globals() else None
    
    recursive = input("\nInclure les fichiers des sous-dossiers ? (o/N) : ").strip().lower() in ('o', 'oui', 'y', 'yes')
    excluded_dirs = set()

    if recursive:
        print("\n💡 Note : Par défaut, les dossiers de dev/temp (.venv, temp, node_modules, .git, etc.) sont ignorés.")
        print("   - Tapez 'TAKE ALL' pour tout inclure sans exclusion.")
        print("   - Ou saisissez des dossiers spécifiques à exclure en plus (séparés par des virgules).")
        
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
                if fp.name != script_name:
                    files.append(fp)
    else:
        files = [f for f in target_dir.iterdir() if f.is_file() and f.name != script_name]

    return files, recursive, excluded_dirs, subfolder_count


def handle_backups() -> tuple[Path, dict, list[str]]:
    print("\n--- 💾 Configuration de la Sauvegarde ---")
    print("Options disponibles :")
    print("  1. Copie intégrale des fichiers (avec sous-dossiers)")
    print("  2. Copie compressée (.ZIP) (avec sous-dossiers)")
    print("  3. Fichier de log JSON (recommandé pour l'annulation)")
    print("  (Laissez vide pour AUCUNE sauvegarde)")
    
    choices = input("Entrez les numéros souhaités séparés par des virgules (ex: 1,3) : ").strip().split(',')
    selected = [c.strip() for c in choices if c.strip() in ('1', '2', '3')]

    desktop = Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = desktop / "FilesEditor" / "FilesRenamer" / "Backup" / timestamp

    backup_info = {"dir": None, "has_log": False, "zip_method": zipfile.ZIP_DEFLATED}
    labels = []

    if '1' in selected: labels.append("Copie intégrale (Arborescence)")
    
    if '2' in selected: 
        print("\n⚙️ Choix du niveau de compression ZIP :")
        print("  1. Stockage (Aucune compression)  | ~1-2 sec / Go  (Vitesse max)")
        print("  2. Standard (Deflate)             | ~10-15 sec / Go (Équilibré) [DÉFAUT]")
        print("  3. Maximum (LZMA)                 | ~1-2 min / Go   (Lent mais fichiers + légers)")
        
        comp_choice = input("Votre choix (1/2/3) [Entrée=2] : ").strip()
        if comp_choice == '1':
            backup_info["zip_method"] = zipfile.ZIP_STORED
            labels.append("Archive ZIP (Aucune compression)")
        elif comp_choice == '3':
            backup_info["zip_method"] = zipfile.ZIP_LZMA
            labels.append("Archive ZIP (Compression Maximum)")
        else:
            backup_info["zip_method"] = zipfile.ZIP_DEFLATED
            labels.append("Archive ZIP (Compression Standard)")

    if '3' in selected: 
        labels.append("Log JSON (undo_renamer)")
        backup_info["has_log"] = True

    if selected:
        backup_info["dir"] = backup_dir

    return backup_dir, backup_info, labels


def execute_backup_files(backup_dir: Path, selected_labels: list[str], files: list[Path], target_dir: Path, backup_info: dict):
    """Exécute la création physique des sauvegardes avec barre de progression."""
    if not backup_dir:
        return

    backup_dir.mkdir(parents=True, exist_ok=True)
    total_files = len(files)
    target_root_name = target_dir.name  # Pour encapsuler dans un dossier racine

    # 1. Copie Intégrale
    if any("Copie intégrale" in l for l in selected_labels):
        orig_dir = backup_dir / "Originals"
        for idx, f in enumerate(files, start=1):
            # Recréer l'arborescence : backup_dir/Originals/NomDuDossierCible/SousDossier.../fichier
            rel_path = f.relative_to(target_dir)
            dest = orig_dir / target_root_name / rel_path
            
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            print_progress_bar(idx, total_files, f.name, step_name="Copie Dossier")

    # 2. Archive ZIP
    if any("Archive ZIP" in l for l in selected_labels):
        zip_path = backup_dir / f"{target_root_name}_backup.zip"
        zip_method = backup_info.get("zip_method", zipfile.ZIP_DEFLATED)
        
        with zipfile.ZipFile(zip_path, 'w', zip_method) as zipf:
            for idx, f in enumerate(files, start=1):
                # Arborescence dans le zip : NomDuDossierCible/SousDossier.../fichier
                rel_path = f.relative_to(target_dir)
                arcname = Path(target_root_name) / rel_path
                zipf.write(f, arcname=str(arcname))
                print_progress_bar(idx, total_files, f.name, step_name="Création ZIP")


def main():
    while True:
        clear_terminal()
        print("=" * 60)
        print("           RENOMMEUR DE FICHIERS AUTOMATIQUE           ")
        print("=" * 60)

        # 1. Configuration
        target_dir = select_target_directory()
        global_prefix_setting, separator, prefix_mapping = configure_prefixes_and_separator()
        allowed_categories = filter_categories(prefix_mapping)
        all_files, recursive, excluded_dirs, subfolder_count = collect_files(target_dir)

        files_to_process = [
            f for f in all_files 
            if get_file_prefix(f.suffix, prefix_mapping) in allowed_categories
        ]

        if not files_to_process:
            print("\n⚠️ Aucun fichier à traiter. Appuyez sur Entrée pour relancer...")
            input()
            continue

        digits_input = input("\nNombre de chiffres minimum pour la numérotation (ex: 3 -> 001) [Défaut: 1] : ").strip()
        padding = int(digits_input) if digits_input.isdigit() else 1

        backup_dir, backup_info, backup_labels = handle_backups()

        # 2. Récapitulatif & Validation
        clear_terminal()
        print("=" * 60)
        print("          📋 RÉCAPITULATIF DE LA CONFIGURATION          ")
        print("=" * 60)
        print(f"📁 Dossier cible       : {target_dir}")
        print(f"📂 Mode Sous-dossiers  : {'Oui (' + str(subfolder_count) + ' sous-dossier(s) trouvé(s))' if recursive else 'Non'}")
        if recursive and excluded_dirs:
            print(f"🛡️  Dossiers ignorés    : {', '.join(sorted(excluded_dirs))}")
        print(f"🏷️  Préfixe global      : {'[DYNAMIQUE par dossier]' if global_prefix_setting == 'AUTO' else global_prefix_setting}")
        print(f"🔗 Séparateur          : '{separator}'")
        print(f"🎯 Catégories incluses : {', '.join(sorted(allowed_categories))}")
        print(f"🔢 Alignement chiffres : {padding} (ex: {'1'.zfill(padding)})")
        print(f"📊 Fichiers à traiter  : {len(files_to_process)} / {len(all_files)} trouvés")
        print(f"💾 Sauvegarde activée  : {', '.join(backup_labels) if backup_labels else 'Aucune'}")
        if backup_dir:
            print(f"📂 Emplacement Backup  : {backup_dir}")
        print("=" * 60)

        confirm = input("\nVoulez-vous exécuter le processus avec ces paramètres ? (O/n) : ").strip().lower()
        if confirm in ('', 'o', 'oui', 'y', 'yes'):
            break
        else:
            print("\n🔄 Annulation... Rechargement des paramètres.")
            import time; time.sleep(1)

    # 3. Exécution
    clear_terminal()
    print("=" * 60)
    print("              ⏳ EXÉCUTION DU PROCESSUS...              ")
    print("=" * 60 + "\n")

    # Phase A : Sauvegarde
    if backup_dir and backup_labels:
        execute_backup_files(backup_dir, backup_labels, files_to_process, target_dir, backup_info)
        print("✅ Phase de sauvegarde terminée.\n")

    # Regroupement & Planification
    categorized_by_folder = {}
    for f in files_to_process:
        folder_path = f.parent
        cat_prefix = get_file_prefix(f.suffix, prefix_mapping)
        categorized_by_folder.setdefault((folder_path, cat_prefix), []).append(f)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "target_directory": str(target_dir),
        "separator": separator,
        "renamed_files": []
    }

    rename_plan = []
    for (folder_path, cat_prefix), file_list in categorized_by_folder.items():
        file_list.sort(key=lambda f: f.stat().st_size)
        current_prefix = sanitize_filename(folder_path.name) if global_prefix_setting == "AUTO" else global_prefix_setting

        for index, old_path in enumerate(file_list, start=1):
            index_str = str(index).zfill(padding)
            ext = old_path.suffix.lower()
            final_name = f"{current_prefix}{separator}{cat_prefix}_{index_str}{ext}"
            final_path = old_path.parent / final_name
            temp_name = f"__tmp_{uuid.uuid4().hex[:8]}__{ext}"
            temp_path = old_path.parent / temp_name

            rename_plan.append((old_path, temp_path, final_path, old_path.name, final_name))

    total_files = len(rename_plan)
    errors = []

    # Phase B : Renommage temporaire
    for idx, (old_p, temp_p, final_p, orig_n, final_n) in enumerate(rename_plan, start=1):
        try:
            old_p.rename(temp_p)
            print_progress_bar(idx, total_files, orig_n, step_name="Passe 1/2 (Temp)")
        except Exception as e:
            errors.append(f"Erreur Passe 1 [{orig_n}] : {e}")

    # Phase C : Renommage Final
    for idx, (old_p, temp_p, final_p, orig_n, final_n) in enumerate(rename_plan, start=1):
        try:
            temp_p.rename(final_p)
            log_data["renamed_files"].append({
                "original_path": str(old_p),
                "new_path": str(final_p),
                "original_name": orig_n,
                "new_name": final_n
            })
            print_progress_bar(idx, total_files, final_n, step_name="Passe 2/2 (Déf)")
        except Exception as e:
            errors.append(f"Erreur Passe 2 [{temp_p.name} -> {final_n}] : {e}")

    # Sauvegarde du log
    if backup_info["has_log"] and backup_info["dir"]:
        log_file = backup_info["dir"] / "rename_log.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)

    # 4. Bilan Final
    clear_terminal()
    print("=" * 60)
    print("           🎉 OPÉRATION TERMINÉE AVEC SUCCÈS !          ")
    print("=" * 60)

    print("\n--- ⚙️ Rappel de la Configuration Appliquée ---")
    print(f"📁 Dossier cible       : {target_dir}")
    print(f"🏷️  Préfixe utilisé     : {'DYNAMIQUE (Nom du dossier)' if global_prefix_setting == 'AUTO' else global_prefix_setting}")
    print(f"🔗 Séparateur          : '{separator}'")
    print(f"🔢 Numérotation        : Alignement à {padding} chiffre(s)")

    print("\n--- 📊 Bilan des Fichiers & Dossiers ---")
    print(f"📂 Sous-dossiers scannés : {subfolder_count}")
    print(f"📄 Fichiers totaux trouvés : {len(all_files)}")
    print(f"✅ Fichiers renommés       : {len(log_data['renamed_files'])} / {total_files}")
    
    if errors:
        print(f"\n❌ ERREURS DÉTECTÉES ({len(errors)}) :")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\n✨ Aucune erreur détectée durant le processus.")

    if backup_dir and backup_labels:
        print("\n--- 💾 Informations de Sauvegarde & Annulation ---")
        print(f"📍 Chemin Backup        : {backup_dir}")
        print(f"📦 Éléments sauvegardés : {', '.join(backup_labels)}")
        if backup_info["has_log"]:
            print("\n🔄 COMMENT ANNULER CETTE ACTION (ROLLBACK) :")
            print("  1. Lancez le script 'undo_renamer.py'")
            print(f"  2. Fournissez le chemin du fichier log suivant :")
            print(f"     '{backup_dir / 'rename_log.json'}'")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()