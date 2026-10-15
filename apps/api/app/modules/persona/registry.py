"""Loads and validates mentor packs from YAML."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.modules.persona.schemas import Defaults, Lens, Pack
from app.modules.profile.taxonomy import RoleFamily, Seniority

log = logging.getLogger(__name__)


class PackError(Exception):
    pass


def find_packs_dir() -> Path:
    configured = get_settings().packs_dir
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packs"
        if (candidate / "defaults.yaml").exists():
            return candidate
    raise PackError("Could not find the packs directory. Set PACKS_DIR.")


@dataclass(frozen=True)
class PackRegistry:
    packs: dict[str, Pack]
    lenses: dict[str, Lens]
    defaults: Defaults

    def get(self, lens_id: str) -> Lens | None:
        return self.lenses.get(lens_id)

    def default_for(self, role_family: str | None, seniority: str | None) -> str:
        if role_family:
            for rule in self.defaults.rules:
                if rule.role_family.value != role_family:
                    continue
                if rule.seniority and (
                    seniority is None or Seniority(seniority) not in rule.seniority
                ):
                    continue
                return rule.lens
        return self.defaults.default_lens

    @property
    def lens_ids(self) -> list[str]:
        return sorted(self.lenses)


def load_registry(directory: Path) -> PackRegistry:
    packs: dict[str, Pack] = {}
    lenses: dict[str, Lens] = {}
    for path in sorted(directory.glob("*.yaml")):
        if path.name == "defaults.yaml":
            continue
        try:
            pack = Pack.model_validate(yaml.safe_load(path.read_text()))
        except Exception as exc:
            raise PackError(f"{path.name}: {exc}") from exc
        if pack.pack.id in packs:
            raise PackError(f"Duplicate pack id {pack.pack.id}")
        packs[pack.pack.id] = pack
        for lens in pack.lenses:
            if lens.id in lenses:
                raise PackError(f"Duplicate lens id {lens.id}")
            lenses[lens.id] = lens
    try:
        defaults = Defaults.model_validate(
            yaml.safe_load((directory / "defaults.yaml").read_text())
        )
    except Exception as exc:
        raise PackError(f"defaults.yaml: {exc}") from exc
    referenced = {defaults.default_lens, *(rule.lens for rule in defaults.rules)}
    unknown = referenced - set(lenses)
    if unknown:
        raise PackError(f"defaults.yaml refers to unknown lenses: {sorted(unknown)}")
    covered = {rule.role_family for rule in defaults.rules}
    uncovered = set(RoleFamily) - covered
    if uncovered:
        log.warning(
            "role families fall back to the default lens: %s", sorted(u.value for u in uncovered)
        )
    return PackRegistry(packs, lenses, defaults)


@lru_cache
def get_registry() -> PackRegistry:
    return load_registry(find_packs_dir())
