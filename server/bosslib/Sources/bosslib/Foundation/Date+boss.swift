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
