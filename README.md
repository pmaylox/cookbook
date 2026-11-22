# My Cookbook — Alpha 0.2.3: saved recipe photos

**Red Dirt Code™ • Product #2**

This update builds on the user's Alpha 0.2.2 photo-scanning app. The original uploaded Claude HTML is preserved unchanged as `archive/original-claude-upload.html`.

## What's new

- **Photo attachments:** Scanned recipe-card and cookbook-page photos are attached to the recipe when you press **Save recipe**, not merely used for OCR and discarded.
- **Organized Android copies:** After the recipe saves, Android 10+ code writes JPEG copies to the phone's **Pictures/MyCookbook/Photos** through the Android MediaStore API. Duplicate filenames are checked during backup restore. Older Android 8/9 versions fall back to an app-specific external pictures directory.
- **Compression:** Images are resized to at most 2,200 px on the longer side and converted to JPEG at 78% quality before being stored. This is intended for legibility and moderate storage, **not an archival lossless copy**. Preserve the original camera file for archival-quality images.
- **Recipe history:** Open a saved recipe to see the attached scan pages and download individual photo copies. Editing a recipe retains its existing photo references.
- **Multi-page capture:** Up to 8 recipe photos per recipe. You can remove a staged photo before saving.
- **Storage separation:** Text, favorites, and shopping data retain the existing `myCookbook.v1` localStorage key. Scanned compressed photos live in separate IndexedDB storage, reducing the risk of filling the small localStorage quota.
- **Full backups:** `Backup and restore` now exports a **full JSON backup including scanned photo bytes and their recipe associations**. Older version-1 text-only backups remain compatible. A damaged backup that refers to a missing photo is rejected before replacing existing recipe data. Full backups have a 24 MB limit.
- **Browser folder option:** On browsers that support the File System Access API, choose a directory under Backup and restore to save copies of **future** scans inside `MyCookbook/Photos`. Folder selection does not automatically persist between sessions. If unsupported, use a saved recipe's **Download photo** button.

## What happens on Android

1. Add recipe → Scan a recipe photo → Take photo / Choose photo.
2. Scan one or more pages, check the OCR text, and tap Auto-fill recipe fields.
3. Review and correct the form. Tap **Save recipe**.
4. The recipe links to the compressed images stored in the app's IndexedDB. Android separately writes a copy to **Pictures/MyCookbook/Photos** (on Android 10+). On failures, the recipe photo is still attached and an error appears; you can manually export it.
5. Open the recipe to view or download saved pages. In Backup and restore, export a **Full JSON backup with photos** before reinstalling or changing phones.

> **No automatic cloud sync.** OneDrive/Google Drive are only involved if you save the full backup into a cloud-backed folder with Android's file picker. Photos are not automatically synced or uploaded to cloud services.

## Device data and limitations

- The in-app photo collection and the user-visible Pictures folder are separate copies. A copied folder alone does not restore the cookbook's database; use the full JSON backup for that.
- Photos copied to Pictures remain in that folder even if you delete a recipe; the app does not automatically remove user-visible copies.
- Browser HTML launched from `file://` or a Downloads preview may lack working IndexedDB. Use a normal secure browser origin or the compiled Android app for real photo persistence.
- Android photo-folder writes, camera capture, MediaStore visibility and actual on-device ML Kit recognition are **not yet verified on a physical device**. The Android project is source code, not an APK.
- The original 180-entry catalog is unchanged and may contain original Gmail thread IDs. Do not publish source openly without reviewing that metadata. Use a **private** GitHub repository for the build pipeline.

## Files

- `my-cookbook-alpha-0.2.3.html`: full browser HTML.
- `app/`, with Gradle config at repo root: native Android WebView container, ML Kit OCR integration and MediaStore photo copies. Android application ID stays `io.reddirtcode.cookbook`, version name `0.2.3-alpha`.
- `tests/`: existing browser regressions and new photo storage/restore integration suite.
- `TEST_RESULTS.md`: automated tests and remaining device validation.
- `archive/original-claude-upload.html`: exact original upload, unchanged.

## Build Android APK

Install Android Studio with Android SDK 36 and JDK 17, open the repository root, sync Gradle, then select **Build → Build APK(s)**. On success, the debug APK is `app/build/outputs/apk/debug/app-debug.apk`. Alternatively, copy this project into a **private** GitHub repository and run the provided Actions workflow. Neither path was executed in this environment.

**Before installing on an existing device:** export the current cookbook's JSON backup. The same Android application ID is retained, but HTML/browser installations and APK installations do not automatically share data.