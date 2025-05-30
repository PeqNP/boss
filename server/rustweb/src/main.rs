use actix_web::{get, App, HttpServer, Responder};

#[get("/version")]
async fn version() -> impl Responder {
    // let name = path.into_inner();
    format!("unknown")
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(version)
    })
        .bind(("127.0.0.1", 8080))?
        .run()
        .await
}
