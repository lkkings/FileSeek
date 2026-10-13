mod autostart;
mod connection;
mod file_manager;
mod import_stream;
mod license;
mod lifecycle;
mod preview_protocol;
mod readiness;
mod runtime;
mod sidecar;
mod startup_args;
mod system_import;
mod system_integration;
mod tray;
mod update;

use std::path::Path;

use preview_protocol::{connection_file_path, PreviewTransportState};
use tauri::{Emitter, Manager, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let startup_intent = startup_args::parse(std::env::args());
    let startup_import = system_import::request_from_args(
        std::env::args(),
        &std::env::current_dir().unwrap_or_default(),
    );
    let pending_import = std::sync::Mutex::new(startup_import);
    let transport_state = PreviewTransportState {
        connection_file: Some(connection_file_path()),
    };
    let protocol_state = transport_state.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(
            |app, args, current_directory| {
                let request = system_import::request_from_args(args, Path::new(&current_directory));
                if request.is_none() {
                    tray::show_main_window(app);
                    return;
                }

                tray::show_main_window(app);
                let _ = app.emit(system_import::EVENT_NAME, request);
            },
        ))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        // App updates are signed by Keygate; its key comes from `keygate.json` through
        // `build.rs`, so `tauri.conf.json` carries none.
        .plugin(
            tauri_plugin_updater::Builder::new()
                .pubkey(env!("KEYGATE_UPDATER_PUBLIC_KEY"))
                .build(),
        )
        .manage(transport_state)
        .manage(pending_import)
        .invoke_handler(tauri::generate_handler![
            connection::api_request,
            readiness::get_readiness,
            readiness::retry_readiness,
            readiness::repair_runtime,
            tray::hide_to_tray,
            license::get_entitlement,
            license::activate_license,
            license::deactivate_license,
            license::recheck_license,
            license::open_library_folder,
            update::get_update_status,
            update::check_for_updates,
            update::download_update,
            update::cancel_update_download,
            update::install_update,
            import_stream::open_import_event_stream,
            system_integration::get_system_integration_status,
            system_integration::set_silent_startup,
            system_integration::set_file_manager_integration,
            system_import::take_pending_system_import
        ])
        .setup(move |app| {
            let mut config = readiness::config_for_app(app.path().resource_dir().ok());
            let config_dir = connection_file_path()
                .parent()
                .map(std::path::PathBuf::from)
                .unwrap_or_default();
            let licensing: license::SharedLicense =
                std::sync::Arc::new(license::LicenseService::for_app(&config_dir));
            // The launch check runs on the readiness thread, before anything is downloaded
            // or started; the UI hears its result like any other.
            config.license = {
                let licensing = licensing.clone();
                let handle = app.handle().clone();
                std::sync::Arc::new(move || {
                    let entitlement = licensing.check();
                    let _ = handle.emit(license::ENTITLEMENT_EVENT, &entitlement);
                    entitlement.is_licensed()
                })
            };
            license::start_checker(licensing.clone(), app.handle().clone());
            app.manage(licensing);
            let license_key: update::LicenseKey = {
                let licensing = app.state::<license::SharedLicense>().inner().clone();
                Box::new(move || {
                    licensing
                        .entitlement()
                        .is_licensed()
                        .then(|| licensing.license_key())
                        .flatten()
                })
            };
            let updates: update::SharedUpdates = std::sync::Arc::new(update::Updates::new(
                app.handle().clone(),
                config_dir.join("logs").join("update.log"),
                license_key,
                // Debug builds skip updates: `tauri dev` is never an installed copy.
                !cfg!(debug_assertions),
            ));
            update::start_checking(updates.clone());
            app.manage(updates);
            let handle = app.handle().clone();
            let mut notifier = readiness::ReadyNotifier::default();
            app.manage(readiness::Readiness::start(
                config,
                Box::new(move |snapshot| {
                    let _ = handle.emit(readiness::EVENT_NAME, snapshot);
                    if notifier.observe(snapshot.state) && !tray::main_window_visible(&handle) {
                        use tauri_plugin_notification::NotificationExt;
                        let _ = handle
                            .notification()
                            .builder()
                            .title("FileSeek")
                            .body("FileSeek 已就绪")
                            .show();
                    }
                }),
            ));
            tray::build(app.handle())?;
            if startup_args::visibility(&startup_intent) == startup_args::StartupVisibility::Hide {
                tray::set_hidden_activation_policy(app.handle());
            } else {
                tray::show_main_window(app.handle());
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if lifecycle::decide_close(window.label(), tray::MAIN_WINDOW)
                    == lifecycle::CloseDecision::HideToTray
                {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .register_uri_scheme_protocol("fileseek-preview", move |_context, request| {
            preview_protocol::handle_preview_request(&protocol_state, &request)
        })
        .build(tauri::generate_context!())
        .expect("error while building the tauri application")
        .run(|app, event| {
            // Quitting from the tray. Closing the window only hides it (above), so the
            // backend keeps working through the queue until the user really quits.
            if let tauri::RunEvent::Exit = event {
                // Longer than the backend's own stop grace, so the exit waits for it.
                app.state::<readiness::Readiness>()
                    .shutdown(sidecar::STOP_GRACE_PERIOD + std::time::Duration::from_secs(3));
            }
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen {
                has_visible_windows,
                ..
            } = event
            {
                if !has_visible_windows {
                    tray::show_main_window(app);
                }
            }
        });
}
