#!/usr/bin/env python3
"""
deploy_zhou.py — Deploy WAM extension ONLY to the current zhou user.

NEVER touches other Windows accounts. This replaces hot_push_all.ps1.

Usage:
    python deploy_zhou.py              # deploy latest WAM to zhou
    python deploy_zhou.py --verify     # verify current installation
    python deploy_zhou.py --uninstall  # remove WAM from zhou
"""
import os, sys, json, shutil, argparse
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

OWNER = 'zhou'
VERSION = '7.2.1'
EXT_ID = 'local.wam'

# Source: the _wam_bundle directory (sibling to scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = SCRIPT_DIR.parent / '_wam_bundle'

# Target: zhou's .windsurf/extensions
TARGET_EXT_DIR = Path(f'C:/Users/{OWNER}/.windsurf/extensions')
TARGET_WAM_DIR = TARGET_EXT_DIR / f'{EXT_ID}-{VERSION}'

REQUIRED_FILES = ['extension.js', 'package.json']
OPTIONAL_FILES = ['media/icon.svg']


def verify_bundle():
    """Check that the bundle has all required files."""
    ok = True
    for f in REQUIRED_FILES:
        fp = BUNDLE_DIR / f
        if not fp.exists():
            print(f'  [MISSING] {fp}')
            ok = False
        else:
            print(f'  [OK] {f} ({fp.stat().st_size:,} bytes)')
    for f in OPTIONAL_FILES:
        fp = BUNDLE_DIR / f
        if fp.exists():
            print(f'  [OK] {f}')
        else:
            print(f'  [WARN] {f} (optional, missing)')
    return ok


def deploy():
    """Deploy WAM to zhou's extensions directory."""
    print(f'\n  Deploying WAM v{VERSION} to {OWNER}...')

    # Verify current user
    current_user = os.environ.get('USERNAME', '')
    if current_user != OWNER:
        print(f'  [WARN] Current user is "{current_user}", not "{OWNER}".')
        print(f'         Deploying to {OWNER} profile anyway (admin access required).')

    # Verify bundle
    print(f'\n  Source: {BUNDLE_DIR}')
    if not verify_bundle():
        print('\n  [FATAL] Bundle incomplete. Aborting.')
        return False

    # Create target directory
    TARGET_WAM_DIR.mkdir(parents=True, exist_ok=True)
    (TARGET_WAM_DIR / 'media').mkdir(exist_ok=True)

    # Remove old WAM versions
    if TARGET_EXT_DIR.exists():
        for d in TARGET_EXT_DIR.iterdir():
            if d.is_dir() and d.name.startswith('local.wam') and d.name != f'{EXT_ID}-{VERSION}':
                print(f'  Removing old: {d.name}')
                shutil.rmtree(d, ignore_errors=True)

    # Copy files
    for f in REQUIRED_FILES + OPTIONAL_FILES:
        src = BUNDLE_DIR / f
        dst = TARGET_WAM_DIR / f
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    ext_size = (TARGET_WAM_DIR / 'extension.js').stat().st_size
    print(f'  Deployed: extension.js ({ext_size:,} bytes)')

    # Update extensions.json
    ext_json = TARGET_EXT_DIR / 'extensions.json'
    arr = []
    if ext_json.exists():
        try:
            with open(ext_json, 'r', encoding='utf-8-sig') as f:
                arr = json.load(f)
            if not isinstance(arr, list):
                arr = []
        except:
            arr = []

    # Remove old WAM entries
    arr = [x for x in arr if x.get('identifier', {}).get('id', '') != EXT_ID]

    # Add new entry
    wam_path = str(TARGET_WAM_DIR).replace('\\', '/')
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    arr.append({
        'identifier': {'id': EXT_ID, 'uuid': EXT_ID},
        'version': VERSION,
        'location': {'$mid': 1, 'path': wam_path, 'scheme': 'file'},
        'relativeLocation': f'{EXT_ID}-{VERSION}',
        'metadata': {
            'installedTimestamp': ts,
            'targetPlatform': 'undefined',
            'size': ext_size
        }
    })

    with open(ext_json, 'w', encoding='utf-8') as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)

    print(f'  extensions.json updated ({len(arr)} extensions)')
    print(f'\n  [OK] WAM v{VERSION} deployed to {OWNER}')
    print(f'  Restart Windsurf to activate.')
    return True


def verify():
    """Verify current WAM installation for zhou."""
    print(f'\n  Verifying WAM for {OWNER}...')

    if not TARGET_WAM_DIR.exists():
        print(f'  [MISSING] {TARGET_WAM_DIR}')
        return False

    ok = True
    for f in REQUIRED_FILES:
        fp = TARGET_WAM_DIR / f
        if fp.exists():
            print(f'  [OK] {f} ({fp.stat().st_size:,} bytes) mod={fp.stat().st_mtime}')
        else:
            print(f'  [MISSING] {f}')
            ok = False

    # Check extensions.json
    ext_json = TARGET_EXT_DIR / 'extensions.json'
    if ext_json.exists():
        try:
            with open(ext_json, 'r', encoding='utf-8-sig') as f:
                arr = json.load(f)
            wam_entries = [x for x in arr if x.get('identifier', {}).get('id', '') == EXT_ID]
            if wam_entries:
                print(f'  [OK] extensions.json: v{wam_entries[0].get("version", "?")}')
            else:
                print(f'  [MISSING] WAM not in extensions.json')
                ok = False
        except Exception as e:
            print(f'  [WARN] extensions.json: {e}')

    # Check no pollution in other users
    print(f'\n  Checking other users...')
    clean = True
    for d in Path('C:/Users').iterdir():
        if not d.is_dir() or d.name == OWNER or d.name in ('Public', 'Default', 'Default User', 'All Users'):
            continue
        ext = d / '.windsurf' / 'extensions'
        if ext.exists():
            for sub in ext.iterdir():
                if sub.is_dir() and sub.name.startswith('local.wam'):
                    print(f'  [POLLUTION] {d.name}: {sub.name}')
                    clean = False
    if clean:
        print(f'  [OK] No WAM pollution in other users')

    status = 'PASS' if (ok and clean) else 'ISSUES FOUND'
    print(f'\n  Verification: {status}')
    return ok and clean


def uninstall():
    """Remove WAM from zhou's extensions."""
    print(f'\n  Uninstalling WAM from {OWNER}...')

    # Remove extension directory
    if TARGET_WAM_DIR.exists():
        shutil.rmtree(TARGET_WAM_DIR, ignore_errors=True)
        print(f'  Removed {TARGET_WAM_DIR.name}')

    # Also remove any other WAM versions
    if TARGET_EXT_DIR.exists():
        for d in TARGET_EXT_DIR.iterdir():
            if d.is_dir() and d.name.startswith('local.wam'):
                shutil.rmtree(d, ignore_errors=True)
                print(f'  Removed {d.name}')

    # Clean extensions.json
    ext_json = TARGET_EXT_DIR / 'extensions.json'
    if ext_json.exists():
        try:
            with open(ext_json, 'r', encoding='utf-8-sig') as f:
                arr = json.load(f)
            arr = [x for x in arr if x.get('identifier', {}).get('id', '') != EXT_ID]
            with open(ext_json, 'w', encoding='utf-8') as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
            print(f'  extensions.json cleaned')
        except:
            pass

    print(f'  [OK] WAM uninstalled from {OWNER}')
    print(f'  Note: .wam-hot/ data preserved. Delete manually if needed.')


def main():
    parser = argparse.ArgumentParser(description=f'Deploy WAM to {OWNER} only')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--verify', action='store_true', help='Verify installation')
    group.add_argument('--uninstall', action='store_true', help='Remove WAM')
    args = parser.parse_args()

    print()
    print('=' * 50)
    print(f'  WAM Deploy (zhou-only) v{VERSION}')
    print('=' * 50)

    if args.verify:
        verify()
    elif args.uninstall:
        uninstall()
    else:
        deploy()

    print()


if __name__ == '__main__':
    main()
