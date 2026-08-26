import os
from pathlib import Path

from powerkit.installer import load_project_config, load_install_manifest, Installer, InstallRequest, execute_install, read_json_file, sha256_file
from powerkit.state import write_project_config, build_project_config, PROJECT_CONFIG_PATH
from powerkit.cli import target_path, default_profiles

def migrate_to_global(target: Path, dry_run: bool = False, verbose: bool = False) -> bool:
    manifest = load_install_manifest(target)
    if not manifest:
        print("No vendored PowerKit installation found to migrate.")
        return False
        
    config = load_project_config(target, required=False)
    platforms = set(manifest.get("platforms", ["codex", "claude", "copilot"]))
    profiles = tuple(manifest.get("profiles", default_profiles()))
    
    print("Migrating vendored PowerKit to global installation...")
    request = InstallRequest(
        base=target,
        profiles=profiles,
        platforms=frozenset(platforms),
        scope="user",
        dry_run=dry_run,
        verbose=verbose,
    )
    execute_install(request)
    
    if not dry_run:
        if config is None:
            config = build_project_config(target, profiles=profiles, platforms=tuple(platforms), agents=True, hooks_staged=False)
        write_project_config(target, config, dry_run=False)
        
        assets = manifest.get("managed_assets", [])
        for asset in assets:
            path_str = asset.get("path")
            expected_sha = asset.get("sha256")
            if not path_str or not expected_sha:
                continue
            
            # Avoid removing the project overlay configuration during migration
            if path_str == str(PROJECT_CONFIG_PATH):
                continue
                
            file_path = target / path_str
            if file_path.is_file():
                current_sha = sha256_file(file_path)
                if current_sha == expected_sha:
                    if verbose:
                        print(f"Removing unmodified vendored asset: {path_str}")
                    file_path.unlink()
                else:
                    print(f"Preserving modified vendored asset: {path_str}")
                    
        # Remove empty directories
        for root, dirs, files in os.walk(target, topdown=False):
            if root.startswith(str(target / ".git")):
                continue
            for d in dirs:
                dir_path = Path(root) / d
                if dir_path.is_dir() and not os.listdir(dir_path):
                    dir_path.rmdir()
                    
        manifest_path = target / ".ai-powerkit" / "install-manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()
            
    print("Migration complete. Repository is now using global PowerKit.")
    return True
