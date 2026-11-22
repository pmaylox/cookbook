package io.reddirtcode.cookbook;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.content.ClipData;
import android.provider.MediaStore;
import android.content.ContentValues;
import android.database.Cursor;
import android.os.Build;
import android.os.Environment;
import java.io.File;
import androidx.core.content.FileProvider;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import android.net.Uri;
import android.os.Bundle;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.text.TextUtils;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Offline-first Android container for the shipped, trusted Cookbook HTML.
 * Not a remotely hosted web app. External URLs are sent to the user's browser.
 * The only exposed bridge methods are document export, external URL launching,
 * and a native Print / Save-as-PDF dialog.
 */
public final class MainActivity extends Activity {
    private static final int CHOOSE_JSON = 101;
    private static final int SAVE_DOCUMENT = 102;
    private static final int CAPTURE_PHOTO = 103;
    private static final String APP_HOST = "appassets.androidplatform.net";

    private WebView cookbookView;
    private WebView printView;
    private android.webkit.ValueCallback<Uri[]> fileChooserCallback;
    private byte[] pendingDocument;
    private Uri cameraPhotoUri;
    private final java.util.concurrent.ExecutorService imageWorker =
            java.util.concurrent.Executors.newSingleThreadExecutor();

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(158, 59, 27));
        getWindow().setNavigationBarColor(Color.rgb(45, 48, 44));
        cookbookView = new WebView(this);
        setContentView(cookbookView);

        WebSettings settings = cookbookView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);  // required for the original myCookbook.v1 storage key
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true); // Android's own document picker returns content URIs
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        cookbookView.setBackgroundColor(Color.rgb(247, 244, 239));

        // Serves bundled static HTML on a safe https origin without network permission.
        final WebViewAssetLoader assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        cookbookView.setWebViewClient(new WebViewClientCompat() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return assetLoader.shouldInterceptRequest(req.getUrl());
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                Uri uri = req.getUrl();
                if (APP_HOST.equalsIgnoreCase(uri.getHost()) && uri.getPath() != null
                        && uri.getPath().startsWith("/assets/")) return false;
                openBrowser(uri.toString());
                return true;
            }
        });
        cookbookView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view,
                    android.webkit.ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
                fileChooserCallback = callback;
                String[] types = params.getAcceptTypes();
                boolean imageRequest = false;
                if (types != null) for (String type : types) {
                    if (type != null && type.toLowerCase(java.util.Locale.ROOT).contains("image")) {
                        imageRequest = true; break;
                    }
                }
                // <input capture=environment> uses the system camera app,
                // with a temporary private cache URI provided by FileProvider.
                if (imageRequest && params.isCaptureEnabled()) {
                    try {
                        File temp = File.createTempFile("recipe-photo-", ".jpg", getCacheDir());
                        cameraPhotoUri = FileProvider.getUriForFile(MainActivity.this,
                                getPackageName() + ".fileprovider", temp);
                        Intent take = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        take.putExtra(MediaStore.EXTRA_OUTPUT, cameraPhotoUri);
                        take.setClipData(ClipData.newRawUri("Recipe photo", cameraPhotoUri));
                        take.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivityForResult(take, CAPTURE_PHOTO);
                        return true;
                    } catch (Exception ex) {
                        cameraPhotoUri = null;
                        // Camera unavailable: let the user choose a saved photo instead.
                        showToast("Camera unavailable. Select a saved photo.");
                    }
                }
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType(imageRequest ? "image/*" : "application/json");
                try { startActivityForResult(pick, CHOOSE_JSON); }
                catch (ActivityNotFoundException ex) {
                    fileChooserCallback.onReceiveValue(null);
                    fileChooserCallback = null;
                    showToast("No photo or document picker is available");
                }
                return true;
            }
        });
        cookbookView.addJavascriptInterface(new CookbookBridge(), "CookbookAndroid");
        cookbookView.loadUrl("https://" + APP_HOST + "/assets/index.html");
    }

    // The app's only local page is trusted. Never inject this interface into external websites.
    private final class CookbookBridge {
        @JavascriptInterface public void openExternal(String url) {
            runOnUiThread(() -> openBrowser(url));
        }
        @JavascriptInterface public void saveBase64(String mime, String filename, String base64) {
            if (base64 == null || base64.length() > 40_000_000) {
                runOnUiThread(() -> showToast("File exceeds export size limit"));
                return;
            }
            final byte[] bytes;
            try { bytes = Base64.decode(base64, Base64.DEFAULT); }
            catch (IllegalArgumentException ex) {
                runOnUiThread(() -> showToast("Could not encode the backup"));
                return;
            }
            runOnUiThread(() -> {
                pendingDocument = bytes;
                Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                save.addCategory(Intent.CATEGORY_OPENABLE);
                save.setType("application/json".equals(mime) ? "application/json" :
                        "image/jpeg".equals(mime) ? "image/jpeg" : "application/octet-stream");
                String safeName = filename == null ? "my-cookbook-backup.json" :
                        filename.replaceAll("[^A-Za-z0-9._-]", "_");
                save.putExtra(Intent.EXTRA_TITLE, safeName);
                try { startActivityForResult(save, SAVE_DOCUMENT); }
                catch (ActivityNotFoundException ex) { pendingDocument = null; showToast("No save location available"); }
            });
        }
        // Writes a second, user-visible copy of the compressed photo. OCR and
        // the recipe attachment live in the app; this is the phone folder copy.
        @JavascriptInterface public void storeRecipePhoto(String photoId, String base64) {
            if (photoId == null || !photoId.matches("photo-[a-z0-9-]{7,55}")) return;
            if (base64 == null || base64.length() > 5_000_000) {
                reportPhotoCopy(photoId, false, "Photo exceeds copy limit"); return;
            }
            imageWorker.execute(() -> {
                Uri inserted = null;
                try {
                    byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                    if (bytes.length == 0 || bytes.length > 3_800_000)
                        throw new IllegalArgumentException("Photo too large");
                    // The Javascript app prepares JPEGs; verify JPEG magic bytes.
                    if (bytes.length < 4 || (bytes[0] & 0xff) != 0xff || (bytes[1] & 0xff) != 0xd8)
                        throw new IllegalArgumentException("Invalid JPEG photo");
                    if (Build.VERSION.SDK_INT >= 29) {
                        String name = "cookbook-" + photoId + ".jpg";
                        String directory = Environment.DIRECTORY_PICTURES + "/MyCookbook/Photos/";
                        try (Cursor cursor = getContentResolver().query(
                                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                                new String[]{MediaStore.Images.Media._ID},
                                MediaStore.Images.Media.DISPLAY_NAME + "=? AND " + MediaStore.Images.Media.RELATIVE_PATH + "=?",
                                new String[]{name, directory}, null)) {
                            if (cursor != null && cursor.moveToFirst()) {
                                reportPhotoCopy(photoId, true, "");
                                return; // Already copied during a previous backup restore.
                            }
                        }
                        ContentValues values = new ContentValues();
                        values.put(MediaStore.Images.Media.DISPLAY_NAME, "cookbook-" + photoId + ".jpg");
                        values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/MyCookbook/Photos");
                        values.put(MediaStore.Images.Media.IS_PENDING, 1);
                        inserted = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                        if (inserted == null) throw new IllegalStateException("Photo folder unavailable");
                        try (OutputStream stream = getContentResolver().openOutputStream(inserted, "w")) {
                            if (stream == null) throw new IllegalStateException("Cannot write photo");
                            stream.write(bytes);
                        }
                        ContentValues ready = new ContentValues();
                        ready.put(MediaStore.Images.Media.IS_PENDING, 0);
                        getContentResolver().update(inserted, ready, null, null);
                    } else {
                        // For Android 8/9, use the app-scoped external pictures dir.
                        File external = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
                        if (external == null) throw new IllegalStateException("External pictures unavailable");
                        File folder = new File(external, "MyCookbook/Photos");
                        if (!folder.isDirectory() && !folder.mkdirs()) throw new IllegalStateException("Cannot make photo folder");
                        try (OutputStream stream = new java.io.FileOutputStream(new File(folder, "cookbook-" + photoId + ".jpg"))) {
                            stream.write(bytes);
                        }
                    }
                    reportPhotoCopy(photoId, true, "");
                } catch (Exception ex) {
                    if (inserted != null) try { getContentResolver().delete(inserted, null, null); } catch (Exception ignored) {}
                    reportPhotoCopy(photoId, false, "Phone photo folder unavailable");
                }
            });
        }
        @JavascriptInterface public void scanImageBase64(String requestId, String imageBase64) {
            if (requestId == null || !requestId.matches("scan-[0-9]{1,15}")) return;
            if (imageBase64 == null || imageBase64.length() > 18_000_000) {
                sendScanResult(requestId, "", "Photo is too large. Try a smaller image.");
                return;
            }
            imageWorker.execute(() -> {
                try {
                    byte[] bytes = Base64.decode(imageBase64, Base64.DEFAULT);
                    Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                    if (bitmap == null) throw new IllegalArgumentException("Photo could not be read");
                    InputImage image = InputImage.fromBitmap(bitmap, 0);
                    com.google.mlkit.vision.text.TextRecognizer recognizer =
                            TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                    recognizer.process(image)
                            .addOnSuccessListener(text -> {
                                sendScanResult(requestId, text.getText(), "");
                                recognizer.close();
                                bitmap.recycle();
                            })
                            .addOnFailureListener(error -> {
                                sendScanResult(requestId, "", "Could not read this photo. Try taking it again.");
                                recognizer.close();
                                bitmap.recycle();
                            });
                } catch (Exception ex) {
                    sendScanResult(requestId, "", "The photo could not be scanned.");
                }
            });
        }
        @JavascriptInterface public void printRecipe(String recipeJson) {
            if (recipeJson == null || recipeJson.length() > 250_000) {
                runOnUiThread(() -> showToast("Recipe is too large to print"));
                return;
            }
            runOnUiThread(() -> printRecipeNative(recipeJson));
        }
    }

    private void reportPhotoCopy(String photoId, boolean success, String message) {
        String script = "window.CookbookPhotoStorage && window.CookbookPhotoStorage.photoCopyResult("
            + JSONObject.quote(photoId) + "," + success + "," + JSONObject.quote(message) + ")";
        runOnUiThread(() -> { if (cookbookView != null) cookbookView.evaluateJavascript(script, null); });
    }

    private void sendScanResult(String requestId, String text, String error) {
        final String script = "window.CookbookRecipeScan && window.CookbookRecipeScan.receive("
                + JSONObject.quote(requestId) + "," + JSONObject.quote(text) + ","
                + JSONObject.quote(error) + ")";
        runOnUiThread(() -> { if (cookbookView != null) cookbookView.evaluateJavascript(script, null); });
    }

    private void openBrowser(String rawUrl) {
        try {
            Uri uri = Uri.parse(rawUrl);
            String scheme = uri.getScheme();
            if (!"https".equalsIgnoreCase(scheme) && !"http".equalsIgnoreCase(scheme)) {
                showToast("Only website links can be opened"); return;
            }
            Intent intent = new Intent(Intent.ACTION_VIEW, uri);
            startActivity(intent);
        } catch (Exception ex) { showToast("Unable to open recipe website"); }
    }

    private void printRecipeNative(String rawJson) {
        try {
            JSONObject recipe = new JSONObject(rawJson);
            String title = recipe.optString("title", "My recipe");
            StringBuilder html = new StringBuilder(4096);
            html.append("<!doctype html><meta charset='utf-8'><style>")
                .append("body{font-family:serif;margin:36px;color:#222}h1{color:#9E3B1B;font-size:26px}")
                .append("h2{font:700 12px sans-serif;text-transform:uppercase;margin-top:24px}")
                .append("li{margin:0 0 10px;line-height:1.5}p{line-height:1.5}")
                .append("</style><h1>").append(escape(title)).append("</h1>");
            String sec = recipe.optString("section", "");
            if (!sec.isEmpty()) html.append("<p>").append(escape(sec)).append("</p>");
            String servings = recipe.optString("servings", "");
            if (!servings.isEmpty()) html.append("<p>Serves: ").append(escape(servings)).append("</p>");
            String time = recipe.optString("time", "");
            if (!time.isEmpty()) html.append("<p>Time: ").append(escape(time)).append("</p>");
            appendList(html, "Ingredients", recipe.optJSONArray("ingredients"), "ul");
            appendList(html, "Steps", recipe.optJSONArray("steps"), "ol");
            String notes = recipe.optString("notes", "");
            if (!notes.isEmpty()) html.append("<h2>Notes</h2><p>").append(escape(notes)).append("</p>");
            String source = recipe.optString("source", "");
            if (!source.isEmpty()) html.append("<h2>Source</h2><p>").append(escape(source)).append("</p>");
            if (printView != null) { printView.destroy(); printView = null; }
            printView = new WebView(this);
            printView.setWebViewClient(new WebViewClient() {
                @Override public void onPageFinished(WebView view, String ignoredUrl) {
                    PrintManager manager = (PrintManager) getSystemService(PRINT_SERVICE);
                    if (manager == null) { showToast("Print service unavailable"); return; }
                    manager.print("My Cookbook - " + title,
                            view.createPrintDocumentAdapter("My Cookbook"),
                            new PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.NA_LETTER).build());
                }
            });
            printView.loadDataWithBaseURL("https://" + APP_HOST + "/print/",
                    html.toString(), "text/html", "UTF-8", null);
        } catch (Exception ex) { showToast("Could not prepare recipe for PDF"); }
    }
    private static void appendList(StringBuilder html, String heading, JSONArray items, String kind) {
        if (items == null || items.length() == 0) return;
        html.append("<h2>").append(heading).append("</h2><").append(kind).append(">");
        for (int i = 0; i < items.length(); i++) {
            String text = items.optString(i, "").trim();
            if (!text.isEmpty()) html.append("<li>").append(escape(text)).append("</li>");
        }
        html.append("</").append(kind).append(">");
    }
    private static String escape(String s) {
        return TextUtils.htmlEncode(s).replace("\n", "<br>");
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent intent) {
        super.onActivityResult(requestCode, resultCode, intent);
        if (requestCode == CHOOSE_JSON) {
            if (fileChooserCallback != null) {
                Uri picked = resultCode == RESULT_OK && intent != null ? intent.getData() : null;
                fileChooserCallback.onReceiveValue(picked != null ? new Uri[]{picked} : null);
                fileChooserCallback = null;
            }
        } else if (requestCode == CAPTURE_PHOTO) {
            if (fileChooserCallback != null) {
                Uri picked = resultCode == RESULT_OK ? cameraPhotoUri : null;
                fileChooserCallback.onReceiveValue(picked == null ? null : new Uri[]{picked});
                fileChooserCallback = null;
            }
            cameraPhotoUri = null;
        } else if (requestCode == SAVE_DOCUMENT) {
            byte[] toSave = pendingDocument;
            pendingDocument = null;
            if (resultCode == RESULT_OK && intent != null && intent.getData() != null && toSave != null) {
                try (OutputStream output = getContentResolver().openOutputStream(intent.getData(), "w")) {
                    if (output == null) throw new IllegalStateException("No write stream");
                    output.write(toSave);
                    output.flush();
                    showToast("Cookbook backup saved");
                } catch (Exception ex) { showToast("Could not save the backup"); }
            }
        }
    }
    private void showToast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    @Override public void onBackPressed() {
        cookbookView.evaluateJavascript("!(document.getElementById('sheet')?.hidden ?? true)", result -> {
            if ("true".equals(result)) cookbookView.evaluateJavascript("closeSheet()", null);
            else MainActivity.super.onBackPressed();
        });
    }
    @Override protected void onDestroy() {
        imageWorker.shutdownNow();
        if (printView != null) { printView.destroy(); printView = null; }
        if (cookbookView != null) { cookbookView.destroy(); cookbookView = null; }
        super.onDestroy();
    }
}
