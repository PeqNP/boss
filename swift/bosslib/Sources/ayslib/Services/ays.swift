/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
internal import Yams

public protocol AYSError: Error, Equatable, CustomStringConvertible { }

struct ConfigFile: Codable {
    enum CodingKeys: String, CodingKey {
        case hmacKey = "hmac_key"
        /// e.g. `/base/dir`
        case dbPath = "db_path"
        /// e.g. `/path/to/media-com.bithead`
        case mediaPath = "media_path"
        /// e.g. `https://bithead.io`
        case host = "host"
    }
    
    let hmacKey: String
    let dbPath: String
    let mediaPath: String
    let host: String
}

public struct Config {
    public let hmacKey: String
    public let databaseDirectory: URL
    public let databasePath: URL
    /// /path/to/media-com.bithead
    public let mediaPath: String
    public let host: String
    /// Returns the full path on disk to the "test/media" directory
    public let testMediaDirectory: URL
    public let testMediaResourcePath: String
    public let testDatabasePath: URL
}

public enum ays {
    open class Error: AYSError {
        public let message: String?

        public var description: String {
            #if DEBUG
            if let message {
                "\(String(describing: Self.self))(\(message))"
            }
            else {
                String(describing: Self.self)
            }
            #else
            message ?? String(describing: Self.self)
            #endif
        }

        public init(_ message: String? = nil) {
            self.message = message
        }

        public static func ==(lhs: ays.Error, rhs: ays.Error) -> Bool {
            type(of: lhs) == type(of: rhs) &&
            lhs.message == rhs.message
        }
    }
    
    private static var _config: Config?
    public static var config: Config {
        guard let _config else {
            fatalError("ays has not been started")
        }
        return _config
    }

    /// Reset all services to not have an implementation.
    ///
    /// Used only for testing.
    static func reset() {
        service.node = NodeService()
        service.user = UserService()
        service.test = TestService()
        
        api.reset()
    }

    /// Delete the ays database.
    ///
    /// This should only be performed during testing! This works only in DEBUG mode.
    public static func deleteDatabase(storage: Database.Storage) async throws {
        #if DEBUG
        try await Database(storage: storage).delete()
        #endif
    }
    
    public static func saveSnapshot(name: String) throws {
        try Database.saveSnapshot(name: name)
    }
    
    public static func loadSnapshot(name: String) async throws {
        try await Database.loadSnapshot(name: name)
    }

    /// Start the services.
    ///
    /// - Parameter databaseUrl: The path to the database
    /// - Throws
    public static func start(storage: Database.Storage) async throws {        
        let config = try ayslib.config()
        guard let dbURL = URL(string: "file://\(config.dbPath)") else {
            throw api.error.InvalidConfiguration("Invalid db_path")
        }
        guard let mediaURL = URL(string: "file://\(config.mediaPath)") else {
            throw api.error.InvalidConfiguration("Invalid media_path")
        }
        Self._config = Config(
            hmacKey: config.hmacKey,
            databaseDirectory: dbURL,
            databasePath: dbURL.appending(component: "ays.sqlite3"),
            mediaPath: config.mediaPath,
            host: config.host,
            testMediaDirectory: mediaURL.appending(components: "upload", "io.bithead.test-manager", "media"),
            testMediaResourcePath: "/upload/io.bithead.test-manager/media",
            testDatabasePath: dbURL.appending(component: "test.sqlite3")
        )

        // Order matters
        service.node = NodeService(NodeSQLiteService())
        service.user = UserService(UserSQLiteService())
        service.test = TestService(TestSQLiteService())

        try await Database.start(storage: storage)
    }
}

// MARK: - Private: Path

func repositoryPath() -> URL {
    #if DEBUG
    homePath().appending(component: "source").appending(component: "ays-server")
    #else
    homePath().appending(component: "ays-server")
    #endif
}

private func databasePath() -> URL {
    homePath().appendingPathComponent("ays.sqlite3")
}

private func homePath() -> URL {
    FileManager.default.homeDirectoryForCurrentUser
}

private func configBasePath() -> URL {
    homePath().appending(component: ".boss")
}

private func configPath() -> URL {
    configBasePath().appending(component: "config")
}

private func config() throws -> ConfigFile {
    let file = configPath()
    log.i("Loading config file (\(file))")
    let contents = try String(contentsOf: file, encoding: .utf8)
    log.i("Configuration ---")
    log.i("\n\(contents.trimmingCharacters(in: .whitespacesAndNewlines))")
    log.i("-----------------")
    let encoder = YAMLDecoder()
    return try encoder.decode(ConfigFile.self, from: contents.data(using: .utf8) ?? Data())
}
