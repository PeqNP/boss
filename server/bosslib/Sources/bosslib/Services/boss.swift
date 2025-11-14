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
    let hmac_key: String
    /// e.g. `/base/dir`
    let db_path: String
    /// e.g. `/path/to/media-com.bithead`
    let media_path: String
    /// e.g. `https://bithead.io`
    let host: String
    let smtp_enabled: String
    /// e.g. `localhost`
    let smtp_host: String
    let smtp_port: String
    let smtp_username: String
    let smtp_password: String
    let smtp_sender_email: String
    let smtp_sender_name: String
    let phone_number: String
}

public struct Config {
    public struct Smtp {
        public let enabled: Bool
        public let host: String
        public let port: Int
        public let username: String
        public let password: String
        public let senderEmail: String
        public let senderName: String
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
    /// Your establishment's phone number. This is how users will contact you if an error occurs.
    public let phoneNumber: String
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
        guard let dbURL = URL(string: "file://\(config.db_path)") else {
            throw api.error.InvalidConfiguration()
        }
        guard let mediaURL = URL(string: "file://\(config.media_path)") else {
            throw api.error.InvalidConfiguration()
        }
        guard let smtpPort = Int(config.smtp_port) else {
            throw api.error.InvalidConfiguration()
        }

        Self._config = Config(
            hmacKey: config.hmac_key,
            databaseDirectory: dbURL,
            databasePath: dbURL.appending(component: "boss.sqlite3"),
            mediaPath: config.media_path,
            host: config.host,
            testMediaDirectory: mediaURL.appending(components: "upload", "io.bithead.test-manager", "media"),
            testMediaResourcePath: "/upload/io.bithead.test-manager/media",
            testDatabasePath: dbURL.appending(component: "test.sqlite3"),
            smtp: .init(
                enabled: config.smtp_enabled == "1",
                host: config.smtp_host,
                port: smtpPort,
                username: config.smtp_username,
                password: config.smtp_password,
                senderEmail: config.smtp_sender_email,
                senderName: config.smtp_sender_name
            ),
            phoneNumber: config.phone_number
        )

        // Order matters
        service.user = UserAPI(UserSQLiteService())
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
    homePath().appendingPathComponent("boss.sqlite3")
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
