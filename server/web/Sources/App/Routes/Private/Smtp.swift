/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Smtp
import Vapor

/// What became of a private SMTP send.
struct SmtpSendResult: Content {
    let sent: Bool
    /// Why nothing went out, when nothing did. Empty when something did.
    let reason: String
}

/// Register SMTP at `/private/smtp/`.
///
/// BOSS already holds the SMTP account. A private service that chose SMTP as
/// its mail vendor hands the message here rather than opening its own session.
func registerSmtp(_ group: RoutesBuilder) {
    group.group("smtp") { smtp in
        smtp.post("send") { req -> SmtpSendResult in
            let form = try req.content.decode(PrivateForm.SendEmail.self)
            guard boss.config.smtp.enabled else {
                return SmtpSendResult(sent: false, reason: "SMTP is not configured")
            }
            let mail = try Email(
                from: EmailAddress(
                    address: boss.config.smtp.senderEmail,
                    name: boss.config.smtp.senderName
                ),
                to: [EmailAddress(address: form.to)],
                subject: form.subject,
                body: form.body
            )
            do {
                try await req.smtp.send(mail)
                boss.log.i("Sent email to (\(form.to))")
                return SmtpSendResult(sent: true, reason: "")
            }
            catch {
                boss.log.e("Failed to send email to (\(form.to)): \(error)")
                return SmtpSendResult(sent: false, reason: "\(error)")
            }
        }.openAPI(
            summary: "Send email through BOSS SMTP",
            description: "Uses the SMTP account BOSS already holds. Answers `sent: false` with a reason when SMTP is off or the send fails, rather than failing the call. * Only available to private services.",
            body: .type(PrivateForm.SendEmail.self),
            contentType: .application(.json),
            response: .type(SmtpSendResult.self),
            responseContentType: .application(.json)
        )
    }
}
