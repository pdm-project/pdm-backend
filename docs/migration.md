# Migrate from pdm-pep517

It is quite easy to migrate from the [pdm-pep517] backend, there are only a few difference between the configurations of the two backends.

## `tool.pdm.build` table

`pdm-pep517` has renamed the `tool.pdm` table to `tool.pdm.build` since 1.0.0. If you are still storing the [build configurations](./build_config.md) directly under `tool.pdm` table, move them under `tool.pdm.build` now. The old table is no longer supported.

=== "Legacy"

    ```toml
    [tool.pdm]
    includes = ["src", "data/*.json"]
    package-dir = "src"
    ```

=== "New"

    ```toml
    [tool.pdm.build]
    includes = ["src", "data/*.json"]
    package-dir = "src"
    ```

## `setup-script`

In `pdm-pep517` you are allowed to call a custom `build` function during the build to add user-generated contents, which is specified by `tool.pdm.build.setup-script` option. However, this option has been dropped in `pdm-backend`, use a custom hook instead, and the custom script can be loaded automatically with the name `pdm_build.py`.

=== "Legacy"

    ```toml
    # pyproject.toml
    [tool.pdm.build]
    run-setuptools = false
    setup-script = "build.py"
    ```
    ```python
    # build.py
    def build(src, dst):
        # add more files to the dst directory
        ...
    ```

=== "New"

    ```toml
    # pyproject.toml
    [tool.pdm.build]
    # Either key is not necessary anymore.
    ```
    ```python
    # pdm_build.py
    def pdm_build_update_files(context, files):
        # add more files to the dst directory
        new_file = do_create_files()
        files["new_file"] = new_file
    ```

And if `run-setuptools` is `true`, `pdm-pep517` will instead generate a `setup.py` file and call the specified script to update the arguments passed to `setup()` function. In `pdm-backend`, this can be also done via custom hook:

=== "Legacy"

    ```toml
    # pyproject.toml
    [tool.pdm.build]
    run-setuptools = true
    setup-script = "build.py"
    ```
    ```python
    # build.py
    def build(setup_kwargs):
        # modify the setup_kwargs
        setup_kwargs['extensions'] = [Extension(...)]
    ```

=== "New"

    ```toml
    # pyproject.toml
    [tool.pdm.build]
    run-setuptools = true
    ```
    ```python
    # pdm_build.py
    def pdm_build_update_setup_kwargs(context, setup_kwargs):
        # modify the setup_kwargs
        setup_kwargs['extensions'] = [Extension(...)]
    ```


That's all, no more changes are required to be made and your project keeps working as before.
