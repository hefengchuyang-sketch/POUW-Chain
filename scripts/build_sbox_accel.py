"""Build helper for optional S-Box C accelerator.

Usage:
    py -3 scripts/build_sbox_accel.py build_ext --inplace

If build toolchain is missing, the project will still work with pure Python fallback.
"""

from setuptools import Extension, setup


setup(
    name="pouw-sbox-accel",
    version="0.1.0",
    ext_modules=[
        Extension(
            "core._sbox_accel",
            ["core/_sbox_accel.c"],
            extra_compile_args=["/O2"] if __import__("os").name == "nt" else ["-O3"],
        )
    ],
)
