/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

/**
 Resources
 Building routes: https://docs.vapor.codes/basics/routing/
 Client request, including auth: https://docs.vapor.codes/basics/client/
 Content: https://docs.vapor.codes/basics/content/

 Return a String with dictionary.
 app.get { req async throws in
     try await req.view.render("index", ["title": "Hello Vapor!"])
 }

 Rate-limit
 ```
 app.group(RateLimitMiddleware(requestsPerMinute: 5)) { rateLimited in
    rateLimited.get("slow-thing") { req in
        // ...
    }
 }
 ```

 Authentication groups
 ```
 app.post("login") { ... }
 let auth = app.grouped(AuthMiddleware())
 auth.get("dashboard") { ... }
 auth.get("logout") { ... }
 ```

 Redirection
 ```
 req.redirect(to: "/some/new/path")
 // Permanent redirect for SEO
 req.redirect(to: "/some/new/path", redirectType: .permanent)
 ```

 Respond w/ String
 ```
 app.get("hello") { req async -> String in
    "Hello, world!"
 }
 ```

 Register a controller.
 ```
 try app.register(collection: NodeController())
 ```
 
 Add headers
 ```
 app.get("hello") { _ -> Response in
     var headers = HTTPHeaders()
     headers.add(name: .contentType, value: "text/html")
     let html = "<html><body>Hello, world!</body></html>"
     return Response(status: .ok, headers: headers, body: .init(string: html))
 }
 ```
 */
