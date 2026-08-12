"""Created on 2026-08-12.

the color palette of a reel site

@author: wf
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from basemkit.yamlable import lod_storable


@dataclass
class Palette:
    """One Material palette schema.

    The eight values are the ones the ColorSchema of ngwidgets carries,
    so a reel site looks like the other BITPlan applications without
    depending on the library.
    """

    primary: str = "#5898d4"
    secondary: str = "#26a69a"
    accent: str = "#9c27b0"
    dark: str = "#1d1d1d"
    positive: str = "#21ba45"
    negative: str = "#c10015"
    info: str = "#31ccec"
    warning: str = "#f2c037"

    def as_css(self) -> str:
        """Render the palette as CSS custom properties.

        Returns:
            the eight values as --name: value declarations.
        """
        css = "\n".join(
            f"  --{name}: {value};" for name, value in self.__dict__.items()
        )
        return css


@lod_storable
class Palettes:
    """The palette schemas a reel site may name."""

    palettes: Dict[str, Palette] = field(default_factory=dict)

    @classmethod
    def resource_path(cls) -> Path:
        """Path of the palettes shipped with the package."""
        path = Path(__file__).parent / "resources" / "palettes.yaml"
        return path

    @classmethod
    def of_resource(cls) -> "Palettes":
        """Load the palettes shipped with the package."""
        palettes = cls.load_from_yaml_file(str(cls.resource_path()))
        return palettes

    def by_name(self, name: str) -> Palette:
        """Get the palette of the given name.

        Args:
            name: name of a Material palette schema e.g. blue_grey.

        Returns:
            the palette.

        Raises:
            ValueError: if no palette of that name is shipped.
        """
        palette = self.palettes.get(name)
        if palette is None:
            available = ", ".join(sorted(self.palettes.keys()))
            raise ValueError(f"unknown palette {name} - available: {available}")
        return palette
