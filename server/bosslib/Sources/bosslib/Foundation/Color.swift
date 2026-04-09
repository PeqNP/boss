/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

public struct Color: Sendable, Codable, Equatable, Hashable, CustomStringConvertible {
    public let red: Double
    public let green: Double
    public let blue: Double
    public let alpha: Double
    
    public init(red: Double, green: Double, blue: Double, alpha: Double = 1.0) {
        self.red   = max(0, min(1, red))
        self.green = max(0, min(1, green))
        self.blue  = max(0, min(1, blue))
        self.alpha = max(0, min(1, alpha))
    }
    
    public init(white: Double, alpha: Double = 1.0) {
        self.init(red: white, green: white, blue: white, alpha: alpha)
    }
    
    public init?(hex: String) {
        let hex = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        let scanner = Scanner(string: hex.hasPrefix("#") ? String(hex.dropFirst()) : hex)
        
        var hexNumber: UInt64 = 0
        guard scanner.scanHexInt64(&hexNumber) else { return nil }
        
        let r, g, b, a: Double
        switch hex.count {
        case 6, 7:  // #RRGGBB or RRGGBB
            r = Double((hexNumber & 0xFF0000) >> 16) / 255.0
            g = Double((hexNumber & 0x00FF00) >> 8) / 255.0
            b = Double( hexNumber & 0x0000FF)  / 255.0
            a = 1.0
        case 8, 9:  // #RRGGBBAA or RRGGBBAA
            r = Double((hexNumber & 0xFF000000) >> 24) / 255.0
            g = Double((hexNumber & 0x00FF0000) >> 16) / 255.0
            b = Double((hexNumber & 0x0000FF00) >> 8) / 255.0
            a = Double( hexNumber & 0x000000FF) / 255.0
        default:
            return nil
        }
        
        self.init(red: r, green: g, blue: b, alpha: a)
    }
    
    public var description: String {
        String(format: "Color(red: %.3f, green: %.3f, blue: %.3f, alpha: %.3f)", red, green, blue, alpha)
    }
}
