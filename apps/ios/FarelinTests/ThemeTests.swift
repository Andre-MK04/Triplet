import SwiftUI
import UIKit
import XCTest
@testable import Farelin

@MainActor
final class ThemeTests: XCTestCase {
    func testPaletteMatchesWebTokensInBothThemes() {
        let tokens: [(Color, UInt32, UInt32)] = [
            (FarelinColor.ink, 0x0B1117, 0xF7F9FB),
            (FarelinColor.soft, 0x0E141A, 0xEEF2F6),
            (FarelinColor.raised, 0x161C22, 0xFFFFFF),
            (FarelinColor.panel, 0x1A2027, 0xFFFFFF),
            (FarelinColor.lifted, 0x252B31, 0xF0F3F7),
            (FarelinColor.deep, 0x090F15, 0xE6EBF0),
            (FarelinColor.cloud, 0xE8F0F4, 0x0F1720),
            (FarelinColor.mist, 0x93A6B4, 0x5A6B78),
            (FarelinColor.mint, 0x7DDFC3, 0x0C785F),
            (FarelinColor.mintInk, 0x00382C, 0xFFFFFF),
            (FarelinColor.coral, 0xFF9A78, 0xBD4426),
            (FarelinColor.sky, 0x8EC5FF, 0x2563B0),
            (FarelinColor.gold, 0xFFD08A, 0x926400),
            (FarelinColor.globeSea, 0x090F15, 0xDCE6EA),
            (FarelinColor.globeLand, 0x5F7F90, 0x8198A3),
            (FarelinColor.globeWire, 0x16202A, 0x8299A4),
            (FarelinColor.globeLived, 0xFF9A78, 0xD65F42),
            (FarelinColor.globeVisited, 0x7DDFC3, 0x16836F),
            (FarelinColor.globeWishlist, 0xE8C46A, 0xA97A12)
        ]
        for (color, dark, light) in tokens {
            for (style, hex) in [(UIUserInterfaceStyle.dark, dark), (.light, light)] {
                let components = rgb(color, style: style)
                XCTAssertEqual(components[0], Double((hex >> 16) & 255) / 255, accuracy: 0.001)
                XCTAssertEqual(components[1], Double((hex >> 8) & 255) / 255, accuracy: 0.001)
                XCTAssertEqual(components[2], Double(hex & 255) / 255, accuracy: 0.001)
            }
        }
    }

    func testTextAndAccentContrastOnPageAndCard() {
        for style in [UIUserInterfaceStyle.light, .dark] {
            for text in [FarelinColor.cloud, FarelinColor.mist, FarelinColor.mint,
                         FarelinColor.coral, FarelinColor.sky, FarelinColor.gold] {
                for surface in [FarelinColor.ink, FarelinColor.raised] {
                    XCTAssertGreaterThanOrEqual(contrast(text, surface, style: style), 4.5)
                }
            }
            XCTAssertGreaterThanOrEqual(contrast(FarelinColor.mintInk, FarelinColor.mint, style: style), 4.5)
        }
    }

    func testHairlinesUseWebAlphaAndCustomGeometryIsFlat() {
        for (style, alpha) in [(UIUserInterfaceStyle.dark, 0.15), (.light, 0.14)] {
            let color = UIColor(FarelinColor.line).resolvedColor(with: UITraitCollection(userInterfaceStyle: style))
            XCTAssertEqual(color.cgColor.alpha, alpha, accuracy: 0.001)
        }
        XCTAssertEqual(FarelinGeometry.cardRadius, 0)
        XCTAssertEqual(FarelinGeometry.controlRadius, 0)
    }

    private func rgb(_ color: Color, style: UIUserInterfaceStyle) -> [Double] {
        var red: CGFloat = 0, green: CGFloat = 0, blue: CGFloat = 0, alpha: CGFloat = 0
        let resolved = UIColor(color).resolvedColor(with: UITraitCollection(userInterfaceStyle: style))
        XCTAssertTrue(resolved.getRed(&red, green: &green, blue: &blue, alpha: &alpha))
        return [Double(red), Double(green), Double(blue)]
    }

    private func contrast(_ first: Color, _ second: Color, style: UIUserInterfaceStyle) -> Double {
        func luminance(_ color: Color) -> Double {
            let values = rgb(color, style: style).map { $0 <= 0.04045 ? $0 / 12.92 : pow(($0 + 0.055) / 1.055, 2.4) }
            return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722
        }
        let left = luminance(first), right = luminance(second)
        return (max(left, right) + 0.05) / (min(left, right) + 0.05)
    }
}
