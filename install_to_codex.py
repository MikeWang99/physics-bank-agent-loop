from pathlib import Path
import os
import shutil
import sys


REPO_ROOT = Path(__file__).resolve().parent
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
SKILLS_SOURCE = REPO_ROOT / "skills"
SKILLS_TARGET = CODEX_HOME / "skills"
ROLE_SOURCE = REPO_ROOT / "skills" / "physics-bank-agent-loop" / "agents"
ROLE_TARGET = CODEX_HOME / "agents"
ROLE_FILES = ("physics_bank_creator.toml", "physics_bank_reviewer.toml")


def install_tree(source: Path, target: Path) -> None:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    for src in files:
        dst = target / src.relative_to(source)
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise RuntimeError(f"Refusing to overwrite a different file: {dst}")
    for src in files:
        dst = target / src.relative_to(source)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)


def install_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Refusing to overwrite a different file: {target}")
        return
    shutil.copy2(source, target)


try:
    install_tree(SKILLS_SOURCE, SKILLS_TARGET)
    for filename in ROLE_FILES:
        install_file(ROLE_SOURCE / filename, ROLE_TARGET / filename)
except Exception as exc:
    print(f"Installation stopped: {exc}", file=sys.stderr)
    raise SystemExit(1)

print(f"Installed skills: {SKILLS_TARGET / 'physics-bank-agent-loop'} and {SKILLS_TARGET / 'physics-bank'}")
print(f"Installed role profiles: {ROLE_TARGET / ROLE_FILES[0]} and {ROLE_TARGET / ROLE_FILES[1]}")
