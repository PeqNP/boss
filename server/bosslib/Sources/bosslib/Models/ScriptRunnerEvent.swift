/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public enum ScriptRunnerEvent {
    public enum LogLevel {
        case debug
        case warning
        case error
    }

    public enum ReturnValue {
        case single(name: String, value: Double)
        case multiple(names: [String], values: [Double])
        case virtualNodes([VirtualNode])
        case virtualElder(names: [String], nodes: [VirtualElderNode])
    }

    public struct Parameter {
        public enum `Type` {
            case string
            case int
        }

        let name: String
        let type: ScriptRunnerEvent.Parameter.`Type`
    }

    // A command that was run on the server
    case command(script: String, parameters: [ScriptRunnerEvent.Parameter])
    // A console log message. Usually provided by the script that was just executed.
    case log(level: ScriptRunnerEvent.LogLevel, message: String)
    // Interface of the script
    case interface(parameters: [Script.Parameter], returns: Script.ReturnValue)
    // The response returned from the script after executing it
    case response(ReturnValue, elapsedTime: Double)
    // Signal to indicate that the script finished executing
    case finished
    // Cancel signal acknowledged by server. This is sent only after a script was cancelled. It can be assumed that the "cancel signal" was initiated by the client, but it can also be related to the server terminating the process i.e. a system reboot
    case cancelled
    // List of available (admin) CLIScripts
    case scriptList([CLIScript])
    // The result of executing a CLIScript
    case scriptResult(CLIResult)
    // The Node API interfaces
    case nodeApi(NodeInterface, [NodeInterface.Options])
    // Node API options
    case nodeApiOptions([NodeInterface.Options])
    // Updates status of an operation
    case status(min: Int, max: Int, message: String)
}
