import os

from pdm.pep517.wheel import WheelBuilder


def build(src, dst):
    meta = WheelBuilder(src).meta
    os.makedirs(os.path.join(dst, "my_package"))
    with open(os.path.join(dst, "my_package/version.foo"), "w") as f:
        f.write(meta.version)
