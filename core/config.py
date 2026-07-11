from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ProjectConfig:
    name: str
    lang: str | None = None

    @property
    def book_dir(self) -> Path:
        return ROOT / "asset" / "book" / self.name

    @property
    def outline_path(self) -> Path:
        return ROOT / "asset" / "outline" / f"{self.name}_{self.lang}.json"

    @property
    def script_dir(self) -> Path:
        return ROOT / "asset" / "script" / self.name

    @property
    def output_dir(self) -> Path:
        return ROOT / "asset" / "output" / self.name

    @property
    def voice_dir(self) -> Path:
        return ROOT / "asset" / "voice"

    def book_json_path(self, name: str | None = None) -> Path:
        base = name or self.name
        suffix = f".{self.lang}" if self.lang else ""
        return self.book_dir / f"{base}{suffix}.json"

    def book_epub_path(self, name: str | None = None) -> Path:
        return self.book_dir / f"{name or self.name}.epub"


_projects: dict[str, ProjectConfig] = {}


def get_project_config(project: str) -> ProjectConfig:
    if project not in _projects:
        _projects[project] = ProjectConfig(name=project)
    return _projects[project]
