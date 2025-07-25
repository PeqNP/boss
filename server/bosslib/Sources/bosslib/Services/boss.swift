/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
internal import Yams

public protocol BOSSError: Error, Equatable, CustomStringConvertible {
    var description: String { get }
}

extension BOSSError {
    public var description: String {
        String(describing: Self.self)
    }
    
    public static func ==(lhs: Self, rhs: Self) -> Bool {
        type(of: lhs) == type(of: rhs) &&
        lhs.description == rhs.description
    }
}

/// Provides a convenient way to create a new type of Error. The name is not great. I may change in the future.
final public class GenericError: BOSSError {
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

    public static func ==(lhs: GenericError, rhs: GenericError) -> Bool {
        lhs.message == rhs.message
    }
}

struct ConfigFile: Codable {
    enum CodingKeys: String, CodingKey {
        case hmacKey = "hmac_key"
        /// e.g. `/base/dir`
        case dbPath = "db_path"
        /// e.g. `/path/to/media-com.bithead`
        case mediaPath = "media_path"
        /// e.g. `https://bithead.io`
        case host = "host"
        /// e.g. `localhost`
        case smtpHost = "smtp_host"
        case smtpUsername = "smtp_username"
        case smtpPassword = "smtp_password"
    }
    
    let hmacKey: String
    let dbPath: String
    let mediaPath: String
    let host: String
    let smtpHost: String
    let smtpUsername: String?
    let smtpPassword: String?
}

public struct Config {
    public struct Smtp {
        let host: String
        let username: String?
        let password: String?
    }
    
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
    public let smtp: Smtp
}

public enum boss {
    
    nonisolated(unsafe) public static let log = Logger(
        name: "boss",
        format: "%name %filename:%line %level - %message",
        level: .info
    )
    
    private nonisolated(unsafe) static var _config: Config?
    public static var config: Config {
        guard let _config else {
            fatalError("BOSS has not been started")
        }
        return _config
    }

    /// Delete the BOSS database.
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
        let config = try bosslib.config()
        guard let dbURL = URL(string: "file://\(config.dbPath)") else {
            throw api.error.InvalidConfiguration()
        }
        guard let mediaURL = URL(string: "file://\(config.mediaPath)") else {
            throw api.error.InvalidConfiguration()
        }
        Self._config = Config(
            hmacKey: config.hmacKey,
            databaseDirectory: dbURL,
            // FIXME: Rename to `boss`. All production systems must rename database first.
            databasePath: dbURL.appending(component: "ays.sqlite3"),
            mediaPath: config.mediaPath,
            host: config.host,
            testMediaDirectory: mediaURL.appending(components: "upload", "io.bithead.test-manager", "media"),
            testMediaResourcePath: "/upload/io.bithead.test-manager/media",
            testDatabasePath: dbURL.appending(component: "test.sqlite3"),
            smtp: .init(
                host: config.smtpHost,
                username: config.smtpUsername,
                password: config.smtpPassword
            )
        )

        // Order matters
        service.user = UserService(UserSQLiteService())
        service.test = TestService(TestSQLiteService())
        
        api.reset()

        try await Database.start(storage: storage)
    }
}

// MARK: - Private: Path

func repositoryPath() -> URL {
    #if DEBUG
    homePath().appending(component: "source").appending(component: "boss")
    #else
    homePath().appending(component: "boss")
    #endif
}

private func databasePath() -> URL {
    // FIXME: Should be `boss.sqlite3`
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
    boss.log.i("Loading config file (\(file))")
    let contents = try String(contentsOf: file, encoding: .utf8)
    boss.log.i("Configuration ---")
    boss.log.i("\n\(contents.trimmingCharacters(in: .whitespacesAndNewlines))")
    boss.log.i("-----------------")
    let encoder = YAMLDecoder()
    return try encoder.decode(ConfigFile.self, from: contents.data(using: .utf8) ?? Data())
}
