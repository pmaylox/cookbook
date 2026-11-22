# Alpha 0.2.3 validation

Completed in the local test environment:

| Suite | Result | Coverage |
|---|---:|---|
| Existing browser regression | 12 passed | 180 catalog entries, categories, search, favorites, CRUD, shopping list, backup import/export, print fallback, HTML escaping |
| Existing photo-scan integration | 8 passed | Camera/gallery inputs, simulated OCR, multiple-page text parsing, human review, failed OCR handling |
| New photo-storage integration | 8 passed | Staged pages, outside-localStorage storage, recipe references, thumbnail display, edit preservation, complete photo JSON export, restoration, corrupt-backup rejection |
| JavaScript syntax check (`node --check`) | passed | App's extracted inline JavaScript |
| Android project inspection | passed (static) | Asset HTML synced, app version/name, MediaStore save-path implementation, manifest, Gradle build workflow |

**Total:** 28 automated browser integration checks passed, plus JavaScript syntax validation.

**Important test caveat:** The headless browser test runner creates an opaque `about:blank` origin that denies real IndexedDB access. The photo-storage integration test injects an asynchronous IndexedDB **test double** to exercise the saving, retrieval and backup logic. Real Android WebView IndexedDB durability and MediaStore writes still require testing on a phone or emulator. The Android code has not been compiled into an APK here.

## Required phone test checklist

- [ ] Install a debug APK after a successful Android Studio/Actions build; verify app opens offline.
- [ ] Import an existing JSON backup and confirm the 180 catalog items and all personal recipes remain.
- [ ] Scan one printed card; check OCR, save, open the recipe, view its photo.
- [ ] Scan a double-sided handwritten card; attach two pages, review misread amounts, save.
- [ ] Inspect **Pictures/MyCookbook/Photos** in Samsung My Files or Gallery for the compressed copies.
- [ ] Export a full JSON backup with photos; restore it on a clean test installation (do not overwrite real data without a backup).
- [ ] Turn off Wi-Fi and verify saved text and photo views still work.
- [ ] Use Download photo from a recipe and confirm JPEG is saved through the system file picker.
- [ ] Confirm behavior on tablet and check available space with many recipe scans.

## Known limitations

- Automatic OneDrive/Google Drive photo upload is not implemented.
- Folder copies are best-effort; scanned attachments remain in IndexedDB if the phone Pictures copy fails.
- Original full-resolution camera files are not preserved by the app; it stores compressed copies.
- Deleting a recipe does not delete its already-copied files from user-visible Pictures.
- Native camera/Android build, installed APK and full MediaStore behavior are unverified.
