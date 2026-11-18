"""Manuale d'uso di Tana (Read the Docs): Sphinx + MyST, come il manuale del tema."""

import tomllib
from pathlib import Path

_pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
release = _pyproject["project"]["version"]
version = ".".join(release.split(".")[:2])

project = "Tana – Manuale d'uso"
copyright = "AGESCI Campania"
author = "AGESCI Campania"
language = "it"

extensions = ["myst_parser", "sphinx_design"]
source_suffix = {".md": "markdown"}
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]

html_theme = "furo"
html_title = f"Tana {release} – Manuale d'uso"
html_static_path = ["_static"]
html_logo = "../static/tana/img/logo/lupo-base-aiello.svg"
html_favicon = "../static/tana/img/logo/lupo-base-aiello.svg"
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#076633",
        "color-brand-content": "#076633",
    },
    "dark_css_variables": {
        "color-brand-primary": "#80c077",
        "color-brand-content": "#80c077",
    },
}

myst_enable_extensions = ["colon_fence", "deflist", "substitution"]
myst_substitutions = {"release": release}
myst_heading_anchors = 3

latex_documents = [("index", "tana-manuale.tex", project, author, "manual")]
