#----------------------------------------------------------------
# Generated CMake target import file for configuration "release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "pcre2::pcre2-8-shared" for configuration "release"
set_property(TARGET pcre2::pcre2-8-shared APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2-8-shared PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libpcre2-8.so.0.15.0"
  IMPORTED_SONAME_RELEASE "libpcre2-8.so.0"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2-8-shared )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2-8-shared "${_IMPORT_PREFIX}/lib/libpcre2-8.so.0.15.0" )

# Import target "pcre2::pcre2-posix-shared" for configuration "release"
set_property(TARGET pcre2::pcre2-posix-shared APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2-posix-shared PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libpcre2-posix.so.3.0.7"
  IMPORTED_SONAME_RELEASE "libpcre2-posix.so.3"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2-posix-shared )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2-posix-shared "${_IMPORT_PREFIX}/lib/libpcre2-posix.so.3.0.7" )

# Import target "pcre2::pcre2-16-shared" for configuration "release"
set_property(TARGET pcre2::pcre2-16-shared APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2-16-shared PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libpcre2-16.so.0.15.0"
  IMPORTED_SONAME_RELEASE "libpcre2-16.so.0"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2-16-shared )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2-16-shared "${_IMPORT_PREFIX}/lib/libpcre2-16.so.0.15.0" )

# Import target "pcre2::pcre2-32-shared" for configuration "release"
set_property(TARGET pcre2::pcre2-32-shared APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2-32-shared PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libpcre2-32.so.0.15.0"
  IMPORTED_SONAME_RELEASE "libpcre2-32.so.0"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2-32-shared )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2-32-shared "${_IMPORT_PREFIX}/lib/libpcre2-32.so.0.15.0" )

# Import target "pcre2::pcre2grep" for configuration "release"
set_property(TARGET pcre2::pcre2grep APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2grep PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pcre2grep"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2grep )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2grep "${_IMPORT_PREFIX}/bin/pcre2grep" )

# Import target "pcre2::pcre2test" for configuration "release"
set_property(TARGET pcre2::pcre2test APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(pcre2::pcre2test PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pcre2test"
  )

list(APPEND _cmake_import_check_targets pcre2::pcre2test )
list(APPEND _cmake_import_check_files_for_pcre2::pcre2test "${_IMPORT_PREFIX}/bin/pcre2test" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
