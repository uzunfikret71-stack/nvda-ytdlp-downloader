# GitHub Actions

Pushes to main, pull requests and Actions > Build add-on > Run workflow build an add-on package. Download the package and SHA-256 file from the nvda-addon artifact.

For a release, update the manifest version (buildVars.py for Media Converter) and release notes, then push a matching vX.Y.Z tag. A successful build creates a draft Release. Publish it after real NVDA testing. Existing releases and assets are never overwritten.

scripts/ci_build.py downloads missing binaries from a fixed existing release and verifies the pinned SHA-256 before extraction. To update binaries, explicitly update that URL and checksum. Media Converter runs unit and FFmpeg integration tests on Windows after preparing these verified binaries; the downloader checks Python syntax and package integrity without executing the binaries.

This workflow does not update installed add-ons or submit anything to the NVDA Add-on Store. Manual NVDA installation, upgrade and accessibility testing is still required. Add-on versions, NVDA compatibility metadata and keyboard shortcuts have not changed.