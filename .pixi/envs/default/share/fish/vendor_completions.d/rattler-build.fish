# Print an optspec for argparse to handle cmd's options that are independent of any subcommand.
function __fish_rattler_build_global_optspecs
	string join \n v/verbose q/quiet log-style= wrap-log-lines= config-file= color= h/help V/version
end

function __fish_rattler_build_needs_command
	# Figure out if the current invocation already has a command.
	set -l cmd (commandline -opc)
	set -e cmd[1]
	argparse -s (__fish_rattler_build_global_optspecs) -- $cmd 2>/dev/null
	or return
	if set -q argv[1]
		# Also print the command, so this can be used to figure out what it is.
		echo $argv[1]
		return 1
	end
	return 0
end

function __fish_rattler_build_using_subcommand
	set -l cmd (__fish_rattler_build_needs_command)
	test -z "$cmd"
	and return 1
	contains -- $cmd[1] $argv
end

complete -c rattler-build -n "__fish_rattler_build_needs_command" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_needs_command" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_needs_command" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_needs_command" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_needs_command" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -s V -l version -d 'Print version'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "build" -d 'Build a package from a recipe'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "publish" -d 'Publish packages to a channel. This command builds packages from recipes (or uses already built packages), uploads them to a channel, and runs indexing'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "test" -d 'Run a test for a single package'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "rebuild" -d 'Rebuild a package from a package file instead of a recipe'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "upload" -d 'Upload a package'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "completion" -d 'Generate shell completion script'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "generate-recipe" -d 'Generate a recipe from PyPI, CRAN, CPAN, or LuaRocks'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "auth" -d 'Handle authentication to external channels'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "debug" -d 'Debug a recipe by setting up the environment without running the build script'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "create-patch" -d 'Create a patch for a directory'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "debug-shell" -d 'Open a debug shell in the build environment'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "package" -d 'Package-related subcommands'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "bump-recipe" -d 'Bump a recipe to a new version'
complete -c rattler-build -n "__fish_rattler_build_needs_command" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s r -l recipe -d 'The recipe file or directory containing `recipe.yaml`. Defaults to the current directory' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l recipe-dir -d 'The directory that contains recipes' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l up-to -d 'Build recipes up to the specified package' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l build-platform -d 'The build platform to use for the build (e.g. for building with emulation, or rendering)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l target-platform -d 'The target platform for the build' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l host-platform -d 'The host platform for the build. If set, it will be used to determine also the target_platform (as long as it is not noarch)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s c -l channel -d 'Add a channel to search for dependencies in' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s m -l variant-config -d 'Variant configuration files for the build' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l variant -d 'Override specific variant values (e.g. --variant python=3.12 or --variant python=3.12,3.11). Multiple values separated by commas will create multiple build variants' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l package-format -d 'The package format to use for the build. Can be one of `tar-bz2` or `conda`. You can also add a compression level to the package format, e.g. `tar-bz2:<number>` (from 1 to 9) or `conda:<number>` (from -7 to 22).' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l compression-threads -d 'The number of threads to use for compression (only relevant when also using `--package-format conda`)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l io-concurrency-limit -d 'The maximum number of concurrent I/O operations to use when installing packages This can be controlled by the `RATTLER_IO_CONCURRENCY_LIMIT` environment variable Defaults to 8 times the number of CPUs' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l test -d 'The strategy to use for running tests' -r -f -a "skip\t'Skip the tests'
native\t'Run the tests only if the build platform is the same as the host platform. Otherwise, skip the tests. If the target platform is noarch, the tests are always executed'
native-and-emulated\t'Always run the tests'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l output-dir -d 'Output directory for build artifacts.' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l channel-priority -d 'Channel priority to use when solving' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l skip-existing -d 'Whether to skip packages that already exist in any channel If set to `none`, do not skip any packages, default when not specified. If set to `local`, only skip packages that already exist locally, default when using `--skip-existing. If set to `all`, skip packages that already exist in any channel' -r -f -a "none\t'Do not skip any packages'
local\t'Skip packages that already exist locally'
all\t'Skip packages that already exist in any channel'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l noarch-build-platform -d 'Define a "noarch platform" for which the noarch packages will be built for. The noarch builds will be skipped on the other platforms' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l extra-meta -d 'Extra metadata to include in about.json' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-read -d 'Allow read access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-read-execute -d 'Allow read and execute access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-read-write -d 'Allow read and write access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l exclude-newer -d 'Exclude packages newer than this date from the solver, in RFC3339 format (e.g. 2024-03-15T12:00:00Z)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l build-num -d 'Override the build number for all outputs (defaults to the build number in the recipe)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l ignore-recipe-variants -d 'Do not read the `variants.yaml` file next to a recipe'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l render-only -d 'Render the recipe files without executing the build'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l with-solve -d 'Render the recipe files with solving dependencies'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l keep-build -d 'Keep intermediate build artifacts after the build'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l no-build-id -d 'Don\'t use build id(timestamp) when creating build directory name'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l no-include-recipe -d 'Don\'t store the recipe in the final package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l no-test -d 'Do not run tests after building (deprecated, use `--test=skip` instead)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l color-build-log -d 'Don\'t force colors in the output of the build script'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l use-zstd -d 'Enable support for repodata.json.zst'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l use-bz2 -d 'Enable support for repodata.json.bz2'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l use-sharded -d 'Enable support for sharded repodata'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l use-jlap -d 'Enable support for JLAP (JSON Lines Append Protocol)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l experimental -d 'Enable experimental features'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l tui -d 'Launch the terminal user interface'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l sandbox -d 'Enable the sandbox'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-network -d 'Allow network access during build (default: false if sandbox is enabled)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l overwrite-default-sandbox-config -d 'Overwrite the default sandbox configuration'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l debug -d 'Enable debug output in build scripts'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l continue-on-failure -d 'Continue building even if (one) of the packages fails to build. This is useful when building many packages with `--recipe-dir`.`'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l error-prefix-in-binary -d 'Error if the host prefix is detected in any binary files'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-symlinks-on-windows -d 'Allow symlinks in packages on Windows (defaults to false - symlinks are forbidden on Windows)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -l allow-absolute-license-paths -d 'Allow absolute paths in license_file entries (defaults to false)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand build" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l to -d 'The channel or URL to publish the package to' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l build-number -d 'Override the build number for all outputs. Use an absolute value (e.g., `--build-number=12`) or a relative bump (e.g., `--build-number=+1`). When using a relative bump, the highest build number from the target channel is used as the base' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s r -l recipe -d 'The recipe file or directory containing `recipe.yaml`. Defaults to the current directory' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l recipe-dir -d 'The directory that contains recipes' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l up-to -d 'Build recipes up to the specified package' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l build-platform -d 'The build platform to use for the build (e.g. for building with emulation, or rendering)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l target-platform -d 'The target platform for the build' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l host-platform -d 'The host platform for the build. If set, it will be used to determine also the target_platform (as long as it is not noarch)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s c -l channel -d 'Add a channel to search for dependencies in' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s m -l variant-config -d 'Variant configuration files for the build' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l variant -d 'Override specific variant values (e.g. --variant python=3.12 or --variant python=3.12,3.11). Multiple values separated by commas will create multiple build variants' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l package-format -d 'The package format to use for the build. Can be one of `tar-bz2` or `conda`. You can also add a compression level to the package format, e.g. `tar-bz2:<number>` (from 1 to 9) or `conda:<number>` (from -7 to 22).' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l compression-threads -d 'The number of threads to use for compression (only relevant when also using `--package-format conda`)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l io-concurrency-limit -d 'The maximum number of concurrent I/O operations to use when installing packages This can be controlled by the `RATTLER_IO_CONCURRENCY_LIMIT` environment variable Defaults to 8 times the number of CPUs' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l test -d 'The strategy to use for running tests' -r -f -a "skip\t'Skip the tests'
native\t'Run the tests only if the build platform is the same as the host platform. Otherwise, skip the tests. If the target platform is noarch, the tests are always executed'
native-and-emulated\t'Always run the tests'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l output-dir -d 'Output directory for build artifacts.' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l channel-priority -d 'Channel priority to use when solving' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l skip-existing -d 'Whether to skip packages that already exist in any channel If set to `none`, do not skip any packages, default when not specified. If set to `local`, only skip packages that already exist locally, default when using `--skip-existing. If set to `all`, skip packages that already exist in any channel' -r -f -a "none\t'Do not skip any packages'
local\t'Skip packages that already exist locally'
all\t'Skip packages that already exist in any channel'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l noarch-build-platform -d 'Define a "noarch platform" for which the noarch packages will be built for. The noarch builds will be skipped on the other platforms' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l extra-meta -d 'Extra metadata to include in about.json' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-read -d 'Allow read access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-read-execute -d 'Allow read and execute access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-read-write -d 'Allow read and write access to the specified paths' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l exclude-newer -d 'Exclude packages newer than this date from the solver, in RFC3339 format (e.g. 2024-03-15T12:00:00Z)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l build-num -d 'Override the build number for all outputs (defaults to the build number in the recipe)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l force -d 'Force upload even if the package already exists (not recommended - may break lockfiles). Only works with S3, filesystem, Anaconda.org, and prefix.dev channels'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l generate-attestation -d 'Automatically generate attestations when uploading to prefix.dev channels. Only works when uploading to prefix.dev channels with trusted publishing enabled'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l ignore-recipe-variants -d 'Do not read the `variants.yaml` file next to a recipe'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l render-only -d 'Render the recipe files without executing the build'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l with-solve -d 'Render the recipe files with solving dependencies'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l keep-build -d 'Keep intermediate build artifacts after the build'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l no-build-id -d 'Don\'t use build id(timestamp) when creating build directory name'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l no-include-recipe -d 'Don\'t store the recipe in the final package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l no-test -d 'Do not run tests after building (deprecated, use `--test=skip` instead)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l color-build-log -d 'Don\'t force colors in the output of the build script'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l use-zstd -d 'Enable support for repodata.json.zst'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l use-bz2 -d 'Enable support for repodata.json.bz2'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l use-sharded -d 'Enable support for sharded repodata'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l use-jlap -d 'Enable support for JLAP (JSON Lines Append Protocol)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l experimental -d 'Enable experimental features'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l tui -d 'Launch the terminal user interface'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l sandbox -d 'Enable the sandbox'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-network -d 'Allow network access during build (default: false if sandbox is enabled)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l overwrite-default-sandbox-config -d 'Overwrite the default sandbox configuration'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l debug -d 'Enable debug output in build scripts'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l continue-on-failure -d 'Continue building even if (one) of the packages fails to build. This is useful when building many packages with `--recipe-dir`.`'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l error-prefix-in-binary -d 'Error if the host prefix is detected in any binary files'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-symlinks-on-windows -d 'Allow symlinks in packages on Windows (defaults to false - symlinks are forbidden on Windows)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -l allow-absolute-license-paths -d 'Allow absolute paths in license_file entries (defaults to false)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand publish" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -s c -l channel -d 'Channels to use when testing' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -s p -l package-file -d 'The package file to test' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l compression-threads -d 'The number of threads to use for compression' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l test-index -d 'The index of the test to run. This is used to run a specific test from the package' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l output-dir -d 'Output directory for build artifacts.' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l channel-priority -d 'Channel priority to use when solving' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l debug -d 'Build test environment and output debug information for manual debugging'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l use-zstd -d 'Enable support for repodata.json.zst'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l use-bz2 -d 'Enable support for repodata.json.bz2'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l use-sharded -d 'Enable support for sharded repodata'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l use-jlap -d 'Enable support for JLAP (JSON Lines Append Protocol)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -l experimental -d 'Enable experimental features'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand test" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -s p -l package-file -d 'The package file to rebuild (can be a local path or URL)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l test -d 'The strategy to use for running tests' -r -f -a "skip\t'Skip the tests'
native\t'Run the tests only if the build platform is the same as the host platform. Otherwise, skip the tests. If the target platform is noarch, the tests are always executed'
native-and-emulated\t'Always run the tests'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l compression-threads -d 'The number of threads to use for compression' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l io-concurrency-limit -d 'The number of threads to use for I/O operations when installing packages' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l output-dir -d 'Output directory for build artifacts.' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l channel-priority -d 'Channel priority to use when solving' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l no-test -d 'Do not run tests after building (deprecated, use `--test=skip` instead)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l use-zstd -d 'Enable support for repodata.json.zst'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l use-bz2 -d 'Enable support for repodata.json.bz2'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l use-sharded -d 'Enable support for sharded repodata'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l use-jlap -d 'Enable support for JLAP (JSON Lines Append Protocol)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -l experimental -d 'Enable experimental features'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand rebuild" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "quetz" -d 'Upload to a Quetz server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "artifactory" -d 'Options for uploading to a Artifactory channel. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "prefix" -d 'Options for uploading to a prefix.dev server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "anaconda" -d 'Options for uploading to a Anaconda.org server'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "s3" -d 'Options for uploading to S3'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "conda-forge" -d 'Options for uploading to conda-forge'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and not __fish_seen_subcommand_from quetz artifactory prefix anaconda s3 conda-forge help" -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s u -l url -d 'The URL to your Quetz server' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s c -l channel -d 'The URL to your channel' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s a -l api-key -d 'The Quetz API key, if none is provided, the token is read from the keychain / auth-file' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from quetz" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s u -l url -d 'The URL to your Artifactory server' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s c -l channel -d 'The URL to your channel' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l username -d 'Your Artifactory username' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l password -d 'Your Artifactory password' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s t -l token -d 'Your Artifactory token' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from artifactory" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s u -l url -d 'The URL to the prefix.dev server (only necessary for self-hosted instances)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s c -l channel -d 'The channel to upload the package to' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s a -l api-key -d 'The prefix.dev API key, if none is provided, the token is read from the keychain / auth-file' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l attestation -d 'Upload an attestation file alongside the package. Note: if you add an attestation, you can _only_ upload a single package. Mutually exclusive with --generate-attestation' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l generate-attestation -d 'Automatically generate attestation using cosign in CI. Mutually exclusive with --attestation'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l store-github-attestation -d 'Also store the generated attestation to GitHub\'s attestation API. Requires `GITHUB_TOKEN` environment variable and only works in GitHub Actions. The attestation will be associated with the current repository'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s s -l skip-existing -d 'Skip upload if package already exists'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -l force -d 'Force overwrite existing packages'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from prefix" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s o -l owner -d 'The owner of the distribution (e.g. conda-forge or your username)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s c -l channel -d 'The channel / label to upload the package to (e.g. main / rc)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s a -l api-key -d 'The Anaconda API key, if none is provided, the token is read from the keychain / auth-file' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s u -l url -d 'The URL to the Anaconda server' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s f -l force -d 'Replace files on conflict'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from anaconda" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -s c -l channel -d 'The channel URL in the S3 bucket to upload the package to, e.g., `s3://my-bucket/my-channel`' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l endpoint-url -d 'The endpoint URL of the S3 backend' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l region -d 'The region of the S3 backend' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l access-key-id -d 'The access key ID for the S3 bucket' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l secret-access-key -d 'The secret access key for the S3 bucket' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l session-token -d 'The session token for the S3 bucket' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l addressing-style -d 'How to address the bucket' -r -f -a "virtual-host\t''
path\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l force-path-style -d '[deprecated] Whether to use path-style S3 URLs' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -l force -d 'Replace files if it already exists'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from s3" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l staging-token -d 'The Anaconda API key' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l feedstock -d 'The feedstock name' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l feedstock-token -d 'The feedstock token' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l staging-channel -d 'The staging channel name' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l anaconda-url -d 'The Anaconda Server URL' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l validation-endpoint -d 'The validation endpoint url' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l provider -d 'The CI provider' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -l dry-run -d 'Dry run, don\'t actually upload anything'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from conda-forge" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "quetz" -d 'Upload to a Quetz server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "artifactory" -d 'Options for uploading to a Artifactory channel. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "prefix" -d 'Options for uploading to a prefix.dev server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "anaconda" -d 'Options for uploading to a Anaconda.org server'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "s3" -d 'Options for uploading to S3'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "conda-forge" -d 'Options for uploading to conda-forge'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand upload; and __fish_seen_subcommand_from help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -s s -l shell -d 'Specifies the shell for which the completions should be generated' -r -f -a "bash\t'Bourne Again SHell (bash)'
elvish\t'Elvish shell'
fish\t'Friendly Interactive SHell (fish)'
nushell\t'Nushell'
powershell\t'PowerShell'
zsh\t'Z SHell (zsh)'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand completion" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -f -a "pypi" -d 'Generate a recipe for a Python package from PyPI'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -f -a "cran" -d 'Generate a recipe for an R package from CRAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -f -a "cpan" -d 'Generate a recipe for a Perl package from CPAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -f -a "luarocks" -d 'Generate a recipe for a Lua package from LuaRocks'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and not __fish_seen_subcommand_from pypi cran cpan luarocks help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -l version -d 'Select a version of the package to generate (defaults to latest)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s w -l write -d 'Whether to write the recipe to a folder'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s u -l use-mapping -d 'Whether to use the conda-forge PyPI name mapping'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s t -l tree -d 'Whether to generate recipes for all dependencies'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from pypi" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s u -l universe -d 'The R Universe to fetch the package from (defaults to `cran`)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s t -l tree -d 'Whether to create recipes for the whole dependency tree or not'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s w -l write -d 'Whether to write the recipe to a folder'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cran" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -l version -d 'Select a version of the package to generate (defaults to latest)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -s w -l write -d 'Whether to write the recipe to a folder'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -s t -l tree -d 'Whether to generate recipes for all dependencies'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from cpan" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -s w -l write-to -d 'Where to write the recipe to' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from luarocks" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from help" -f -a "pypi" -d 'Generate a recipe for a Python package from PyPI'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from help" -f -a "cran" -d 'Generate a recipe for an R package from CRAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from help" -f -a "cpan" -d 'Generate a recipe for a Perl package from CPAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from help" -f -a "luarocks" -d 'Generate a recipe for a Lua package from LuaRocks'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand generate-recipe; and __fish_seen_subcommand_from help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -f -a "login" -d 'Store authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -f -a "logout" -d 'Remove authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and not __fish_seen_subcommand_from login logout help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l token -d 'The token to use (for authentication with prefix.dev)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l username -d 'The username to use (for basic HTTP authentication)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l password -d 'The password to use (for basic HTTP authentication)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l conda-token -d 'The token to use on anaconda.org / quetz authentication' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l s3-access-key-id -d 'The S3 access key ID' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l s3-secret-access-key -d 'The S3 secret access key' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l s3-session-token -d 'The S3 session token' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from login" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from logout" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from help" -f -a "login" -d 'Store authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from help" -f -a "logout" -d 'Remove authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand auth; and __fish_seen_subcommand_from help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s r -l recipe -d 'Recipe file to debug' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s o -l output -d 'Output directory for build artifacts' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l target-platform -d 'The target platform to build for' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l host-platform -d 'The host platform to build for (defaults to target_platform)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l build-platform -d 'The build platform to build for (defaults to current platform)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s c -l channel -d 'Channels to use when building' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l output-dir -d 'Output directory for build artifacts.' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l allow-insecure-host -d 'List of hosts for which SSL certificate verification should be skipped' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l auth-file -d 'Path to an auth-file to read authentication information from' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l channel-priority -d 'Channel priority to use when solving' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l output-name -d 'Name of the specific output to debug' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l use-zstd -d 'Enable support for repodata.json.zst'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l use-bz2 -d 'Enable support for repodata.json.bz2'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l use-sharded -d 'Enable support for sharded repodata'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l use-jlap -d 'Enable support for JLAP (JSON Lines Append Protocol)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -l experimental -d 'Enable experimental features'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -s d -l directory -d 'Directory where we want to create the patch. Defaults to current directory if not specified' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l name -d 'The name for the patch file to create' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l patch-dir -d 'Optional directory where the patch file should be written. Defaults to the recipe directory determined from `.source_info.json` if not provided' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l exclude -d 'Comma-separated list of file names (or glob patterns) that should be excluded from the diff' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l add -d 'Include new files matching these glob patterns (e.g., "*.txt", "src/**/*.rs")' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l include -d 'Only include modified files matching these glob patterns (e.g., "*.c", "src/**/*.rs") If not specified, all modified files are included (subject to --exclude)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l overwrite -d 'Whether to overwrite the patch file if it already exists'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -l dry-run -d 'Perform a dry-run: analyze changes and log the diff, but don\'t write the patch file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand create-patch" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -l work-dir -d 'Work directory to use (reads from last build in rattler-build-log.txt if not specified)' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -s o -l output-dir -d 'Output directory containing rattler-build-log.txt' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand debug-shell" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -f -a "inspect" -d 'Inspect and display information about a built package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -f -a "extract" -d 'Extract a conda package to a directory'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and not __fish_seen_subcommand_from inspect extract help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l paths -d 'Show detailed file listing with hashes and sizes'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l about -d 'Show extended about information'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l run-exports -d 'Show run exports'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l all -d 'Show all available information'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -l json -d 'Output as JSON'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from inspect" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -s d -l dest -d 'Destination directory for extraction (defaults to package name without extension)' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from extract" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from help" -f -a "inspect" -d 'Inspect and display information about a built package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from help" -f -a "extract" -d 'Extract a conda package to a directory'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand package; and __fish_seen_subcommand_from help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -s r -l recipe -d 'Path to the recipe file (recipe.yaml). Defaults to current directory' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l version -d 'The new version to bump to. If not specified, will auto-detect the latest version from the source URL\'s provider (GitHub, PyPI, crates.io)' -r
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l log-style -d 'Logging style' -r -f -a "fancy\t'Use fancy logging output'
json\t'Use JSON logging output'
plain\t'Use plain logging output'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l wrap-log-lines -d 'Wrap log lines at the terminal width. This is automatically disabled on CI (by detecting the `CI` environment variable)' -r -f -a "true\t''
false\t''"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l config-file -d 'The rattler-build configuration file to use' -r -F
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l color -d 'Enable or disable colored output from rattler-build. Also honors the `CLICOLOR` and `CLICOLOR_FORCE` environment variable' -r -f -a "always\t'Always use colors'
never\t'Never use colors'
auto\t'Use colors when the output is a terminal'"
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l include-prerelease -d 'Include pre-release versions when auto-detecting (e.g., alpha, beta, rc)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l check-only -d 'Only check for updates without modifying the recipe'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l dry-run -d 'Perform a dry-run: show what would be changed without writing to the file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -l keep-build-number -d 'Keep the current build number instead of resetting it to 0'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -s v -l verbose -d 'Increase logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -s q -l quiet -d 'Decrease logging verbosity'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand bump-recipe" -s h -l help -d 'Print help (see more with \'--help\')'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "build" -d 'Build a package from a recipe'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "publish" -d 'Publish packages to a channel. This command builds packages from recipes (or uses already built packages), uploads them to a channel, and runs indexing'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "test" -d 'Run a test for a single package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "rebuild" -d 'Rebuild a package from a package file instead of a recipe'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "upload" -d 'Upload a package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "completion" -d 'Generate shell completion script'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "generate-recipe" -d 'Generate a recipe from PyPI, CRAN, CPAN, or LuaRocks'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "auth" -d 'Handle authentication to external channels'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "debug" -d 'Debug a recipe by setting up the environment without running the build script'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "create-patch" -d 'Create a patch for a directory'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "debug-shell" -d 'Open a debug shell in the build environment'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "package" -d 'Package-related subcommands'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "bump-recipe" -d 'Bump a recipe to a new version'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and not __fish_seen_subcommand_from build publish test rebuild upload completion generate-recipe auth debug create-patch debug-shell package bump-recipe help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "quetz" -d 'Upload to a Quetz server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "artifactory" -d 'Options for uploading to a Artifactory channel. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "prefix" -d 'Options for uploading to a prefix.dev server. Authentication is used from the keychain / auth-file'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "anaconda" -d 'Options for uploading to a Anaconda.org server'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "s3" -d 'Options for uploading to S3'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from upload" -f -a "conda-forge" -d 'Options for uploading to conda-forge'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from generate-recipe" -f -a "pypi" -d 'Generate a recipe for a Python package from PyPI'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from generate-recipe" -f -a "cran" -d 'Generate a recipe for an R package from CRAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from generate-recipe" -f -a "cpan" -d 'Generate a recipe for a Perl package from CPAN'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from generate-recipe" -f -a "luarocks" -d 'Generate a recipe for a Lua package from LuaRocks'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from auth" -f -a "login" -d 'Store authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from auth" -f -a "logout" -d 'Remove authentication information for a given host'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from package" -f -a "inspect" -d 'Inspect and display information about a built package'
complete -c rattler-build -n "__fish_rattler_build_using_subcommand help; and __fish_seen_subcommand_from package" -f -a "extract" -d 'Extract a conda package to a directory'
