use actix_web::{get, App, HttpServer, Responder};

use web::configure_app;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Initialize any app-wide setup here if needed
    // e.g., api::initialize(); // If you add an init function later

    HttpServer::new(|| {
        App::new()
            .configure(web::configure_app)
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}