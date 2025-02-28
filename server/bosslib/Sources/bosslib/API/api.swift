/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

private enum Constant {
    static let base36Characters = "0123456789abcdefghijklmnopqrstuvwxyz"
}

public enum api: Sendable {

    nonisolated(unsafe) private static var _version: String?

    public static func version() throws -> String {
        if let version = Self._version {
            return version
        }

        let path = repositoryPath()
        boss.log.i("Repository path (\(path.path()))")

        let task = Process()
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        task.standardInput = nil
        task.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        task.arguments = ["-C", path.path(), "log", "-1", "--date", "format:%Y.%m.%d", "--format=%ad %h"]
        try task.run()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let version = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) else {
            return "unknown"
        }

        Self._version = version
        return version
    }
}

public enum UserState {
    case unloaded(UserID)
    case loaded(User)
}

extension api {
    public enum error {
        final class AdminRequired: BOSSError { }
        final class InvalidConfiguration: BOSSError { }
        /// Use for all errors you want to mask to user
        final class ServerError: BOSSError { }
    }
    
    /// Resets all public APIs to use their default implementation
    static func reset() {
        api.account = AccountAPI()
        api.node = NodeAPI()
    }
}

/// Provides a way to replace an error returned from one system to another.
///
/// - Parameter expression: The expression to evaluate that may throw
/// - Parameter replaceWithError: The error to replace the originating `Error` with
/// - Returns: The same type returned from expression
@discardableResult
func call<T>(_ expression: @autoclosure () async throws -> T, file: String = #file, line: Int = #line, _ replaceWithError: @autoclosure () -> Error) async throws -> T {
    do {
        return try await expression()
    } catch {
        let replace = replaceWithError()
        boss.log.w("Error (\(error)) replaced w/ (\(replace))", file: file, line: line)
        throw replace
    }
}

/// Perform basic validation steps on an incoming string which includes:
/// 1. Stripping whitspace
/// 2. Ensuring string has a value
///
/// - Parameter value: The string to validate
/// - Parameter field: The field the value represents
/// - Returns: Trimmed string
/// - Throws: `ays.error.InvalidAccountInfo`
public func stringValue(_ value: String?, field: api.error.InvalidAccountInfo.Field) throws -> String {
    try stringValue(value, error: api.error.InvalidAccountInfo(field: field))
}

public func stringValue(_ value: String?, error: @autoclosure () -> Error) throws -> String {
    guard let value = stringValue(value) else {
        throw error()
    }
    return value
}

/// Returns a trimmed string value
///
/// - Parameter value: The string to get value for
/// - Returns: Trimmed string. If `nil`, or value is empty, `nil`.
public func stringValue(_ value: String?) -> String? {
    guard let value else {
        return nil
    }
    let trimmedValue = value.trimmingCharacters(in: .whitespacesAndNewlines)
    guard trimmedValue.count > 0 else {
        return nil
    }
    return trimmedValue
}

/// Create a user session token ID.
///
/// - Returns: `UserSession` `TokenID`
func makeTokenID() -> TokenID {
    makeUUID()
}

/// Create a verification code that can be used to verify a user's email address.
///
/// - Returns: Code, 6 letters long
func makeVerificationCode() -> VerificationCode {
    makeRandomCode(length: 6)
}

// MARK: - Private: Codes

/// Create a UUID with hyphens removed.
///
/// - Returns: UUID with hyphens removed
private func makeUUID() -> String {
    NSUUID().uuidString.replacingOccurrences(of: "-", with: "")
}

/// Make a random code of a specified length.
///
/// - Parameter length: The size of the code to make
/// - Returns: A random code of specified length
private func makeRandomCode(length: Int) -> String {
    let randomString = (0..<length).map { _ in Constant.base36Characters.randomElement() ?? "a" }
    return String(randomString)
}
