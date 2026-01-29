setlocal EnableExtensions EnableDelayedExpansion
call activate base

set "FEEDSTOCK_ROOT=%cd%"

call conda config --add channels conda-forge
call conda config --add channels robostack-staging
call conda config --set channel_priority strict

:: Enable long path names on Windows
reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f

:: conda remove --force m2-git

for %%X in (%CURRENT_RECIPES%) do (
    echo "BUILDING RECIPE %%X"
    cd %FEEDSTOCK_ROOT%\\recipes\\%%X\\
    copy %FEEDSTOCK_ROOT%\\conda_build_config.yaml .\\conda_build_config.yaml
    boa build .
    if errorlevel 1 exit 1
)

anaconda -t %ANACONDA_API_TOKEN% upload "C:\\bld\\win-64\\*.tar.bz2" --force
if errorlevel 1 exit 1
