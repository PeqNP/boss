/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public struct VirtualNode: Codable {
    public let name: String
    public let value: Double
}

public struct VirtualElderNode: Codable {
    public let name: String
    public let values: [Double]
}

public struct Script: Equatable, Codable {
    public enum Ownership: Equatable, Codable, Sendable {
        case unknown
        case owner
        case reference(nodeId: String, nodePath: String)
        case sibling(measurementId: String, measurementName: String)
        case siblingReference(nodeId: String, nodePath: String, measurementId: String, measurementName: String)

        public static let `default`: Script.Ownership = .owner
    }
    public enum Language: String, CaseIterable, Codable, Equatable, Sendable {
        case erlang
        case go
        case javascript
        case lua
        case perl
        case php
        case python
        case ruby
        case rust
        case shell
        case swift

       public static let `default`: Script.Language = .python
    }
    public struct Parameter: Equatable, Codable {
        public enum `Type`: Equatable, Codable {
            case string
            case int
            case boolean
            case double
        }
        public var id: String? // `nil` means it is a new Parameter
        public let name: String
        public let type: Parameter.`Type`
    }
    public enum ReturnValue: Equatable, Codable, Sendable {
        case unknown
        case single(name: String)
        case multiple(names: [String])
        case virtualNodes
        case virtualElder

        public static let `default`: Script.ReturnValue = .single(name: "not_set")
    }

    public var ownership: Ownership
    public var parameters: [Parameter]
    public var returns: ReturnValue
    public var language: Script.Language
    public var text: String
}

extension Script.Language {
    public var toString: String {
        switch self {
        case .erlang:
            return "Erlang"
        case .go:
            return "Go"
        case .javascript:
            return "JavaScript"
        case .lua:
            return "Lua"
        case .perl:
            return "Perl"
        case .php:
            return "PHP"
        case .python:
            return "Python"
        case .ruby:
            return "Ruby"
        case .rust:
            return "Rust"
        case .shell:
            return "shell"
        case .swift:
            return "Swift"
        }
    }
}

extension Script.ReturnValue {
    public var toString: String {
        switch self {
        case .unknown:
            return "unknown"
        case .multiple(let names):
            return "multiple(\(names.joined(separator: ", ")))"
        case .single(let name):
            return "single(\(name))"
        case .virtualNodes:
            return "virtual nodes"
        case .virtualElder:
            return "virtual elder"
        }
    }
}

extension Script.Parameter.`Type` {
    public var toString: String {
        switch self {
        case .boolean:
            return "bool"
        case .double:
            return "float"
        case .int:
            return "int"
        case .string:
            return "str"
        }
    }
}

public struct ExecutedScript {
    public enum Status {
        case success
        case failure(String)
    }

    public let status: ExecutedScript.Status
    public let returnValue: ScriptRunnerEvent.ReturnValue
    public let elapsedTime: Double
    public let logs: [String]
}

// Represents a CLI script that can be executed on the @ys server
public struct CLIScript {
    public let name: String
    public let parameters: [String]
}

public struct CLIResult {
    public let statusCode: Int
    public let output: String
}
