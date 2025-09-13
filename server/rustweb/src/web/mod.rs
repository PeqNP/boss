mod api;
use crate::api;

use actix_web::{web, App, HttpResponse, Responder};
//use boss::api;

/// Configures the Actix Web application with all endpoints.
///
/// This function sets up the app with services, scopes, and routes.
/// It also injects the API services where needed (e.g., for data access).
///
/// # Example
/// ```
/// let app = configure_app(App::new());
/// ```
pub fn configure_app(cfg: &mut web::ServiceConfig) {
    cfg
        .service(
            web::scope("/api")
                .route("/version", web::get().to(version_handler))
        )
        .service(
            web::scope("/auth")
                .route("/sign-in", web::get().to(sign_in_handler))
        );
}

/// Handler for the /api/version endpoint.
///
/// Fetches the version from the API module and returns it as JSON.
async fn version_handler() -> impl Responder {
    match api::version() {
        Ok(version) => HttpResponse::Ok().json(serde_json::json!({ "version": version })),
        Err(_) => HttpResponse::InternalServerError().json(serde_json::json!({ "error": "Failed to get version" })),
    }
}

/// Handler for the /api/auth/sign-in endpoint.
///
/// Example handler that uses the authentication service.
async fn sign_in_handler() -> impl Responder {
    // Access the singleton API
    let auth = &api::api().auth;
    auth.sign_in(); // TODO: Send params

    HttpResponse::Ok().json(serde_json::json!({ "message": "Signed in" }))
}

// Add more handlers as needed, e.g., for users, etc.