"""Setup configuration for FinTrack."""
from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="FinTrack",
    version="1.2.0",
    author="Aron Fredriksson",
    author_email="arofre903@gmail.com",
    description="A robust portfolio tracker with multi-currency support and short selling",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/arofre/FinTrack",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.3.0",
        "yfinance>=0.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "twine>=4.0.0",
            "build>=0.8.0",
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/arofre/FinTrack/issues",
        "Source": "https://github.com/arofre/FinTrack",
        "Documentation": "https://github.com/arofre/FinTrack/wiki",
    },
    include_package_data=True,
    zip_safe=False,
)
