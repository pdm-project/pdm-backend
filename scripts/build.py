"""
This is a simple script to call pdm-pep517's backend apis to make release artifacts.
"""
import logging

import pdm.backend as api

logger = logging.getLogger("pdm.backend")
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def main() -> None:
    api.build_sdist("dist")
    api.build_wheel("dist")
    api.build_editable("dist")


if __name__ == "__main__":
    main()
