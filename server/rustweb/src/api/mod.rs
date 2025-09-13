
// src/api/mod.rs

use once_cell::sync::Lazy;
use std::sync::Mutex;

mod auth;  // Declares the auth submodule
pub use auth::AuthenticationService;  // Re-export if needed, but not necessary for internal use

pub mod errors;

use crate::api::errors::VersionError;

static VERSION: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));

/// Retrieves the current version of the server based on the latest git commit hash and date.
///
/// This function executes a `git log` command to fetch the latest commit date (formatted as YYYY.MM.DD)
/// and short hash. The result is cached for subsequent calls. If the command fails or the output
/// cannot be processed, it returns "unknown".
///
/// # Returns
/// A `Result` containing the version string or a `VersionError` if an error occurs.
///
/// # Example
/// ```
/// use boss::api::version;
/// let version = version().expect("Failed to get version");
/// println!("Version: {}", version);
/// ```
pub fn version() -> Result<String, VersionError> {
    // Check if version is cached
    {
        let version_guard = VERSION
            .lock()
            .map_err(|e| VersionError::MutexLock(format!("Mutex lock failed: {}", e)))?;
        if let Some(version) = version_guard.as_ref() {
            return Ok(version.clone());
        }
    }

    // Get repository path
    let path = repository_path();
    println!("Repository path: {:?}", path);

    // Execute git command
    let output = std::process::Command::new("/usr/bin/git")
        .arg("-C")
        .arg(path)
        .args(["log", "-1", "--date", "format:%Y.%m.%d", "--format=%ad %h"])
        .output()
        .map_err(VersionError::GitCommand)?;

    // Check if the command was successful
    if !output.status.success() {
        return Ok("unknown".to_string());
    }

    // Convert output to string and trim
    let version = String::from_utf8(output.stdout)
        .map_err(VersionError::Utf8Decode)?
        .trim()
        .to_string();

    // Cache the version
    {
        let mut version_guard = VERSION
            .lock()
            .map_err(|e| VersionError::MutexLock(format!("Mutex lock failed: {}", e)))?;
        *version_guard = Some(version.clone());
    }

    Ok(version)
}

/// Returns the path to the git repository.
///
/// This is a placeholder function; implement it based on your specific needs.
fn repository_path() -> std::path::PathBuf {
    std::path::PathBuf::from(".")
}

// Define the top-level Api struct to hold all services as fields
#[derive(Debug)]
pub struct Api {
    pub auth: auth::AuthenticationService,
    // Add more services here, e.g., pub user: user::UserService,
}

// Singleton getter for the Api instance
static API: Lazy<Api> = Lazy::new(|| {
    Api {
        auth: auth::AuthenticationService::new(),
        // Initialize other services here
    }
});

/// Returns a reference to the singleton Api instance.
///
/// This provides access to all services in a namespaced way, e.g., api().auth.sign_in().
///
/// # Example
/// ```
/// use boss::api::api;
/// api().auth.sign_in();
/// ```
pub fn api() -> &'static Api {
    &API
}