#!/usr/bin/env python3

"""
Setup Lidl Plus api
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="lidl-plus",
    version="0.4.0",
    author="Andre Basche",
    description="Fetch receipts and more from Lidl Plus",
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "GitHub": "https://github.com/yagueto/lidl-plus",
        "Original project": "https://github.com/Andre0512/lidl-plus",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    platforms="any",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28.1,<3",
    ],
    extras_require={
        "auth": [
            "selenium>=4.10.0,<5",
        ]
    },
    entry_points={
        "console_scripts": [
            "lidl-plus = lidlplus.__main__:start",
        ]
    },
)
