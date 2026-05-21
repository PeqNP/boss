/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

extension DateFormatter {
    // Example: Fri, May 13 2026 @ 4:56pm
    public static var usInformal: DateFormatter {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone.current
        formatter.locale = Locale.current
        formatter.dateFormat = "EEE, MMM d yyyy @ h:mma"
        return formatter
    }

    // Example: 1:58p PST
    public static var hoursFormatter: DateFormatter {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone.current
        formatter.locale = Locale.current
        formatter.dateFormat = "h:mmaaaaa z"
        return formatter
    }
}

public func formattedDate(for ts: Double, timeZone: TimeZone? = nil, using formatter: DateFormatter) -> String {
    let date = Date(timeIntervalSince1970: ts)
    if let timeZone {
        formatter.timeZone = timeZone
    }
    let formattedDate = formatter.string(from: date)
    return formattedDate
}

extension Date {
    /// Returns the elapsed time since this date in a compact `Nd Nh` format.
    /// - If >= 1 day: `"1d 4h"`
    /// - If < 1 day: `"4h"`
    public var formattedElapsedTime: String {
        let elapsed = max(0, Date().timeIntervalSince(self))
        let totalHours = Int(elapsed) / 3600
        let days = totalHours / 24
        let hours = totalHours % 24
        if days > 0 {
            return "\(days)d \(hours)h"
        }
        return "\(totalHours)h"
    }
}
