# Multi-Python-version builds: an experiment

This branch explores what it would take to build ros-humble for more than one
Python version, following up on [RoboStack/robostack.github.io#100](https://github.com/RoboStack/robostack.github.io/issues/100).

## Why this was stuck

vinca currently adds a Python host + run dependency to **every** recipe,
unconditionally, regardless of whether the package has any Python content of
its own. Since that dependency participates in rattler-build's pinned Python
variant, pinning more than one Python version in `conda_build_config.yaml`
would rebuild the **entire distro** once per Python version — including pure
C++ libraries like `rclcpp`, `rmw_*`, `rcutils`, `cyclonedds`, `iceoryx*`,
that have no Python content at all. @traversaro's investigation in the linked
issue found this split empirically (via a post-hoc scan of already-built
package contents): out of ~650 humble packages, ~418 have no Python content,
~97 have compiled Python bindings (mostly `*_msgs` packages), and ~136 are
pure Python.

## What changed

**vinca** ([Tobias-Fischer/vinca#feature/conditional-python-dependency-v2](https://github.com/Tobias-Fischer/vinca/tree/feature/conditional-python-dependency-v2),
pending a PR to RoboStack/vinca):

- `_package_needs_python()`: an ahead-of-time heuristic, computed entirely
  from data vinca already parses out of `package.xml` — no extra network
  fetches, no post-hoc binary inspection needed. A package needs Python if:
  - its build type is `ament_python` (pure Python by construction), or
  - it's a `rosidl_interface_packages` member (msg/srv/action packages always
    get compiled Python bindings via `rosidl_generator_py`, independent of
    what else they declare), or
  - it actually depends (build, exec, run, or test) on a known Python-flavored
    package name (`rclpy`, `pybind11`, `python_cmake_module`,
    `ament_cmake_python`), or on any rosdep key containing "python" or
    starting with "pybind" (catches the `python3-*`/`python-*` naming
    convention).

  Deliberately conservative toward **false positives**: getting this wrong in
  the "needs Python" direction just costs an unnecessary rebuild; getting it
  wrong the other way silently ships a stale/missing artifact for the Python
  versions it wasn't rebuilt for. `buildtool_depend`/`buildtool_export_depend`
  are deliberately *not* scanned (that tag means "a tool needed to invoke the
  build", never "this package's own artifact has Python content" — e.g.
  `rclcpp` declares `<buildtool_depend>python3</buildtool_depend>` purely so
  `ament_cmake_gen_version_h` can run a codegen script), and
  `rosidl_default_generators`/`rosidl_generator_py` were dropped from the
  marker list after finding `rclcpp` depends on the former as a *test-only*
  dependency (for `test_msgs`, unrelated to `rclcpp`'s own content) — the
  `rosidl_interface_packages` group-membership check is the precise signal
  for that case.
- The build-time-only Python every `ament_cmake` recipe still needs (ament's
  own CMake tooling shells out to Python for boilerplate regardless of the
  package's content) is kept, but pinned to the single `python_min` version
  via Jinja rather than left as a bare `"python"` — confirmed via
  `rattler-build build --render-only` that a fully-resolved version
  constraint like this doesn't participate in the variant/`used_vars` scan
  (one build variant either way), while a bare `"python"` produces one
  variant per pinned Python version.
- `build_ament_cmake.sh.in` routes the C/C++ compiler through `sccache` when
  present (a no-op otherwise), and falls back to computing a standard
  `lib/pythonX.Y/site-packages` path when `$SP_DIR` is unset (rattler-build
  only sets it when Python is an actual host dependency, but a handful of
  packages — e.g. `ament_cmake_test` — call `ament_python_install_package()`
  in their own CMakeLists for some small internal helper without declaring a
  Python dependency in `package.xml` at all).

**ros-humble** (this branch):

- `conda_build_config.yaml`: `python`'s `[not emscripten]` entry changed from
  a single pinned version to a real 3-entry matrix (3.11, 3.12, 3.13); the
  `[emscripten]` entry is untouched. Note the build-string glob differs by
  version — conda-forge only started tagging the build string with the minor
  version (`*_cp313`, to disambiguate from the free-threaded `*_cp313t`
  variant) starting with 3.13; 3.11/3.12 still publish under the older
  `*_cpython` suffix (matching this repo's existing convention for the
  single 3.12 pin it replaces).
- `pixi.toml`: added `sccache` as a dependency and `--no-build-id` to the
  `build` task (required for `sccache`/`ccache` to actually get cache hits,
  since both are sensitive to the timestamped build-directory paths
  rattler-build uses by default), added a `sccache-stats` task, and pointed
  the `vinca` pypi-dependency at the fork branch above pending its own PR.

## What was verified

Rather than trying to build the full ~900-package distro, this was validated
against a representative 133-package subset (`std_msgs`, `example_interfaces`,
`rclcpp`, `rclpy`, `demo_nodes_cpp`, `demo_nodes_py`, `launch`, `ros2cli`,
`ros2topic`, plus their transitive closure — deliberately spanning all three
of the categories above), osx-arm64 only, built locally end-to-end:

- **77 packages built exactly once** regardless of the 3-version matrix
  (`rclcpp`, `rmw_*`, `rcutils`, `cyclonedds`, `iceoryx*`, `fastcdr`,
  `demo_nodes_cpp`, `gtest`/`gmock`-vendor, `rosidl_default_generators`, ...).
- **56 packages built 3×**, once per Python version (all `*_msgs` packages,
  `rclpy`, `launch*`, `ros2cli`, `ros2topic`, `demo_nodes_py`, the `ament_*`
  lint tools, `rosidl_adapter`/`cli`/`parser`/`generator_*`, `pybind11_vendor`,
  and — as an accepted false positive — `fastrtps`, which declares a
  `buildtool_depend` mix that the heuristic reads as genuinely Python-flavored).
- 245 total build artifacts (77×1 + 56×3 = 245), exactly matching the
  classification with zero exceptions.
- `sccache` measurably reuses compiled objects across Python-version rebuilds
  of the same package. Real wall-clock timings, isolated single-recipe
  rebuilds (`rattler-build build --recipe ...`, same command each time, no
  `--skip-existing` so all 3 Python variants are genuinely rebuilt):

  **`std_msgs`** — a small message package, mostly CMake configure/rosidl
  codegen rather than compilation:

  | Scenario | py3.11 | py3.12 | py3.13 |
  |---|---|---|---|
  | No sccache (fresh each time) | 55s | 48s | 37s |
  | With sccache (cold → warm within one run) | 47s | 35s | 28s |

  **`fastrtps`** — a large, compile-heavy vendored C++ library (also
  Python-classified, see the accepted-false-positive note above), same
  methodology:

  | Scenario | py3.11 | py3.12 | py3.13 |
  |---|---|---|---|
  | No sccache (fresh each time) | 57s | 58s | 61s |
  | With sccache (cold → warm within one run) | 66s | 22s | 22s |

  confirmed via `sccache --show-stats` on that run: 645 compile requests,
  430 cache hits (66.67%). The first variant pays a small cache-write
  penalty (66s vs. 57s cold), but the second and third variants — which
  reuse most of the same compiled objects across the Python-version-specific
  bindings layer — are **~2.6-2.8× faster** (58s→22s, 61s→22s) than a fresh,
  uncached rebuild. This is the realistic payoff for the packages this whole
  change causes to be rebuilt more than once: the benefit scales with how
  much actual C/C++ compilation a package does, and is much more pronounced
  for something like `fastrtps` than for a small message package like
  `std_msgs`, where CMake configure/codegen overhead dominates instead.

## Open questions for reviewers

- **CI cost**: flipping the *entire* distro's `python:` pin to this 3-version
  matrix would 3× the build time for whatever fraction of the ~900 packages
  the heuristic classifies as Python-dependent (roughly 40% on this subset,
  though the full-distro fraction hasn't been measured). Worth deciding
  deliberately rather than as a side effect of merging the vinca change —
  the vinca change alone is harmless with a single-version pin (it just stops
  adding a spurious Python dependency to non-Python packages).
- **`ament_cmake_test`-shaped edge cases**: any package that calls
  `ament_python_install_package()` internally without declaring a Python
  dependency in `package.xml` builds its Python helper once, at whichever
  Python version happens to be `python_min` — a downstream package importing
  that helper while running under a *different* active Python version could
  see a site-packages path mismatch. Not exercised in this validation run
  (`--test skip` throughout); worth flagging for anyone relying on it in
  production.
- Is 3 versions (3.11/3.12/3.13) the right starting matrix, or should it
  track conda-forge's currently-supported set more closely (e.g. include
  3.14)?
