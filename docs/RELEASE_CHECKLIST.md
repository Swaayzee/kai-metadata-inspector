# 2.0 release checklist

## Automated gates

- [x] Syntax and Ruff checks
- [x] Core tests
- [x] Headless GUI construction test
- [x] Real ExifTool GPS/clean integration test
- [x] Local frozen-app diagnostics
- [x] Local AppDir assembly validation
- [ ] Windows native workflow
- [ ] macOS Intel native workflow
- [ ] macOS Apple Silicon native workflow
- [ ] Linux x86_64 AppImage workflow

## Manual gates

- [ ] Complete the native matrix in `docs/TESTING.md`
- [ ] Add final `.ico` and `.icns` assets
- [ ] Configure Windows code signing
- [ ] Configure Apple Developer ID signing and notarization
- [ ] Publish SHA-256 checksums
- [ ] Create GitHub 2.0 release notes
