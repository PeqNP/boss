use thiserror::Error;

/// Errors that can occur when retrieving the version.
#[derive(Error, Debug)]
pub enum VersionError {
    #[error("failed to execute git command: {0}")]
    GitCommand(#[from] std::io::Error),
    #[error("failed to decode git output as UTF-8: {0}")]
    Utf8Decode(#[from] std::string::FromUtf8Error),
    #[error("mutex lock failed: {0}")]
    MutexLock(String),
}