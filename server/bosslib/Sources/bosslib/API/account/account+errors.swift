/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public extension api.error {
    final class FailedToCreateJWT: BOSSError { }
    final class FailedToSendVerificationCode: BOSSError { }
    final class FailedToVerifyAccountCode: BOSSError { }
    final class InvalidJWT: BOSSError { }
    final class UserNotFoundInSessionStore: BOSSError { }
    final class UserSessionExpiredDueToInactivity: BOSSError { }
    final class InvalidMFA: BOSSError { }
    final class InvalidSlackCode: BOSSError { }
    final class InvalidVerificationCode: BOSSError { }
    // Attempting to verify MFA, but user does not have MFA enabled
    final class MFANotEnabled: BOSSError { }
    // User has MFA enabled, but TOTP secret is not configured -- should never happen
    final class MFANotConfigured: BOSSError { }
    // User attempted to sign in w/o MFA challenge proces (e.g. refer to signIn)
    final class MFARequired: BOSSError { }
    // User is attempting to access a resource before they have passed MFA challenge
    final class MFANotVerified: BOSSError { }
    final class NodeNotFound: BOSSError { }
    final class AccessError: BOSSError { }
    final class TOTPSecretRequired: BOSSError { }
    final class UserNotFound: BOSSError { }
    final class UserIsNotVerified: BOSSError { }
    final class UserIsVerified: BOSSError { }
    /// Account recovery is already in progress. You cannot create more than one active account recovery record.
    final class AccountRecoveryInProgress: BOSSError { }
    /// Account recovery code has already been used
    final class AccountAlreadyRecovered: BOSSError { }
    /// Account recovery code has expired
    final class AccountRecoveryCodeExpired: BOSSError { }
    
    // Any error related to the creation of a TOTP secret
    struct TOTPError: BOSSError {
        let message: String
        
        public var description: String {
            message
        }
        
        init(_ message: String) {
            self.message = message
        }
    }
    
    struct InvalidNode: BOSSError {
        let message: String
        
        public var description: String {
            message
        }
        
        init(_ message: String) {
            self.message = message
        }
    }

    struct InvalidAccountInfo: BOSSError {
        public enum Field: Equatable, CustomStringConvertible, Sendable {
            case email
            case fullName
            case orgPath
            case password

            public var description: String {
                switch self {
                case .email:
                    "Email"
                case .fullName:
                    "Full name"
                case .orgPath:
                    "Organization path"
                case .password:
                    "Password"
                }
            }
        }

        public let field: Field

        public init(field: Field) {
            self.field = field
        }

        public var description: String {
            "Please provide a value for field (\(field))."
        }
    }
}
