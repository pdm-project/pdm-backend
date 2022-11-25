import os


def pdm_build_initialize(context):
    context.ensure_build_dir()
    os.makedirs(os.path.join(context.build_dir, "my_package"))
    with open(os.path.join(context.build_dir, "my_package/version.txt"), "w") as f:
        f.write(context.config.metadata["version"])
