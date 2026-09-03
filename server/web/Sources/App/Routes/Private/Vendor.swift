/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Smtp
import Vapor

/// Where a message leaves BOSS for a person.
///
/// A private service holds the rule about what to say and who to say it to. It
/// does not hold an account with a carrier, so it hands the message here and
/// this decides how it goes out.
protocol Vendor: Sendable {
    /// The name a service asks for this vendor by.
    var name: String { get }

    /// Deliver, or say why not.
    func send(_ message: VendorMessage, on req: Request) async throws -> VendorResult
}

/// One message, on whichever channel it was addressed to.
struct VendorMessage: Sendable {
    let to: String
    /// Empty on a channel that carries no subject, which is every one but email.
    let subject: String
    let body: String
}

/// What became of it.
struct VendorResult: Content {
    let sent: Bool
    /// Why nothing went out, when nothing did. Empty when something did.
    let reason: String
}

/// Email over the SMTP account BOSS already holds.
///
/// The same account the recovery mail goes out on. A separate one is a second
/// thing to configure and a second thing to be misconfigured.
struct SMTPVendor: Vendor {
    let name = "smtp"

    func send(_ message: VendorMessage, on req: Request) async throws -> VendorResult {
        guard boss.config.smtp.enabled else {
            return VendorResult(sent: false, reason: "SMTP is not configured")
        }
        let mail = try Email(
            from: EmailAddress(
                address: boss.config.smtp.senderEmail,
                name: boss.config.smtp.senderName
            ),
            to: [EmailAddress(address: message.to)],
            subject: message.subject,
            body: message.body
        )
        try await req.smtp.send(mail)
        boss.log.i("Sent email to (\(message.to))")
        return VendorResult(sent: true, reason: "")
    }
}

/// Every vendor there is, by the channel it serves.
///
/// A channel with nobody registered answers `sent: false` and says so, rather
/// than throwing: a business that has not arranged an SMS account is a
/// business whose confirmations do not go out by text, which is a state the
/// caller reports and not a failure of the call.
enum VendorRegistry {
    static let vendors: [String: [any Vendor]] = [
        "email": [SMTPVendor()],
        "sms": []
    ]

    /// The vendor to use for a channel, by name when one is asked for.
    static func vendor(for channel: String, named: String?) -> (any Vendor)? {
        let registered = vendors[channel] ?? []
        guard let named, !named.isEmpty else {
            return registered.first
        }
        return registered.first { $0.name == named }
    }
}

/// Register the vendor routes at `/private/vendor/`.
///
/// Called by a private service only, which is what the `/private` group means.
/// There is no OTP route here: a code's digits, its hash, when it expires and
/// how many attempts are left belong to the service that owns the appointment,
/// and it already has them. This layer carries a message and nothing else.
func registerVendor(_ group: RoutesBuilder) {
    group.group("vendor") { vendor in
        vendor.post(":channel", "send") { req -> VendorResult in
            let channel = req.parameters.get("channel") ?? ""
            let form = try req.content.decode(PrivateForm.SendMessage.self)

            guard VendorRegistry.vendors[channel] != nil else {
                return VendorResult(sent: false, reason: "There is no \(channel) channel")
            }
            guard let vendor = VendorRegistry.vendor(for: channel, named: form.vendor) else {
                return VendorResult(
                    sent: false,
                    reason: "No vendor is registered to send \(channel)"
                )
            }
            return try await vendor.send(
                VendorMessage(to: form.to, subject: form.subject ?? "", body: form.body),
                on: req
            )
        }.openAPI(
            summary: "Send a message on a channel",
            description: "Hand a message to whichever vendor serves this channel — `email` or `sms`. Answers `sent: false` with a reason when no vendor is registered, rather than failing: a channel nobody has arranged is a state to report. * Only available to private services.",
            body: .type(PrivateForm.SendMessage.self),
            contentType: .application(.json),
            response: .type(VendorResult.self),
            responseContentType: .application(.json)
        )
    }
}
