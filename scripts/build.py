"""
This is a simple script to call pdm-pep517's backend apis to make release artifacts.
"""
import argparse
import logging
import os

import pdm.backend as api

logger = logging.getLogger("pdm.backend")
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wheel", action="store_false", dest="wheel")
    parser.add_argument("--no-sdist", action="store_false", dest="sdist")
    parser.add_argument("--no-editable", action="store_false", dest="editable")
    parser.add_argument("path", nargs="?", default=".")
    args = parser.parse_args()
    os.chdir(args.path)
    if args.sdist:
        api.build_sdist("dist")
    if args.wheel:
        api.build_wheel("dist")
    if args.editable:
        api.build_editable("dist")


if __name__ == "__main__":
    main()
