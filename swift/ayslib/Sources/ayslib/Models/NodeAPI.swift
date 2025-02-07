/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public struct NodeInterface: Equatable {
    public struct Func: Equatable {
        public enum Owner: Equatable {
            case me
            case template(ShallowNode)
            case unknown
        }
        public struct DataSource: Equatable {
            public let name: String
            public let description: String
        }
        public struct Parameter: Equatable {
            public enum Value: Equatable {
                case property(String)
                case key(Int)
                case globalKey(Int)
                case dataSource(DataSource)
            }
            public let type: Script.Parameter.`Type`
            public let name: String
            public let value: Func.Parameter.Value?
        }

        public let owner: Func.Owner
        public let parameters: [Func.Parameter]
        public let name: String // Displayable name
        public let functionName: String
    }

    public struct Options: Equatable {
        public struct Option: Equatable {
            public let name: String
            public let value: String
        }

        // NodeAPIFunc.Parameter.name
        public let name: String
        public let options: [Options.Option]
    }

    public enum Response {
        public struct Log {
            let level: AlertingLevel
            let message: String
        }
        public struct Status {
            let currentJob: Int
            let totalJobs: Int
            let message: String
        }

        case log(Response.Log)
        case status(Response.Status)
        case error(String)
        case finished
    }

    public let language: Script.Language
    public let source: String
    public let funcs: [Func]
}

