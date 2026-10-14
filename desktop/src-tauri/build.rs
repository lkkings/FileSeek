use std::path::Path;

/// The target triple, which keys the model source list (`runtime-sources/<target>.json`).
fn emit_runtime_target() {
    println!(
        "cargo:rustc-env=FILESEEK_RUNTIME_TARGET={}",
        std::env::var("TARGET").expect("cargo sets TARGET for build scripts")
    );
}

/// `tauri.conf.json` bundles `resources/backend/`, which `scripts/stage-backend.mjs`
/// fills with the compiled backend (`backend/build_nuitka.py`) during `pnpm build`. Dev
/// builds run the backend with `uv` from the checkout and never stage it, so the directory
/// may not exist; tauri-build refuses a missing resource path, so create it empty.
fn ensure_backend_resource_dir() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("resources/backend");
    std::fs::create_dir_all(dir).expect("could not create resources/backend");
}

/// The model files the first run downloads for this target (`release/build_sources.py`),
/// compiled into the app so their sha256s cannot be swapped after signing. A target with
/// no list gets an empty one, and the app reports the platform as unsupported.
fn emit_runtime_sources() {
    let target = std::env::var("TARGET").expect("cargo sets TARGET for build scripts");
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("runtime-sources");
    let path = dir.join(format!("{target}.json"));
    println!("cargo:rerun-if-changed={}", path.display());
    let path = if path.is_file() {
        path
    } else {
        let out = Path::new(&std::env::var("OUT_DIR").unwrap()).join("no-runtime-sources.json");
        std::fs::write(&out, "").unwrap();
        out
    };
    println!("cargo:rustc-env=FILESEEK_RUNTIME_SOURCES={}", path.display());
}

/// The Keygate server licenses come from, baked in as compile-time constants so an
/// installed app cannot be pointed elsewhere (`licensing-security`: build-time config).
///
/// Read from `keygate.json`; each field can be overridden by an environment variable of
/// the same name in upper case with a `KEYGATE_` prefix (`KEYGATE_BASE_URL`, ...), for CI.
/// `product_id` is the `pid` Keygate signs into tokens: a release build needs it, so a
/// token for another product on the same server is rejected; a debug build may leave it
/// empty and skips that check.
fn emit_keygate_config() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("keygate.json");
    println!("cargo:rerun-if-changed={}", path.display());
    let file: serde_json::Value = serde_json::from_slice(
        &std::fs::read(&path).expect("desktop/src-tauri/keygate.json is required to build"),
    )
    .expect("keygate.json is not valid JSON");
    let release = std::env::var("PROFILE").as_deref() == Ok("release");

    let field = |name: &str| {
        let env_name = format!("KEYGATE_{}", name.to_ascii_uppercase());
        println!("cargo:rerun-if-env-changed={env_name}");
        std::env::var(&env_name)
            .ok()
            .filter(|value| !value.trim().is_empty())
            .or_else(|| file[name].as_str().map(str::to_owned))
            .unwrap_or_default()
            .trim()
            .to_owned()
    };

    let base_url = field("base_url").trim_end_matches('/').to_owned();
    assert!(
        base_url.starts_with("https://") || (!release && base_url.starts_with("http://")),
        "keygate base_url must be an https URL, got {base_url:?}"
    );
    let slug = field("product_slug");
    assert!(!slug.is_empty(), "keygate product_slug is required");
    let key = field("license_public_key");
    assert!(
        key.len() == 64 && key.chars().all(|c| c.is_ascii_hexdigit()),
        "keygate license_public_key must be 32 bytes of hex (GET /api/v1/license/pubkey)"
    );
    // Keygate's "Public key for Tauri" (Signing tab): what app updates are signed with.
    let updater_key = field("updater_public_key");
    assert!(
        !release || !updater_key.is_empty(),
        "keygate updater_public_key is required for a release build"
    );
    let product_id = field("product_id");
    assert!(
        !release || !product_id.is_empty(),
        "keygate product_id is required for a release build (the `pid` in a token)"
    );

    println!("cargo:rustc-env=KEYGATE_BASE_URL={base_url}");
    println!("cargo:rustc-env=KEYGATE_PRODUCT_SLUG={slug}");
    println!("cargo:rustc-env=KEYGATE_PRODUCT_ID={product_id}");
    println!("cargo:rustc-env=KEYGATE_LICENSE_PUBLIC_KEY={key}");
    println!("cargo:rustc-env=KEYGATE_UPDATER_PUBLIC_KEY={updater_key}");
}

fn main() {
    emit_runtime_target();
    emit_runtime_sources();
    emit_keygate_config();
    ensure_backend_resource_dir();
    tauri_build::build()
}
