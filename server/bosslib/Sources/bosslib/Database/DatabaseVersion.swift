/// Copyright ⓒ 2023 Bithead LLC. All rights reserved.

enum DatabaseVersionError: Error {
    case invalidFormat(currentVersion: String, targetVersion: String)
    case nonNumericComponent(String)
}

protocol DatabaseVersion {
    var version: String { get }
    func update(_ session: Database.Session) async throws
}
