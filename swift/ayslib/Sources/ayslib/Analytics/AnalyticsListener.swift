/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

protocol AnalyticsListener {
    func receive(_ event: AnalyticsEvent)
    func transaction(_ event: AnalyticsEvent, _ context: AnalyticsTransaction)
}
