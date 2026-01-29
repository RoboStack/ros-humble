"""Utilities for converting ROS package licenses to SPDX format."""

import re
from typing import List, Optional, Dict
from license_expression import get_spdx_licensing, ExpressionError

# Lookup table for common non-SPDX license strings to SPDX identifiers
# Note: Keys are lowercase for case-insensitive matching
# Note: Entries like BSD-2 and GPL are omitted as they're already normalized
# by license-expression (BSD-2 -> BSD-2-Clause, GPL -> GPL-1.0-or-later)
LICENSE_LOOKUP: Dict[str, str] = {
    # BSD variants
    "bsd": "BSD-3-Clause",
    "bsd-3": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "3-clause bsd": "BSD-3-Clause",
    "bsd clause 3": "BSD-3-Clause",
    "bsd 3 clause": "BSD-3-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "bds-3": "BSD-3-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "bsd license 2.0": "BSD-2-Clause",
    # Apache variants
    "apache": "Apache-2.0",
    "apache 2": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "apache2": "Apache-2.0",
    "apache2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache 2.0 license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache-2.0 license": "Apache-2.0",
    "alv2": "Apache-2.0",
    # GPL variants
    "gplv2": "GPL-2.0-only",
    "gpl-2": "GPL-2.0-only",
    "gpl-2.0": "GPL-2.0-only",
    "gnu general public license v2.0": "GPL-2.0-only",
    "gplv3": "GPL-3.0-only",
    "gpl-3": "GPL-3.0-only",
    "gpl-3.0": "GPL-3.0-only",
    # AGPL variants
    "agplv3": "AGPL-3.0-only",
    "agpl-3": "AGPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    # LGPL variants (note: defaulting to 2.1-or-later for ROS compatibility)
    "lgpl": "LGPL-2.1-or-later",
    "lgplv2": "LGPL-2.1-or-later",
    "lgplv2.1": "LGPL-2.1-or-later",
    "lgpl-2": "LGPL-2.1-or-later",
    "lgpl-2.1": "LGPL-2.1-or-later",
    "lgpl v2.1": "LGPL-2.1-or-later",
    "lgplv3": "LGPL-3.0-only",
    "lgpl-3": "LGPL-3.0-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "lgpl-v3": "LGPL-3.0-only",
    "LGPL (amcl)": "LGPL-2.1-or-later",
    "gnu lesser public license 2.1": "LGPL-2.1-only",
    # Mozilla/MPL variants
    "mozilla": "MPL-2.0",
    "mpl": "MPL-2.0",
    "mpl-2.0 license": "MPL-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "mozilla public license version 1.1": "MPL-1.1",
    # Eclipse variants
    "eclipse public license 2.0": "EPL-2.0",
    "eclipse distribution license 1.0": "BSD-3-Clause",
    # Boost variants
    "boost": "BSL-1.0",
    "boost software license": "BSL-1.0",
    "bsl": "BSL-1.0",
    # MIT variants
    "mit license": "MIT",
    # Zlib variants
    "zlib license": "Zlib",
    # Creative Commons
    "cc by-nc-sa 4.0": "CC-BY-NC-SA-4.0",
    "cc0": "CC0-1.0",
    "creative commons zero v1.0 universal": "CC0-1.0",
    "creative commons attribution-noncommercial-noderivatives 4.0 international public license": "CC-BY-NC-ND-4.0",
    "creative commons": "CC0-1.0",  # The version is an assumption
    # Public Domain (choosing Unlicense as more appropriate for code)
    "public domain": "Unlicense",
}


def _process_single_license(
    lic_str: str, package_name: Optional[str] = None
) -> Optional[str]:
    """Process a single license string and convert to SPDX.

    Args:
        lic_str: A single license string
        package_name: Optional package name for warning messages

    Returns:
        SPDX license identifier or None
    """
    # Try to validate and get normalized SPDX expression
    validation_result = validate_and_normalize_license(lic_str)

    if validation_result:
        # Valid SPDX license, use normalized form
        return validation_result
    # Check if it's in the lookup table (case-insensitive)
    elif lic_str.lower() in LICENSE_LOOKUP:
        return LICENSE_LOOKUP[lic_str.lower()]

    # Not found in lookup table either - use LicenseRef-
    # Clean up the license string for use in LicenseRef
    clean_lic = re.sub(r"[^A-Za-z0-9.\-]", "-", lic_str)
    license_ref = f"LicenseRef-{clean_lic}"
    pkg_info = f" in package '{package_name}'" if package_name else ""
    print(
        f"Warning: License '{lic_str}'{pkg_info} is not a "
        f"recognized SPDX identifier. Using '{license_ref}' instead."
    )
    return license_ref


def convert_to_spdx_license(
    licenses: List[str], package_name: Optional[str] = None
) -> Optional[str]:
    """Convert ROS package licenses to SPDX format.

    Args:
        licenses: A list of license strings from catkin_pkg package.licenses
        package_name: Optional package name to include in warning messages

    Returns:
        A SPDX license expression string, or None if no valid license found.

    Rules:
        - If license is "TODO", return None (don't add license)
        - If license is valid SPDX, use as-is
        - If license is not recognized, prefix with "LicenseRef-"
        - Multiple licenses are combined with " OR "
    """
    if not licenses:
        return None

    spdx_licenses: List[str] = []

    for lic in licenses:
        lic_str = str(lic).strip()

        # Skip TODO and empty licenses
        if not lic_str or lic_str.upper() == "TODO":
            continue

        # Check lookup table first (before splitting on commas)
        # This handles cases like "Apache License, Version 2.0"
        if lic_str.lower() in LICENSE_LOOKUP:
            spdx_licenses.append(LICENSE_LOOKUP[lic_str.lower()])
            continue

        # Check if license can be normalized by SPDX
        validation_result = validate_and_normalize_license(lic_str)
        if validation_result:
            spdx_licenses.append(validation_result)
            continue

        # Check if license contains comma (multiple licenses in one string)
        if "," in lic_str:
            # Split by comma and process each part
            # Filter out empty strings from malformed input
            # (trailing/double commas)
            parts = [part.strip() for part in lic_str.split(",") if part.strip()]
            sub_licenses = []
            seen_sub = set()
            for part in parts:
                result = _process_single_license(part, package_name)
                if result and result not in seen_sub:
                    seen_sub.add(result)
                    sub_licenses.append(result)
            if sub_licenses:
                # Join with OR for comma-separated licenses (dual-licensed)
                spdx_licenses.append(" OR ".join(sub_licenses))
            continue

        # Process single license (fallback for LicenseRef)
        result = _process_single_license(lic_str, package_name)
        if result:
            spdx_licenses.append(result)

    if not spdx_licenses:
        return None

    # Deduplicate licenses while preserving order
    seen = set()
    unique_licenses = []
    for lic in spdx_licenses:
        if lic not in seen:
            seen.add(lic)
            unique_licenses.append(lic)

    # Combine multiple licenses with OR
    return " OR ".join(unique_licenses)


def validate_and_normalize_license(license_string: str) -> Optional[str]:
    """Validate and normalize a license string to SPDX format.

    Args:
        license_string: A license identifier string

    Returns:
        The normalized SPDX identifier if valid, None otherwise
    """
    if not license_string:
        return None

    licensing = get_spdx_licensing()

    try:
        # Use the validate method to check if the license expression is valid
        validation_result = licensing.validate(license_string)
        # If there are no validation errors, return the normalized expression
        if len(validation_result.errors) == 0:
            return validation_result.normalized_expression
        return None
    except (ExpressionError, Exception):
        return None


def is_valid_spdx_license(license_string: str) -> bool:
    """Check if a license string is a valid SPDX identifier.

    Args:
        license_string: A license identifier string

    Returns:
        True if the license is a valid SPDX identifier, False otherwise
    """
    return validate_and_normalize_license(license_string) is not None
