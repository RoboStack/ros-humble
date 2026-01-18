from vinca.license_utils import convert_to_spdx_license, is_valid_spdx_license


# Tests for is_valid_spdx_license function


def test_valid_common_licenses():
    """Test common valid SPDX licenses."""
    assert is_valid_spdx_license("MIT")
    assert is_valid_spdx_license("Apache-2.0")
    assert is_valid_spdx_license("BSD-3-Clause")
    assert is_valid_spdx_license("GPL-3.0-only")
    assert is_valid_spdx_license("LGPL-2.1-or-later")


def test_invalid_licenses():
    """Test invalid/non-standard license strings."""
    assert not is_valid_spdx_license("Proprietary")
    assert not is_valid_spdx_license("Custom License")
    assert not is_valid_spdx_license("TODO")
    assert not is_valid_spdx_license("Unknown")


def test_empty_string():
    """Test empty string returns False."""
    assert not is_valid_spdx_license("")


# Tests for convert_to_spdx_license function


def test_empty_list():
    """Test empty list returns None."""
    assert convert_to_spdx_license([]) is None


def test_single_valid_license():
    """Test single valid SPDX license."""
    assert convert_to_spdx_license(["MIT"]) == "MIT"
    assert convert_to_spdx_license(["Apache-2.0"]) == "Apache-2.0"
    assert convert_to_spdx_license(["BSD-3-Clause"]) == "BSD-3-Clause"


def test_single_invalid_license():
    """Test single invalid license gets LicenseRef- prefix."""
    result = convert_to_spdx_license(["Proprietary"])
    assert result == "LicenseRef-Proprietary"
    result = convert_to_spdx_license(["Custom License"])
    assert result == "LicenseRef-Custom-License"


def test_todo_license_ignored():
    """Test TODO license is skipped."""
    assert convert_to_spdx_license(["TODO"]) is None
    assert convert_to_spdx_license(["todo"]) is None
    assert convert_to_spdx_license(["Todo"]) is None


def test_multiple_valid_licenses():
    """Test multiple valid licenses are combined with OR."""
    result = convert_to_spdx_license(["MIT", "Apache-2.0"])
    assert result == "MIT OR Apache-2.0"

    result = convert_to_spdx_license(["BSD-3-Clause", "GPL-3.0-only"])
    assert result == "BSD-3-Clause OR GPL-3.0-only"


def test_multiple_invalid_licenses():
    """Test multiple invalid licenses get LicenseRef- prefix and OR."""
    result = convert_to_spdx_license(["Custom", "Proprietary"])
    assert result == "LicenseRef-Custom OR LicenseRef-Proprietary"


def test_mixed_valid_invalid_licenses():
    """Test mix of valid and invalid licenses."""
    result = convert_to_spdx_license(["MIT", "Custom"])
    assert result == "MIT OR LicenseRef-Custom"


def test_todo_with_valid_licenses():
    """Test TODO is filtered out when combined with valid licenses."""
    result = convert_to_spdx_license(["TODO", "MIT"])
    assert result == "MIT"

    result = convert_to_spdx_license(["MIT", "TODO", "Apache-2.0"])
    assert result == "MIT OR Apache-2.0"


def test_all_todos():
    """Test list of only TODOs returns None."""
    assert convert_to_spdx_license(["TODO", "todo", "Todo"]) is None


def test_license_with_spaces_converted():
    """Test licenses with spaces have spaces replaced with hyphens."""
    result = convert_to_spdx_license(["My License"])
    assert result == "LicenseRef-My-License"


def test_license_with_slashes_converted():
    """Test licenses with slashes have slashes replaced with hyphens."""
    result = convert_to_spdx_license(["BSD/MIT"])
    assert result == "LicenseRef-BSD-MIT"


def test_whitespace_stripped():
    """Test leading/trailing whitespace is stripped."""
    assert convert_to_spdx_license(["  MIT  "]) == "MIT"
    assert convert_to_spdx_license([" Apache-2.0 "]) == "Apache-2.0"


def test_license_lookup_bsd():
    """Test BSD license is mapped to BSD-3-Clause."""
    assert convert_to_spdx_license(["BSD"]) == "BSD-3-Clause"


def test_license_lookup_apache():
    """Test Apache variants are mapped correctly."""
    assert convert_to_spdx_license(["Apache"]) == "Apache-2.0"
    assert convert_to_spdx_license(["Apache 2"]) == "Apache-2.0"
    assert convert_to_spdx_license(["Apache 2.0"]) == "Apache-2.0"


def test_license_lookup_gpl():
    """Test GPL variants are mapped correctly."""
    # GPL is a valid SPDX identifier and gets normalized
    assert convert_to_spdx_license(["GPL"]) == "GPL-1.0-or-later"
    # GPLv3 is not valid SPDX, so use lookup table
    assert convert_to_spdx_license(["GPLv3"]) == "GPL-3.0-only"


def test_license_lookup_with_valid():
    """Test mixed lookup and valid licenses."""
    result = convert_to_spdx_license(["BSD", "MIT"])
    assert result == "BSD-3-Clause OR MIT"


def test_bsd2_normalized():
    """Test BSD-2 is automatically normalized (not in lookup)."""
    assert convert_to_spdx_license(["BSD-2"]) == "BSD-2-Clause"


def test_empty_strings_from_trailing_comma():
    """Test trailing commas don't create empty LicenseRef."""
    assert convert_to_spdx_license(["MIT,"]) == "MIT"
    assert convert_to_spdx_license([",MIT"]) == "MIT"


def test_empty_strings_from_double_commas():
    """Test double commas are handled correctly."""
    result = convert_to_spdx_license(["MIT,,BSD"])
    assert result == "MIT OR BSD-3-Clause"


def test_invalid_characters_in_licenseref():
    """Test invalid characters are replaced in LicenseRef identifiers."""
    # Parentheses should be replaced
    result = convert_to_spdx_license(["Custom(v1.0)"])
    assert result == "LicenseRef-Custom-v1.0-"
    assert "(" not in result

    # Underscores should be replaced
    result = convert_to_spdx_license(["Custom_License"])
    assert result == "LicenseRef-Custom-License"
    assert "_" not in result

    # Spaces should be replaced
    result = convert_to_spdx_license(["My Custom License"])
    assert result == "LicenseRef-My-Custom-License"

    # Slashes should be replaced
    result = convert_to_spdx_license(["Custom/License"])
    assert result == "LicenseRef-Custom-License"


def test_duplicate_licenses_deduplicated():
    """Test duplicate licenses are deduplicated."""
    assert convert_to_spdx_license(["MIT", "MIT"]) == "MIT"
    result = convert_to_spdx_license(["BSD", "BSD-3-Clause"])
    assert result == "BSD-3-Clause"


def test_comma_separated_licenses():
    """Test comma-separated licenses are split with OR."""
    result = convert_to_spdx_license(["BSD, Apache 2.0"])
    assert result == "BSD-3-Clause OR Apache-2.0"

    result = convert_to_spdx_license(["MIT,BSD,Apache 2.0"])
    assert result == "MIT OR BSD-3-Clause OR Apache-2.0"


def test_comma_separated_with_duplicates():
    """Test comma-separated licenses with duplicates are deduplicated."""
    result = convert_to_spdx_license(["MIT, MIT"])
    assert result == "MIT"


def test_case_insensitive_lookup():
    """Test lookup table works with different cases."""
    # Lowercase
    assert convert_to_spdx_license(["bsd"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["apache"]) == "Apache-2.0"
    assert convert_to_spdx_license(["mit license"]) == "MIT"

    # Uppercase
    assert convert_to_spdx_license(["BSD"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["APACHE"]) == "Apache-2.0"

    # Mixed case
    assert convert_to_spdx_license(["BoOsT"]) == "BSL-1.0"


def test_new_license_variants():
    """Test newly added common license variants."""
    # BSD variants
    assert convert_to_spdx_license(["BSD Clause 3"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["BDS-3"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["BSD 3-Clause License"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["BSD 3 Clause"]) == "BSD-3-Clause"

    # GPL variants
    assert convert_to_spdx_license(["GPLv2"]) == "GPL-2.0-only"
    assert convert_to_spdx_license(["GPL-2"]) == "GPL-2.0-only"
    assert convert_to_spdx_license(["GPL-3.0"]) == "GPL-3.0-only"

    # LGPL variants (defaults to 2.1-or-later)
    assert convert_to_spdx_license(["LGPL"]) == "LGPL-2.1-or-later"
    assert convert_to_spdx_license(["LGPLv2"]) == "LGPL-2.1-or-later"
    assert convert_to_spdx_license(["LGPL-2.1"]) == "LGPL-2.1-or-later"
    assert convert_to_spdx_license(["LGPL v2.1"]) == "LGPL-2.1-or-later"
    assert convert_to_spdx_license(["LGPLv3"]) == "LGPL-3.0-only"
    assert convert_to_spdx_license(["LGPL-v3"]) == "LGPL-3.0-only"
    assert convert_to_spdx_license(["GNU Lesser Public License 2.1"]) == "LGPL-2.1-only"

    # AGPL variants
    assert convert_to_spdx_license(["AGPLv3"]) == "AGPL-3.0-only"
    assert convert_to_spdx_license(["AGPL-3.0"]) == "AGPL-3.0-only"

    # Boost variants
    assert convert_to_spdx_license(["Boost"]) == "BSL-1.0"
    assert convert_to_spdx_license(["Boost Software License"]) == "BSL-1.0"
    assert convert_to_spdx_license(["BSL"]) == "BSL-1.0"

    # MIT variants
    assert convert_to_spdx_license(["MIT License"]) == "MIT"

    # Apache variants
    assert convert_to_spdx_license(["Apache-2"]) == "Apache-2.0"
    assert convert_to_spdx_license(["Apache 2.0 License"]) == "Apache-2.0"
    assert convert_to_spdx_license(["ALv2"]) == "Apache-2.0"

    # MPL variants
    assert convert_to_spdx_license(["MPL-2.0 license"]) == "MPL-2.0"
    assert convert_to_spdx_license(["Mozilla Public License 2.0"]) == "MPL-2.0"

    # Creative Commons variants
    assert (
        convert_to_spdx_license(
            [
                "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International Public License"
            ]
        )
        == "CC-BY-NC-ND-4.0"
    )
    assert convert_to_spdx_license(["CC0"]) == "CC0-1.0"

    # Public Domain
    assert convert_to_spdx_license(["Public Domain"]) == "Unlicense"


def test_additional_license_variants():
    """Test additional license variants from real ROS packages."""
    # Apache variants
    assert convert_to_spdx_license(["Apache2"]) == "Apache-2.0"
    assert convert_to_spdx_license(["Apache2.0"]) == "Apache-2.0"

    # LGPL variants
    assert convert_to_spdx_license(["LGPLv2.1"]) == "LGPL-2.1-or-later"

    # Eclipse variants
    assert convert_to_spdx_license(["Eclipse Public License 2.0"]) == "EPL-2.0"
    assert (
        convert_to_spdx_license(["Eclipse Distribution License 1.0"]) == "BSD-3-Clause"
    )

    # Zlib
    assert convert_to_spdx_license(["zlib License"]) == "Zlib"

    # BSD variants
    assert convert_to_spdx_license(["3-Clause BSD"]) == "BSD-3-Clause"
    assert convert_to_spdx_license(["BSD License 2.0"]) == "BSD-2-Clause"

    # Creative Commons
    assert (
        convert_to_spdx_license(["Creative Commons Zero v1.0 Universal"]) == "CC0-1.0"
    )

    # GNU GPL
    assert (
        convert_to_spdx_license(["GNU General Public License v2.0"]) == "GPL-2.0-only"
    )
