// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "bosslib",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .library(name: "bosslib", targets: ["bosslib"]),
    ],
    dependencies: [
        .package(url: "https://github.com/vapor/jwt-kit", from: "4.3.13"),
        .package(url: "https://github.com/vapor/sqlite-kit", from: "4.5.2"),
        .package(url: "https://github.com/PeqNP/Yams.git", from: "5.1.4"),
        .package(url: "https://github.com/pointfreeco/swift-custom-dump", from: "1.0.0"),
    ],
    targets: [
        .target(name: "CBcrypt"),
        .target(
            name: "bosslib",
            dependencies: [
                .target(name: "CBcrypt"),
                .product(name: "JWTKit", package: "jwt-kit"),
                .product(name: "SQLiteKit", package: "sqlite-kit"),
                .product(name: "Yams", package: "Yams"),
            ]
        ),

        // Testing
        .testTarget(
            name: "bosslibTests",
            dependencies: [
                .target(name: "bosslib"),
                .product(name: "CustomDump", package: "swift-custom-dump"),
            ]
        ),
    ]
)
