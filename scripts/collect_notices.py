"""Collect licenses and metadata for the installed desktop dependency closure."""
import importlib.metadata as metadata
from pathlib import Path
import shutil
import sys
import sysconfig

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def collect(destination):
    destination.mkdir(parents=True, exist_ok=True)
    pending = [("reelforge", {"desktop"}), ("pyinstaller", set())]
    seen = set()
    inventory = []
    while pending:
        name, extras = pending.pop()
        key = (canonicalize_name(name), tuple(sorted(extras)))
        if key in seen:
            continue
        seen.add(key)
        distribution = metadata.distribution(name)
        directory = destination / (canonicalize_name(name) + "-" + distribution.version)
        directory.mkdir(exist_ok=True)
        (directory / "METADATA.txt").write_text(distribution.read_text("METADATA") or "", encoding="utf-8")
        for file in distribution.files or []:
            if any(word in file.name.lower() for word in ["license", "copying", "notice", "copyright"]):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    target = directory / Path(str(file).replace("..", "parent"))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        inventory.append(f"{distribution.metadata['Name']}=={distribution.version}")
        for dependency in distribution.requires or []:
            requirement = Requirement(dependency)
            if not requirement.marker or any(requirement.marker.evaluate({"extra": extra}) for extra in extras | {""}):
                pending.append((requirement.name, set(requirement.extras)))
    for candidate in [Path(sysconfig.get_path("stdlib")) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE.txt"]:
        if candidate.is_file():
            shutil.copy2(candidate, destination / "Python-LICENSE.txt")
            break
    else:
        raise RuntimeError("Python's license must be included before building")
    (destination / "DEPENDENCIES.txt").write_text("\n".join(sorted(set(inventory))) + "\n", encoding="utf-8")
