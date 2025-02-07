/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public extension api.error {
    struct OrgNodeExists: AYSError {
        let path: String

        public var description: String {
            "Node organization (\(path)) exists. If this is your organization, and need help accessing your account, please call \(Global.phoneNumber)."
        }
    }
    struct NodeExists: AYSError {
        let path: String

        public var description: String {
            "Node (\(path)) exists."
        }
    }
    struct InvalidOrganization: AYSError {
        let path: String

        public var description: String {
            "Invalid organization (\(path)). An organization must be composed of only two parts. e.g. bithead.com, google.com, x.com, etc. If your host has more than two TLDs, please call \(Global.phoneNumber) to setup your account."
        }
    }
    struct TLDDoesNotExist: AYSError {
        let tld: String

        public var description: String {
            "The TLD (\(tld)) does not exist and must be created before your account can be created. Please call \(Global.phoneNumber) to have it created."
        }
    }
    struct InvalidParameter: AYSError {
        let name: String
        let expected: String?

        public init(name: String, expected: String? = nil) {
            self.name = name
            self.expected = expected
        }

        public var description: String {
            if let expected {
                "Invalid parameter value for (\(name)). Expected type (\(expected))."
            }
            else {
                "Invalid parameter value for (\(name))."
            }
        }
    }
    struct RequiredParameter: AYSError {
        let name: String

        public init(_ name: String) {
            self.name = name
        }

        public var description: String {
            "Parameter (\(name)) is required."
        }
    }
}
