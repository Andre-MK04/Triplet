import SwiftUI
import UIKit

enum FarelinColor {
    // Exact paired RGB tokens from apps/web/app/globals.css. Do not approximate
    // the colors with percentages or substitute Apple's generic system gray.
    static let ink = paired(0x0B1117, 0xF7F9FB)
    static let soft = paired(0x0E141A, 0xEEF2F6)
    static let raised = paired(0x161C22, 0xFFFFFF)
    static let panel = paired(0x1A2027, 0xFFFFFF)
    static let lifted = paired(0x252B31, 0xF0F3F7)
    static let deep = paired(0x090F15, 0xE6EBF0)
    static let cloud = paired(0xE8F0F4, 0x0F1720)
    static let mist = paired(0x93A6B4, 0x5A6B78)
    static let mint = paired(0x7DDFC3, 0x0C785F)
    static let action = mint
    static let mintInk = paired(0x00382C, 0xFFFFFF)
    static let coral = paired(0xFF9A78, 0xBD4426)
    static let sky = paired(0x8EC5FF, 0x2563B0)
    static let gold = paired(0xFFD08A, 0x926400)
    static let line = paired(0xE8F0F4, 0x0B1117, darkAlpha: 0.15, lightAlpha: 0.14)
    // Decorative globe materials from RouteGlobe/TravelMapGlobe, not text.
    static let globeSea = paired(0x090F15, 0xDCE6EA)
    static let globeLand = paired(0x5F7F90, 0x8198A3)
    static let globeWire = paired(0x16202A, 0x8299A4)
    static let globeLived = paired(0xFF9A78, 0xD65F42)
    static let globeVisited = paired(0x7DDFC3, 0x16836F)
    static let globeWishlist = paired(0xE8C46A, 0xA97A12)

    private static func paired(_ dark: UInt32, _ light: UInt32,
                               darkAlpha: CGFloat = 1, lightAlpha: CGFloat = 1) -> Color {
        Color(uiColor: UIColor { traits in
            let value = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((value >> 16) & 255) / 255,
                           green: CGFloat((value >> 8) & 255) / 255,
                           blue: CGFloat(value & 255) / 255,
                           alpha: traits.userInterfaceStyle == .dark ? darkAlpha : lightAlpha)
        })
    }
}

enum FarelinGeometry {
    static let cardRadius: CGFloat = 0
    static let controlRadius: CGFloat = 0
}

@MainActor
enum FarelinNativeChrome {
    static func configure() {
        // Do not replace standard/scroll-edge UINavigationBarAppearance here:
        // iOS 26.5 loses its large-title rendering with that global override.
        // Keep the native title/material lifecycle; brand the content and tint.
        UINavigationBar.appearance().tintColor = UIColor(FarelinColor.mint)

        // Keep the native tab-bar material rather than building a custom web nav.
        UITabBar.appearance().tintColor = UIColor(FarelinColor.mint)
        UITabBar.appearance().unselectedItemTintColor = UIColor(FarelinColor.mist)
        UITableView.appearance().backgroundColor = UIColor(FarelinColor.ink)
        UITableViewCell.appearance().backgroundColor = UIColor(FarelinColor.raised)
        UISegmentedControl.appearance().selectedSegmentTintColor = UIColor(FarelinColor.raised)
        UISegmentedControl.appearance().backgroundColor = UIColor(FarelinColor.soft)
        UISegmentedControl.appearance().setTitleTextAttributes(
            [.foregroundColor: UIColor(FarelinColor.cloud)], for: .normal)
        UISegmentedControl.appearance().setTitleTextAttributes(
            [.foregroundColor: UIColor(FarelinColor.cloud)], for: .selected)
    }
}

/// Brand the content, while preserving native navigation, sheets and controls.
struct FarelinAppSurface: ViewModifier {
    func body(content: Content) -> some View {
        content
            .foregroundStyle(FarelinColor.cloud)
            .tint(FarelinColor.mint)
            .scrollContentBackground(.hidden)
            .background(FarelinColor.ink.ignoresSafeArea())
    }
}

struct FarelinSectionLabel: View {
    let title: String
    var accented = false

    var body: some View {
        Text(title)
            .font(.caption2.monospaced().weight(.semibold))
            .tracking(1.2)
            .foregroundStyle(accented ? FarelinColor.action : FarelinColor.mist)
    }
}

struct FarelinPrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.monospaced().weight(.semibold))
            .tracking(0.8)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .frame(minHeight: 44)
            .foregroundStyle(FarelinColor.mintInk)
            .background(
                FarelinColor.mint.opacity(
                    !isEnabled ? 0.42 : (configuration.isPressed ? 0.75 : 1)
                )
            )
            .clipShape(.rect(cornerRadius: FarelinGeometry.controlRadius))
            .scaleEffect(reduceMotion ? 1 : (configuration.isPressed ? 0.985 : 1))
            .opacity(isEnabled ? 1 : 0.72)
            .animation(reduceMotion ? nil : .snappy(duration: 0.18), value: configuration.isPressed)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.15), value: isEnabled)
    }
}

struct FarelinCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(FarelinColor.raised, in: .rect(cornerRadius: FarelinGeometry.cardRadius))
            .overlay {
                RoundedRectangle(cornerRadius: FarelinGeometry.cardRadius)
                    .stroke(FarelinColor.line, lineWidth: 1)
            }
    }
}

extension View {
    func farelinAppSurface() -> some View {
        modifier(FarelinAppSurface())
    }
    func farelinCard() -> some View {
        modifier(FarelinCardModifier())
    }
}
