import distutils
import os
import re
import sys
import urllib.parse as urllib_parse
import urllib.request as urllib_request
import warnings
from contextlib import contextmanager
from fnmatch import fnmatchcase
from sysconfig import get_config_var
from typing import Iterable, List, Optional, Sequence

from ._vendor import packaging


def safe_name(name: str) -> str:
    """Convert an arbitrary string to a standard distribution name

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.
    """
    return re.sub("[^A-Za-z0-9.]+", "-", name)


def safe_version(version):
    """
    Convert an arbitrary string to a standard version string
    """
    try:
        # normalize the version
        return str(packaging.version.Version(version))
    except packaging.version.InvalidVersion:
        version = version.replace(" ", ".")
        return re.sub("[^A-Za-z0-9.]+", "-", version)


def to_filename(name):
    """Convert a project or version name to its filename-escaped form

    Any '-' characters are currently replaced with '_'.
    """
    return name.replace("-", "_")


def find_packages_iter(
    where: os.PathLike = ".",
    exclude: Iterable[str] = (),
    include: Iterable[str] = ("*",),
) -> Iterable[str]:
    """
    All the packages found in 'where' that pass the 'include' filter, but
    not the 'exclude' filter.
    """

    def _build_filter(patterns):
        """
        Given a list of patterns, return a callable that will be true only if
        the input matches at least one of the patterns.
        """
        return lambda name: any(fnmatchcase(name, pat=pat) for pat in patterns)

    exclude, include = _build_filter(exclude), _build_filter(include)
    for root, dirs, files in os.walk(where, followlinks=True):
        # Copy dirs to iterate over it, then empty dirs.
        all_dirs = dirs[:]
        dirs[:] = []

        for dir in all_dirs:
            full_path = os.path.join(root, dir)
            rel_path = os.path.relpath(full_path, where)
            package = rel_path.replace(os.path.sep, ".")
            # Skip directory trees that are not valid packages
            if "." in dir or not os.path.isfile(os.path.join(full_path, "__init__.py")):
                continue

            # Should this package be included?
            if include(package) and not exclude(package):
                yield package

            # Keep searching subdirectories, as there may be more packages
            # down there, even if the parent was excluded.
            dirs.append(dir)


@contextmanager
def cd(path: str):
    _old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(_old_cwd)


def normalize_path(filename: os.PathLike) -> str:
    """Normalize a file/dir name for comparison purposes"""
    filename = os.path.abspath(filename) if sys.platform == "cygwin" else filename
    return os.path.normcase(os.path.realpath(os.path.normpath(filename)))


def path_to_url(path: str) -> str:
    """
    Convert a path to a file: URL.  The path will be made absolute and have
    quoted path parts.
    """
    path = os.path.normpath(os.path.abspath(path))
    url = urllib_parse.urljoin("file:", urllib_request.pathname2url(path))
    return url


_SETUPTOOLS_SHIM = (
    "import sys, setuptools, tokenize; sys.argv[0] = {0!r}; __file__={0!r};"
    "f=getattr(tokenize, 'open', open)(__file__);"
    "code=f.read().replace('\\r\\n', '\\n');"
    "f.close();"
    "exec(compile(code, __file__, 'exec'))"
)


def make_setuptools_shim_args(
    setup_py_path,  # type: str
    global_options=None,  # type: Sequence[str]
    no_user_config=False,  # type: bool
    unbuffered_output=False,  # type: bool
):
    # type: (...) -> List[str]
    """
    Get setuptools command arguments with shim wrapped setup file invocation.

    :param setup_py_path: The path to setup.py to be wrapped.
    :param global_options: Additional global options.
    :param no_user_config: If True, disables personal user configuration.
    :param unbuffered_output: If True, adds the unbuffered switch to the
     argument list.
    """
    args = [sys.executable]
    if unbuffered_output:
        args += ["-u"]
    args += ["-c", _SETUPTOOLS_SHIM.format(setup_py_path)]
    if global_options:
        args += global_options
    if no_user_config:
        args += ["--no-user-cfg"]
    return args


def get_platform() -> str:
    """Return our platform name 'win32', 'linux_x86_64'"""
    result = distutils.util.get_platform().replace(".", "_").replace("-", "_")
    if result == "linux_x86_64" and sys.maxsize == 2147483647:
        # pip pull request #3497
        result = "linux_i686"
    return result


def get_flag(var, fallback, expected=True, warn=True):
    """Use a fallback value for determining SOABI flags if the needed config
    var is unset or unavailable."""
    val = get_config_var(var)
    if val is None:
        if warn:
            warnings.warn(
                "Config variable '{0}' is unset, Python ABI tag may "
                "be incorrect".format(var),
                RuntimeWarning,
                2,
            )
        return fallback
    return val == expected


def get_abi_tag() -> str:
    """Return the ABI tag based on SOABI (if available) or emulate SOABI
    (CPython 2, PyPy).
    A replacement for pip._internal.models.pep425tags:get_abi_tag()
    """

    from ._vendor.packaging.tags import interpreter_name as get_abbr_impl

    soabi = get_config_var("SOABI")
    impl = get_abbr_impl()
    abi = None  # type: Optional[str]
    python_version = sys.version_info[:2]

    if not soabi and impl in {"cp", "pp"} and hasattr(sys, "maxunicode"):
        d = ""
        m = ""
        u = ""
        is_cpython = impl == "cp"
        if get_flag("Py_DEBUG", lambda: hasattr(sys, "gettotalrefcount"), warn=False):
            d = "d"
        if python_version < (3, 8) and get_flag(
            "WITH_PYMALLOC", lambda: is_cpython, warn=False
        ):
            m = "m"
        if python_version < (3, 3) and get_flag(
            "Py_UNICODE_SIZE",
            lambda: sys.maxunicode == 0x10FFFF,
            expected=4,
            warn=False,
        ):
            u = "u"
        abi = "%s%s%s%s%s" % (impl, "".join(map(str, python_version)), d, m, u)
    elif soabi and soabi.startswith("cpython-"):
        abi = "cp" + soabi.split("-")[1]
    elif soabi:
        abi = soabi.replace(".", "_").replace("-", "_")

    return abi
