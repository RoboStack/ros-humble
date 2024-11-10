"""
Patch Verifier Module

This module provides functionality to analyze build logs, determine if a build failed, 
and identify the package that caused the failure.

Functions:
    - identify_failed_package: Analyzes the build log to identify the package causing a build failure.
    - check: Determines if a build was successful and identifies the problematic package if it failed.

Typical Usage Example:
    >>> import patch_verifier
    >>> log_path = "/path/to/build_log.txt"
    >>> build_success, failed_package = patch_verifier.check(log_path)
    >>> if not build_success:
    ...     print(f"Build failed due to package: {failed_package}")
"""


import os
import re



def identify_failed_package(path):
    """
    Identifies the package that caused a build error by analyzing the provided log file.

    This function reads the specified log file, searches for lines that indicate a build error
    by matching the pattern 'Output: <package_name>', and returns the last package name found.
    If no such pattern is found, it raises a ValueError.

    Args:
        path (str): The file path to the log file that needs to be analyzed.

    Returns:
        str: The name of the package that caused the build error.

    Raises:
        ValueError: If no failing package is found in the log file.
        FileNotFoundError: If the specified log file does not exist.
        IOError: If there is an error reading the log file.

    Example:
        >>> identify_failed_package('/path/to/logfile.log')
        'example_package'

    Notes:
        - The function assumes that the log file is in plain text format and that each line
          follows the pattern 'Output: <package_name>' when a package fails.
        - The regular expression used to identify the failing package is case-sensitive.
        - If multiple lines match the pattern, the function returns the last package name found.
    """
    with open(path) as f:
        pattern = r"Output:\s*(\S+)"
        f_data = f.read()
        match = re.findall(pattern, f_data)
        target = match[-1]
        if match:
            return target
        else:
            raise ValueError("No failing package found")



def check(path):
    """
    Determines if a build was successful by analyzing the last line of a log file.
    
    The function reads the last line of the specified log file and checks if it's empty
    (after removing whitespace and special characters). An empty last line indicates
    a successful build. If the build failed, it identifies the problematic package.
    
    Args:
        path (str): The file path to the build log to analyze
        
    Returns:
        - build_success (bool): True if build succeeded, False otherwise
        - bad_package (str or None): Name of failed package if build failed,
            None if build was successful
              
    Raises:
        OSError: If there are issues reading the log file
        UnicodeDecodeError: If the log file contains invalid Unicode characters
        
    Example:
        >>> success, package = check("build_log.txt")
        >>> if not success:
        ...     print(f"Build failed due to package: {package}")
        
    Notes:
        - The function uses reverse file reading to efficiently get the last line
        - Special characters (╵) and whitespace are stripped before analysis
        - Empty last line after stripping indicates successful build
    """
    file = open(path,"rb")
    try:  # catch OSError in case of a one line file 
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b'\n':
            file.seek(-2, os.SEEK_CUR)
    except OSError:
        file.seek(0)
    last_line = file.readline().decode()
    print(last_line)
    sampled = re.sub(r'[╵\s]', '', last_line)
    build_success = not bool(len(sampled))
    if  build_success:
        return build_success, None
    else:
        return build_success, identify_failed_package(path)