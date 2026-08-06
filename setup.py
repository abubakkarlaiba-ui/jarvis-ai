"""JARVIS — setuptools packaging."""

from pathlib import Path

from setuptools import find_packages, setup

root = Path(__file__).resolve().parent

long_description = ""
readme = root / "README.md"
if readme.exists():
    long_description = readme.read_text(encoding="utf-8")

requirements = []
req_file = root / "requirements.txt"
if req_file.exists():
    requirements = [
        line.strip()
        for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="jarvis-ai",
    version="2.0.0",
    author="JARVIS Team",
    description="J.A.R.V.I.S. — Just A Rather Very Intelligent System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "jarvis=jarvis.__main__:main",
        ],
    },
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "jarvis": [
            "static/**/*",
            "templates/**/*",
            "data/**/*",
        ],
    },
)
