import SwiftUI
import UIKit

/// Same type families as apps/web/app/layout.tsx. Custom text still scales
/// against iOS semantic text styles, including accessibility sizes.
enum FarelinTypography {
    enum Family: String, CaseIterable {
        case display = "BricolageGrotesque"
        case body = "HankenGrotesk"
        case mono = "JetBrainsMono"
    }

    static func name(_ family: Family, weight: Font.Weight) -> String {
        let suffix: String
        switch weight {
        case .medium: suffix = "Medium"
        case .semibold: suffix = "SemiBold"
        case .bold: suffix = "Bold"
        case .heavy, .black: suffix = "ExtraBold"
        default: suffix = "Regular"
        }
        return "\(family.rawValue)-\(suffix)"
    }

    static func font(_ style: Font.TextStyle, weight: Font.Weight? = nil,
                     family: Family = .body) -> Font {
        let size: CGFloat
        switch style {
        case .largeTitle: size = 34
        case .title: size = 28
        case .title2: size = 22
        case .title3: size = 20
        case .headline, .body: size = 17
        case .callout: size = 16
        case .subheadline: size = 15
        case .footnote: size = 13
        case .caption: size = 12
        case .caption2: size = 11
        @unknown default: size = 17
        }
        return .custom(name(family, weight: weight ?? (style == .headline ? .semibold : .regular)),
                       size: size, relativeTo: style)
    }

    static func display(size: CGFloat, weight: Font.Weight = .bold,
                        relativeTo style: Font.TextStyle = .largeTitle) -> Font {
        .custom(name(.display, weight: weight), size: size, relativeTo: style)
    }

    static func mono(size: CGFloat, weight: Font.Weight = .semibold) -> Font {
        .custom(name(.mono, weight: weight), size: size, relativeTo: .caption2)
    }

    @MainActor static func configureNativeLabels() {
        // Customize fonts directly, not the bar's standard/scroll-edge appearance.
        // Replacing those appearances hid native large titles on iOS 26.5.
        guard let display = UIFont(name: name(.display, weight: .bold), size: 34),
              let body = UIFont(name: name(.body, weight: .semibold), size: 17),
              let tab = UIFont(name: name(.body, weight: .medium), size: 11) else {
            assertionFailure("Missing bundled brand fonts")
            return // Preserve usable native navigation if packaging ever regresses.
        }
        UINavigationBar.appearance().largeTitleTextAttributes = [
            .font: UIFontMetrics(forTextStyle: .largeTitle).scaledFont(for: display)
        ]
        UINavigationBar.appearance().titleTextAttributes = [
            .font: UIFontMetrics(forTextStyle: .headline).scaledFont(for: body)
        ]
        UITabBarItem.appearance().setTitleTextAttributes([.font: tab], for: .normal)
    }
}
