// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "boss",
    platforms: [
       .macOS(.v13)
    ],
    dependencies: [
        // @yslib framework
        .package(path: "../bosslib"),
        // 💧 A server-side Swift web framework.
        .package(url: "https://github.com/vapor/vapor.git", from: "4.99.3"),
        // 🗄 An ORM for SQL and NoSQL databases.
        .package(url: "https://github.com/vapor/leaf.git", from: "4.3.0"),
        // 🔵 Non-blocking, event-driven networking for Swift. Used for custom executors
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.76.1"),
        // Generate OpenAPI documentation from Vapor routes
        .package(url: "https://github.com/dankinsoid/VaporToOpenAPI.git", from: "4.6.6"),
    ],
    targets: [
        .executableTarget(
            name: "boss",
            dependencies: [
                .product(name: "bosslib", package: "bosslib"),
                .product(name: "Leaf", package: "leaf"),
                .product(name: "Vapor", package: "vapor"),
                .product(name: "NIOCore", package: "swift-nio"),
                .product(name: "NIOPosix", package: "swift-nio"),
                .product(name: "VaporToOpenAPI", package: "VaporToOpenAPI"),
            ],
            swiftSettings: swiftSettings
        ),
        .testTarget(
            name: "bossTests",
            dependencies: [
                .target(name: "boss"),
                .product(name: "XCTVapor", package: "vapor"),
            ],
            swiftSettings: swiftSettings
        )
    ]
)

var swiftSettings: [SwiftSetting] { [
    .enableUpcomingFeature("DisableOutwardActorInference"),
    .enableExperimentalFeature("StrictConcurrency"),
] }
