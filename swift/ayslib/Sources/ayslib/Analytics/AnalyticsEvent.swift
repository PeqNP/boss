/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

/**

 NOTES:
 - Some events, specifically "page load" events, may have additional context. In these cases, to allow a `AnalyticsListener` to easily encode the value, the context should be `Encodable` and be able to be turned into a single-depth key/value dictionary. This includes `struct`s, dictionaries, etc.
 */

import Foundation

protocol AnalyticsEvent { }
