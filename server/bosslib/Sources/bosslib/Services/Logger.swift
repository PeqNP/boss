/// Copyright © 2020 Bithead LLC. All rights reserved.

import Foundation

public enum LogLevel: Int {
    case debug
    case info
    case warning
    case error
    case critical

    public static func < (a: LogLevel, b: LogLevel) -> Bool {
        return a.rawValue < b.rawValue
    }
}

public enum Severity: Int {
    case info
    case warning
    case error
}

struct LogEvent: AnalyticsEvent {
    let message: String
    let level: LogLevel
    let file: String
    let line: Int
}

public struct Logger {
    let name: String
    let format: String
    let level: LogLevel

    private func formatMessage(_ message: String, level: String, file: String, line: Int) -> String {
        format
            .replacingOccurrences(of: "%name", with: name)
            // Display file name only
            .replacingOccurrences(of: "%filename", with: URL(string: file)?.lastPathComponent ?? "")
            // Displays full path to file
            .replacingOccurrences(of: "%file", with: file)
            .replacingOccurrences(of: "%line", with: String(line))
            .replacingOccurrences(of: "%level", with: level)
            .replacingOccurrences(of: "%message", with: message)
    }

    public func d(_ message: String, file: String = #file, line: Int = #line) {
        guard level < .info else {
            return
        }
        print(formatMessage(message, level: "DEBUG", file: file, line: line))
    }

    public func i(_ message: String, file: String = #file, line: Int = #line) {
        guard level < .warning else {
            return
        }
        print(formatMessage(message, level: "INFO", file: file, line: line))
    }

    public func w(_ message: String, file: String = #file, line: Int = #line) {
        guard level < .error else {
            return
        }
        print(formatMessage(message, level: "WARNING", file: file, line: line))
    }

    public func e(_ message: String, file: String = #file, line: Int = #line) {
        guard level < .critical else {
            return
        }
        print(formatMessage(message, level: "ERROR", file: file, line: line))
    }
    public func e(_ error: Error, file: String = #file, line: Int = #line) {
        guard level < .critical else {
            return
        }
        print(formatMessage(error.localizedDescription, level: "ERROR", file: file, line: line))
    }

    public func c(_ message: String, file: String = #file, line: Int = #line) {
        print(formatMessage(message, level: "CRITICAL", file: file, line: line))
    }

    public func strongSelf(file: String = #file, line: Int = #line) {
        e("\(name) - Could not get reference to strong self", file: file, line: line)
    }

    public func nib(file: String = #file, line: Int = #line) {
        e("\(name) - Could not load nib", file: file, line: line)
    }
}
