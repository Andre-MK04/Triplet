import SwiftUI

enum FarelinColor {
    static let mint = Color(red: 0.49, green: 0.87, blue: 0.76)
    static let coral = Color(red: 1.00, green: 0.60, blue: 0.47)
    static let gold = Color(red: 0.91, green: 0.77, blue: 0.42)
    static let ink = Color(red: 0.043, green: 0.067, blue: 0.090)
    static let cloud = Color(red: 0.91, green: 0.94, blue: 0.96)
}

struct FarelinSectionLabel: View {
    let title: String
    var accented = false

    var body: some View {
        Text(title)
            .font(.caption2.monospaced().weight(.semibold))
            .tracking(1.2)
            .foregroundStyle(accented ? FarelinColor.mint : Color.secondary)
    }
}

struct FarelinPrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .foregroundStyle(FarelinColor.ink)
            .background(
                FarelinColor.mint.opacity(
                    !isEnabled ? 0.42 : (configuration.isPressed ? 0.75 : 1)
                )
            )
            .clipShape(.rect(cornerRadius: 16))
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
            .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 22))
            .overlay {
                RoundedRectangle(cornerRadius: 22)
                    .stroke(Color(.separator).opacity(0.35), lineWidth: 0.5)
            }
    }
}

extension View {
    func farelinCard() -> some View {
        modifier(FarelinCardModifier())
    }
}
