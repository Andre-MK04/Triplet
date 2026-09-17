import SwiftUI
import UIKit
import XCTest
@testable import Farelin

@MainActor
final class TypographyTests: XCTestCase {
    func testEveryBundledFamilyAndWeightLoadsWithoutSystemFallback() {
        for family in FarelinTypography.Family.allCases {
            for weight in [Font.Weight.regular, .medium, .semibold, .bold, .heavy] {
                let name = FarelinTypography.name(family, weight: weight)
                let font = UIFont(name: name, size: 17)
                XCTAssertNotNil(font, "Missing registered font: \(name)")
                XCTAssertEqual(font?.fontName, name)
            }
        }
    }

    func testBrandFamiliesMatchWebTypographyAndKeepPreviousGeometry() {
        XCTAssertEqual(FarelinTypography.Family.display.rawValue, "BricolageGrotesque")
        XCTAssertEqual(FarelinTypography.Family.body.rawValue, "HankenGrotesk")
        XCTAssertEqual(FarelinTypography.Family.mono.rawValue, "JetBrainsMono")
        XCTAssertNotNil(Bundle.main.url(forResource: "BricolageGrotesque-Bold", withExtension: "ttf"))
    }

    func testMetricsScaleAtAccessibilitySizes() throws {
        let base = try XCTUnwrap(UIFont(name: "HankenGrotesk-Regular", size: 17))
        let metrics = UIFontMetrics(forTextStyle: .body)
        let standard = metrics.scaledFont(for: base, compatibleWith: UITraitCollection(preferredContentSizeCategory: .large))
        let large = metrics.scaledFont(for: base, compatibleWith: UITraitCollection(preferredContentSizeCategory: .accessibilityExtraExtraExtraLarge))
        XCTAssertGreaterThan(large.pointSize, standard.pointSize)
        XCTAssertEqual(large.familyName, base.familyName)
    }
}
