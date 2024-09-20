import email
import os
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

import pdm.backend as api
from pdm.backend.wheel import WheelBuilder
from tests.testutils import get_tarball_names, get_wheel_names

pytestmark = pytest.mark.usefixtures("fixture_project")


@pytest.mark.parametrize("name", ["demo-module"])
def test_build_single_module(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert api.get_requires_for_build_sdist() == []
    assert api.get_requires_for_build_wheel() == []
    assert sdist_name == "demo_module-0.1.0.tar.gz"
    assert wheel_name == "demo_module-0.1.0-py3-none-any.whl"
    tar_names = get_tarball_names(dist / sdist_name)
    for name in [
        "foo_module.py",
        "bar_module.py",
        "LICENSE",
        "pyproject.toml",
        "PKG-INFO",
        "README.md",
    ]:
        assert f"demo_module-0.1.0/{name}" in tar_names

    zip_names = get_wheel_names(dist / wheel_name)
    for name in ["foo_module.py", "bar_module.py"]:
        assert name in zip_names

    for name in ("pyproject.toml", "LICENSE"):
        assert name not in zip_names

    assert "demo_module-0.1.0.dist-info/licenses/LICENSE" in zip_names


@pytest.mark.parametrize("name", ["demo-module"])
def test_build_single_module_with_build_number(dist: Path) -> None:
    build_number = "20231241"
    wheel_name = api.build_wheel(
        dist.as_posix(),
        config_settings={"--build-number": build_number},
    )
    assert wheel_name == f"demo_module-0.1.0-{build_number}-py3-none-any.whl"
    with zipfile.ZipFile(dist / wheel_name) as zf:
        wheel_metadata = email.message_from_bytes(
            zf.read("demo_module-0.1.0.dist-info/WHEEL")
        )
        assert wheel_metadata["Build"] == build_number


@pytest.mark.parametrize("name", ["demo-module"])
def test_build_single_module_without_build_number(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    assert wheel_name == "demo_module-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(dist / wheel_name) as zf:
        wheel_metadata = email.message_from_bytes(
            zf.read("demo_module-0.1.0.dist-info/WHEEL")
        )
        assert "Build" not in wheel_metadata


@pytest.mark.parametrize("name", ["demo-package"])
def test_build_package(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert sdist_name == "demo_package-0.1.0.tar.gz"
    assert wheel_name == "demo_package-0.1.0-py2.py3-none-any.whl"

    tar_names = get_tarball_names(dist / sdist_name)
    assert "demo_package-0.1.0/my_package/__init__.py" in tar_names
    assert "demo_package-0.1.0/my_package/data.json" in tar_names
    assert "demo_package-0.1.0/single_module.py" not in tar_names
    assert "demo_package-0.1.0/data_out.json" in tar_names

    zip_names = get_wheel_names(dist / wheel_name)
    assert "my_package/__init__.py" in zip_names
    assert "my_package/data.json" in zip_names
    assert "single_module.py" not in zip_names
    assert "data_out.json" not in zip_names


@pytest.mark.parametrize("name", ["demo-src-package"])
def test_build_src_package(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert sdist_name == "demo_package-0.1.0.tar.gz"
    assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

    tar_names = get_tarball_names(dist / sdist_name)
    zip_names = get_wheel_names(dist / wheel_name)
    assert "demo_package-0.1.0/src/my_package/__init__.py" in tar_names
    assert "demo_package-0.1.0/src/my_package/data.json" in tar_names

    assert "my_package/__init__.py" in zip_names
    assert "my_package/data.json" in zip_names


@pytest.mark.parametrize("name", ["demo-package-include"])
def test_build_package_include(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert sdist_name == "demo_package-0.1.0.tar.gz"
    assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

    tar_names = get_tarball_names(dist / sdist_name)

    assert "demo_package-0.1.0/my_package/__init__.py" in tar_names
    assert "demo_package-0.1.0/my_package/data.json" not in tar_names
    assert "demo_package-0.1.0/requirements.txt" in tar_names
    assert "demo_package-0.1.0/data_out.json" in tar_names

    with zipfile.ZipFile(dist / wheel_name) as zf:
        zip_names = zf.namelist()
        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" not in zip_names
        assert "requirements.txt" in zip_names
        assert "data_out.json" in zip_names
        assert "demo_package-0.1.0.data/scripts/my_script.sh" in zip_names
        if os.name != "nt":
            info = zf.getinfo("demo_package-0.1.0.data/scripts/my_script.sh")
            filemode = info.external_attr >> 16
            assert filemode & 0o111


@pytest.mark.parametrize("name", ["demo-package-include"])
def test_build_package_data_relative(dist: Path, fixture_project: Path) -> None:
    from pdm.backend.config import tomli_w, tomllib

    with open(fixture_project / "pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)
    pyproject["tool"]["pdm"]["build"]["wheel-data"]["scripts"] = [
        {"path": "scripts/**/*", "relative-to": "scripts/"}
    ]
    with open(fixture_project / "pyproject.toml", "wb") as fp:
        tomli_w.dump(pyproject, fp)
    wheel_name = api.build_wheel(dist.as_posix())

    with zipfile.ZipFile(dist / wheel_name) as zf:
        zip_names = zf.namelist()
        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" not in zip_names
        assert "requirements.txt" in zip_names
        assert "data_out.json" in zip_names
        assert "demo_package-0.1.0.data/scripts/data/my_script.sh" in zip_names
        if os.name != "nt":
            info = zf.getinfo("demo_package-0.1.0.data/scripts/data/my_script.sh")
            filemode = info.external_attr >> 16
            assert filemode & 0o111


@pytest.mark.parametrize("name", ["demo-pep420-package"])
def test_namespace_package_by_include(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert sdist_name == "demo_package-0.1.0.tar.gz"
    assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

    tar_names = get_tarball_names(dist / sdist_name)
    zip_names = get_wheel_names(dist / wheel_name)
    assert "demo_package-0.1.0/foo/my_package/__init__.py" in tar_names
    assert "demo_package-0.1.0/foo/my_package/data.json" in tar_names

    assert "foo/my_package/__init__.py" in zip_names
    assert "foo/my_package/data.json" in zip_names


@pytest.mark.parametrize("name", ["demo-explicit-package-dir"])
def test_build_explicit_package_dir(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert sdist_name == "demo_package-0.1.0.tar.gz"
    assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

    tar_names = get_tarball_names(dist / sdist_name)
    zip_names = get_wheel_names(dist / wheel_name)
    assert "demo_package-0.1.0/foo/my_package/__init__.py" in tar_names
    assert "demo_package-0.1.0/foo/my_package/data.json" in tar_names

    assert "my_package/__init__.py" in zip_names
    assert "my_package/data.json" in zip_names


@pytest.mark.parametrize("name", ["demo-metadata-test"])
def test_demo_metadata_test__sdist__pkg_info(
    dist: Path, name: str, tmp_path: Path
) -> None:
    filename = api.build_sdist(dist.as_posix())
    with tarfile.open(dist / filename) as archive:
        archive.extractall(tmp_path)
    pkg_info_path = next(tmp_path.rglob("PKG-INFO"))
    parsed_pkg_info = email.message_from_bytes(pkg_info_path.read_bytes())
    assert dict(parsed_pkg_info) == {
        "Author-Email": '"Corporation, Inc." <corporation@example.com>, Example '
        "<example@example.com>",
        "Description-Content-Type": "text/markdown",
        "License-Expression": "MIT",
        "Metadata-Version": "2.4",
        "Name": name,
        "Requires-Python": ">=3.8",
        "Version": "3.2.1",
    }


@pytest.mark.parametrize("name", ["demo-package"])
def test_prepare_metadata(dist: Path) -> None:
    dist_info = api.prepare_metadata_for_build_wheel(dist.as_posix())
    assert dist_info == "demo_package-0.1.0.dist-info"
    for filename in ("WHEEL", "METADATA"):
        assert (dist / dist_info / filename).is_file()


@pytest.mark.parametrize("name", ["demo-package"])
def test_build_wheel_metadata_identical(dist: Path) -> None:
    dist_info = api.prepare_metadata_for_build_wheel(dist.as_posix())
    (dist / dist_info / "other.txt").write_text("foo")

    wheel_name = api.build_wheel(
        dist.as_posix(), metadata_directory=str(dist / dist_info)
    )

    with zipfile.ZipFile(dist / wheel_name) as wheel:
        assert f"{dist_info}/other.txt" in wheel.namelist()
        assert wheel.read(f"{dist_info}/other.txt") == b"foo"


@pytest.mark.parametrize("name", ["demo-src-pymodule"])
def test_build_package_with_modules_in_src(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())

    tar_names = get_tarball_names(dist / sdist_name)
    assert "demo_module-0.1.0/src/foo_module.py" in tar_names

    zip_names = get_wheel_names(dist / wheel_name)
    assert "foo_module.py" in zip_names


@pytest.mark.parametrize("name", ["demo-cextension"])
def test_build_with_cextension(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())
    assert api.get_requires_for_build_sdist() == []
    assert api.get_requires_for_build_wheel() == ["setuptools>=40.8.0"]

    zip_names = get_wheel_names(dist / wheel_name)
    assert "my_package/__init__.py" in zip_names
    assert (
        "my_package/hellomodule.c" not in zip_names
    ), "Not collect c files while building wheel"
    extension_suffix = ".pyd" if sys.platform == "win32" else ".so"
    assert any(name.endswith(extension_suffix) for name in zip_names)

    tar_names = get_tarball_names(dist / sdist_name)
    assert "demo_package-0.1.0/my_package/__init__.py" in tar_names
    assert (
        "demo_package-0.1.0/my_package/hellomodule.c" in tar_names
    ), "Collect c files while building sdist"
    assert not any(
        path.startswith("build") for path in tar_names
    ), 'Not collect c files in temporary directory "./build"'


@pytest.mark.parametrize("name", ["demo-cextension-in-src"])
def test_build_with_cextension_in_src(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())

    zip_names = get_wheel_names(dist / wheel_name)
    assert "my_package/__init__.py" in zip_names
    assert (
        "my_package/hellomodule.c" not in zip_names
    ), "Not collect c files while building wheel"
    extension_suffix = ".pyd" if sys.platform == "win32" else ".so"
    assert any(name.endswith(extension_suffix) for name in zip_names)

    tar_names = get_tarball_names(dist / sdist_name)
    assert "demo_package-0.1.0/src/my_package/__init__.py" in tar_names
    assert (
        "demo_package-0.1.0/src/my_package/hellomodule.c" in tar_names
    ), "Collect c files while building sdist"
    assert not any(
        path.startswith("build") for path in tar_names
    ), 'Not collect c files in temporary directory "./build"'


@pytest.mark.parametrize("name", ["demo-package"])
def test_build_editable(dist: Path, fixture_project: Path) -> None:
    wheel_name = api.build_editable(dist.as_posix())
    assert api.get_requires_for_build_editable() == []
    with zipfile.ZipFile(dist / wheel_name) as zf:
        namelist = zf.namelist()
        assert "demo_package.pth" in namelist
        assert "_editable_impl_demo_package.py" in namelist
        assert "demo_package-0.1.0.dist-info/licenses/LICENSE" in namelist

        metadata = email.message_from_bytes(
            zf.read("demo_package-0.1.0.dist-info/METADATA")
        )
        assert "editables" in metadata.get_all("Requires-Dist", [])

        pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
        assert pth_content == "import _editable_impl_demo_package"

        proxy_module = zf.read("_editable_impl_demo_package.py").decode("utf-8").strip()
        assert proxy_module == (
            "from editables.redirector import RedirectingFinder as F\n"
            "F.install()\n"
            "F.map_module('my_package', {!r})".format(
                str((fixture_project / "my_package" / "__init__.py").resolve())
            )
        )


@pytest.mark.parametrize("name", ["demo-src-package-include"])
def test_build_editable_src(dist: Path, fixture_project: Path) -> None:
    wheel_name = api.build_editable(dist.as_posix())

    with zipfile.ZipFile(dist / wheel_name) as zf:
        namelist = zf.namelist()
        assert "demo_package.pth" in namelist
        assert "_editable_impl_demo_package.py" in namelist
        assert (
            "my_package/data.json" not in namelist
        ), "data files in proxy modules are excluded"
        assert "data_out.json" in namelist

        pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
        assert pth_content == "import _editable_impl_demo_package"

        proxy_module = zf.read("_editable_impl_demo_package.py").decode("utf-8").strip()
        assert proxy_module == (
            "from editables.redirector import RedirectingFinder as F\n"
            "F.install()\n"
            "F.map_module('my_package', {!r})".format(
                str((fixture_project / "sub" / "my_package" / "__init__.py").resolve())
            )
        )


@pytest.mark.parametrize("name", ["demo-pep420-package"])
def test_build_editable_pep420(dist: Path, fixture_project: Path) -> None:
    with pytest.warns(UserWarning) as recorded:
        wheel_name = api.build_editable(dist.as_posix())

    assert len(recorded) == 1
    assert str(recorded.pop().message).startswith("editables backend is not available")

    with zipfile.ZipFile(dist / wheel_name) as zf:
        namelist = zf.namelist()
        assert "demo_package.pth" in namelist
        assert "__editables_demo_package.py" not in namelist

        metadata = email.message_from_bytes(
            zf.read("demo_package-0.1.0.dist-info/METADATA")
        )
        assert "editables" not in metadata.get_all("Requires-Dist", [])

        pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
        assert pth_content == str(fixture_project.resolve())


@pytest.mark.parametrize("name", ["demo-package"])
def test_prepare_metadata_for_editable(dist: Path) -> None:
    dist_info = api.prepare_metadata_for_build_editable(dist.as_posix())
    assert dist_info == "demo_package-0.1.0.dist-info"
    with (dist / dist_info / "METADATA").open("rb") as metadata:
        deps = email.message_from_binary_file(metadata).get_all("Requires-Dist")
    assert "editables" in deps


@pytest.mark.parametrize("name", ["demo-purelib-with-build"])
def test_build_purelib_project_with_build(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

    with zipfile.ZipFile(dist / wheel_name) as zf:
        wheel_metadata = email.message_from_bytes(
            zf.read("demo_package-0.1.0.dist-info/WHEEL")
        )
        version = zf.read("my_package/version.txt").decode("utf-8").strip()
        assert version == "0.1.0"
        assert wheel_metadata["Root-Is-Purelib"] == "true"


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Check file mode on Unix only"
)
@pytest.mark.parametrize("name", ["demo-package"])
def test_build_wheel_preserve_permission(dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    with zipfile.ZipFile(dist / wheel_name) as zf:
        info = zf.getinfo("my_package/executable")
        filemode = info.external_attr >> 16
        assert filemode & 0o111


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_build_wheel_write_version_to_file(fixture_project: Path, dist) -> None:
    builder = WheelBuilder(fixture_project)
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "scm",
        "write_to": "foo/__version__.py",
    }
    with builder:
        wheel_name = builder.build(dist)
        with zipfile.ZipFile(wheel_name) as zf:
            version = zf.read("foo/__version__.py").decode("utf-8").strip()
            assert version == "0.1.0"


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_build_wheel_write_version_to_file_template(
    fixture_project: Path, dist: Path
) -> None:
    builder = WheelBuilder(fixture_project)
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "scm",
        "write_to": "foo/__version__.py",
        "write_template": '__version__ = "{}"\n',
    }
    with builder:
        wheel_name = builder.build(dist)
        with zipfile.ZipFile(wheel_name) as zf:
            version = zf.read("foo/__version__.py").decode("utf-8").strip()
            assert version == '__version__ = "0.1.0"'


@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_override_scm_version_via_env_var(
    dist: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PDM_BUILD_SCM_VERSION", "1.0.0")
    wheel_name = api.build_wheel(dist.as_posix())
    assert wheel_name == "foo-1.0.0-py3-none-any.whl"


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_build_wheel_custom_version_format(fixture_project: Path, dist) -> None:
    builder = WheelBuilder(fixture_project)
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "scm",
        "version_format": "version:format_version",
    }
    with builder:
        wheel = builder.build(dist)
        assert wheel.name == "foo-0.1.0rc0-py3-none-any.whl"


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize("getter", ["get_version:run", "get_version:run()"])
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_get_version_from_call(fixture_project: Path, getter: str, dist: Path) -> None:
    builder = WheelBuilder(fixture_project)
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "call",
        "write_to": "foo/__version__.py",
        "getter": getter,
    }
    fixture_project.joinpath("get_version.py").write_text("def run(): return '1.1.1'\n")
    with builder:
        wheel_name = builder.build(dist)
        assert wheel_name.name == "foo-1.1.1-py3-none-any.whl"
        with zipfile.ZipFile(wheel_name) as zf:
            version = zf.read("foo/__version__.py").decode("utf-8").strip()
        assert version == "1.1.1"


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize(
    "settings, cleanup", [("true", False), ("false", True), ("0", True), ("1", False)]
)
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_clean_not_called_if_envset(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings: str,
    cleanup: bool,
    dist: Path,
) -> None:
    monkeypatch.setenv("PDM_BUILD_NO_CLEAN", settings)
    builder = WheelBuilder(fixture_project)
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "scm",
        "write_to": "foo/__version__.py",
    }

    test_file = fixture_project / ".pdm-build" / "testfile"
    os.makedirs(fixture_project / ".pdm-build", exist_ok=True)
    test_file.touch()
    assert os.path.exists(test_file)

    with builder:
        builder.build(dist)
        if cleanup:
            assert not os.path.exists(test_file)
        else:
            assert os.path.exists(test_file)


@pytest.mark.usefixtures("scm")
@pytest.mark.parametrize(
    "settings, cleanup", [("", False), (True, False), (None, False)]
)
@pytest.mark.parametrize("name", ["demo-using-scm"])
def test_clean_not_called_if_config_settings_exist(
    fixture_project: Path, settings: bool, cleanup: bool, dist: Path
) -> None:
    builder = WheelBuilder(
        fixture_project, config_settings={"no-clean-build": settings}
    )
    builder.config.data.setdefault("tool", {}).setdefault("pdm", {})["version"] = {
        "source": "scm",
        "write_to": "foo/__version__.py",
    }

    test_file = fixture_project / ".pdm-build" / "testfile"
    os.makedirs(fixture_project / ".pdm-build", exist_ok=True)
    test_file.touch()
    assert os.path.exists(test_file)

    with builder:
        builder.build(dist)
        if cleanup:
            assert not os.path.exists(test_file)
        else:
            assert os.path.exists(test_file)


@pytest.mark.parametrize("name", ["demo-licenses"])
def test_build_wheel_with_license_file(fixture_project: Path, dist: Path) -> None:
    wheel_name = api.build_wheel(dist.as_posix())
    sdist_name = api.build_sdist(dist.as_posix())

    tar_names = get_tarball_names(dist / sdist_name)
    licenses = ["LICENSE", "licenses/LICENSE.MIT.md", "licenses/LICENSE.APACHE.md"]
    for file in licenses:
        assert f"demo_module-0.1.0/{file}" in tar_names

    zip_names = get_wheel_names(dist / wheel_name)
    for file in licenses:
        assert f"demo_module-0.1.0.dist-info/licenses/{file}" in zip_names
