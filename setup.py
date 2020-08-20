import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cisipy", # Replace with your own username
    version="0.0.4",
    author="Shahul Alam",
    author_email="alam.shahul@gmail.com",
    description="Compressed imaging transcriptomics in Python.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alam-shahul/cisipy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "toml",
        "numpy",
        "scipy",
        "scikit-image",
        "tifffile",
        "nd2reader",
        "python-bioformats",
        "pyimagej",
        "starfish",
        "sympy<=1.5.1",
        "spams"
    ],
    package_data={
        "preprocessing": ["Fuse.ijm", "segment.cppipe"],
    },
    python_requires='>=3.7',
)
