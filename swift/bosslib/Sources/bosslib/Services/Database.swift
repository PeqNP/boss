/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

public class Database {
    public enum Storage: CustomStringConvertible {
        /// Use an in-memory database
        case memory
        /// Use a database at a specific location
        case file(URL)
        /// Stores the database, on disk, in a location decided by the API.
        /// For now, this is the home directory of the current user.
        case automatic
        
        public var description: String {
            switch self {
            case .memory:
                "in-memory"
            case .file(let url):
                "file (\(url))"
            case .automatic:
                "automatic"
            }
        }
    }

    /// Represents a `Connection` `Session`. This is necessary to get around constraints of default values not being able to `throw`. This creates, caches, and returns a connection that library functions can pass around and re-use.
    public class Session {
        private let pool: ConnectionPool
        private var connection: Connection?

        init(_ pool: ConnectionPool) {
            self.pool = pool
        }

        public func conn() async throws -> Connection {
            if let connection {
                return connection
            }
            let connection = try await pool.conn()
            self.connection = connection
            return connection
        }
    }

    class ConnectionPool {
        private let source: SQLiteConnectionSource
        private var connection: Connection?

        init(source: SQLiteConnectionSource) {
            self.source = source
        }

        func conn() async throws -> Connection {
            if let connection {
                return connection
            }
            let connection = try await Connection(source.makeConnection(
                logger: .init(label: "ays"),
                on: MultiThreadedEventLoopGroup.singleton.any()
            ).get())
            self.connection = connection
            return connection
        }
    }

    public class Connection {
        private let conn: SQLiteConnection

        // Number of times this connection has requested a transaction to begin.
        // This ensures BEGIN And COMMIT are called appropriately.
        private var transactions: Int = 0

        init(_ conn: SQLiteConnection) {
            self.conn = conn
        }

        deinit {
            close()
        }

        public func close() {
            _ = conn.close()
        }

        public func begin() async throws {
            guard transactions == 0 else {
                transactions += 1
                return
            }
            _ = try await conn.query("BEGIN EXCLUSIVE TRANSACTION")
            transactions = 1
        }

        public func rollback() async throws {
            // Only rollback if a transaction has been made
            guard transactions != 0 else {
                return
            }
            _ = try await conn.query("ROLLBACK")
            transactions = 0
        }

        public func commit() async throws {
            guard transactions != 0 else {
                throw service.error.TransactionNotStarted()
            }
            // Only commit if last matching commit has been made
            guard transactions == 1 else {
                transactions -= 1
                return
            }
            _ = try await conn.query("COMMIT TRANSACTION")
            transactions = 0
        }

        func sql() -> SQLDatabase {
            conn.sql()
        }

        func select() -> SQLSelectBuilder {
            conn.sql().select()
        }
        
        func query(_ query: String, _ binds: [SQLiteData], _ onRow: @escaping (SQLiteRow) -> Void) async throws {
            try await conn.query(query, binds, onRow)
        }
    }

    public static private(set) var current: Database = .init(storage: .memory)

    /// Start and connect the database.
    ///
    /// This must be called by the application who is using this library. Otherwise, the database will be an in-memory db only.
    /// - Parameter storage: The storage type
    /// - Throws: `AYSError`
    public static func start(storage: Storage) async throws {
        let db = Database(storage: storage)

        boss.log.i("Starting database (\(db.storage))")
        
        do {
            let conn = try await db.pool.conn()
            let rows = try await conn.select().column("version").from("versions").orderBy("id", .descending).limit(1).all()
            guard let row = rows.first else {
                throw service.error.DatabaseFailure("Database exists at (\(storage)) but is empty")
            }
            let version = try row.decode(column: "version", as: String.self)
            boss.log.i("Database version (\(version))")
        } catch let error as SQLiteError {
            // If this is a new database, it will have no tables. I wish there was a better way to test if this is a new database...
            // In all other contexts it's because the schema changed or some other unexpected error.
            guard error.message == "no such table: versions" else {
                throw service.error.DatabaseFailure("Unexpected SQL error (\(error))")
            }
            try await createDatabase(db: db)
        } catch {
            throw service.error.DatabaseFailure("Unexpected error (\(error))")
        }

        Self.current = db
    }
    
    /// Save the current state of the database as a snapshot.
    ///
    /// - Parameter name: The name of the snapshot
    public static func saveSnapshot(name: String) throws {
        let name = "\(name).sqlite3"
        boss.log.i("Saving database snapshot (\(name))")
        let file = boss.config.databaseDirectory.appendingPathComponent(name)
        try current.copy(to: file)
    }
    
    /// Loads and starts a database to a given snapshot.
    ///
    /// This copies the snapshot to `snapshot.sqlite3` before it is used. This ensures the snapshot database can be used on subsequent runs w/o its state being affected.
    ///
    /// - Parameter name: The name of the snapshot
    public static func loadSnapshot(name: String) async throws {
        let name = "\(name).sqlite3"
        boss.log.i("Loading database snapshot (\(name))")
        let snapshot = boss.config.databaseDirectory.appendingPathComponent(name)
        
        guard FileManager.default.fileExists(atPath: snapshot.relativePath) else {
            return boss.log.w("Attempting to copy snapshot that does not exist (\(snapshot))")
        }
        let dest = boss.config.databaseDirectory.appendingPathComponent("snapshot.sqlite3")
        // Remove previous snapshot, if necessary
        do {
            try FileManager.default.removeItem(at: dest)
        }
        try FileManager.default.copyItem(at: snapshot, to: dest)
        
        try await Database.start(storage: .file(dest))
    }

    public static func session() -> Database.Session {
        Self.current.session()
    }

    private let storage: Storage
    
    private var _pool: ConnectionPool?
    private var pool: ConnectionPool {
        if let _pool {
            return _pool
        }
        let pool = makePool()
        _pool = pool
        return pool
    }

    init(storage: Storage) {
        self.storage = storage
    }

    func session() -> Session {
        Session(pool)
    }

    func delete() async throws {
        switch storage {
        case .automatic:
            let  url = boss.config.databasePath
            if FileManager.default.fileExists(atPath: url.relativePath) {
                try FileManager.default.removeItem(at: url)
            } else {
                boss.log.w("Database does not exist at URL (\(url.relativePath))")
            }
        case let .file(url):
            if FileManager.default.fileExists(atPath: url.relativePath) {
                try FileManager.default.removeItem(at: url)
            } else {
                boss.log.w("Database does not exist at URL (\(url.relativePath))")
            }
        case .memory:
            break
        }
    }
    
    func copy(to destURL: URL) throws {
        let url: URL? = switch storage {
        case .memory:
            nil
        case .file(let url):
            url
        case .automatic:
            try boss.config.databasePath
        }
        guard let url else {
            return boss.log.w("Copying an in-memory database is not supported")
        }
        guard FileManager.default.fileExists(atPath: url.relativePath) else {
            return boss.log.w("Attempting to copy a database that does not yet exist at path (\(url))")
        }
        // Remove, if needed
        do {
            try FileManager.default.removeItem(at: destURL)
        }
        try FileManager.default.copyItem(at: url, to: destURL)
    }

    private func makePool() -> ConnectionPool {
        switch storage {
        case .automatic:
            let url = boss.config.databasePath
            boss.log.i("Automatic database @ (\(url))")
            return ConnectionPool(source: SQLiteConnectionSource(
                configuration: .init(
                    storage: .file(path: url.relativePath),
                    enableForeignKeys: true
                ),
                threadPool: .singleton
            ))
        case let .file(url):
            return ConnectionPool(source: SQLiteConnectionSource(
                configuration: .init(
                    storage: .file(path: url.relativePath),
                    enableForeignKeys: true
                ),
                threadPool: .singleton
            ))
        case .memory:
            return ConnectionPool(source: SQLiteConnectionSource(
                configuration: .init(
                    storage: .memory,
                    enableForeignKeys: true
                ),
                threadPool: .singleton
            ))
        }
    }
}

func encode<T: Encodable>(_ value: T?) throws -> SQLExpression {
    guard let value else {
        return SQLLiteral.null
    }
    return SQLBind(try JSONEncoder().encode(value))
}

func decode<T: Decodable>(_ value: Data, as type: T.Type) throws -> T {
    try JSONDecoder().decode(T.self, from: value)
}

/**
 Examples

 // drop table

 try await self.db.drop(table: "planets")
             .ifExists()
             .run()
 
 // create table

 try await self.db.create(table: "planets").ifNotExists()
     .column("id", type: .int, .primaryKey)
     .column("galaxyID", type: .int, .references("galaxies", "id"))
     .run()

 // index

 try await self.db.create(index: "test_index")
     .on("planets")
     .column("id")
     .unique()
     .run()

 // query all

 _ = try await self.db.select()
             .column("*")
             .from("galaxies")
             .where("name", .notEqual, SQLLiteral.null)
             .where { $0
                 .orWhere("name", .equal, SQLBind("Milky Way"))
                 .orWhere("name", .equal, SQLBind("Andromeda"))
             }
             .all()

 _ = try await self.db.select()
             .column("*")
             .from("galaxies")
             .where(SQLColumn("name"), .equal, SQLBind("Milky Way"))
             .groupBy("id")
             .orderBy("name", .descending)
             .all()

 // count

 try await self.db.select()
             .column(SQLFunction("count", args: "name"))
             .from("planets")
             .where("galaxyID", .equal, SQLBind(5))
             .run()

 try await self.db.select()
             .column(SQLFunction("count", args: SQLLiteral.all))
             .from("planets")
             .where("galaxyID", .equal, SQLBind(5))
             .run()

 // insert

 try await self.db.insert(into: "planets")
     .columns("id", "name")
     .values(SQLLiteral.null, SQLBind("Earth"))
     .run()

 try await self.db.insert(into: "planets")
     .columns("id", "name")
     .values(SQLLiteral.null, SQLBind("Mercury"))
     .values(SQLLiteral.null, SQLBind("Venus"))
     .values(SQLLiteral.null, SQLBind("Mars"))
     .values(SQLLiteral.null, SQLBind("Jpuiter"))
     .values(SQLLiteral.null, SQLBind("Pluto"))
     .run()
 */
