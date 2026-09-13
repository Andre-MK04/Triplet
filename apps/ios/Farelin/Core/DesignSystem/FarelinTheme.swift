import SwiftUI

enum FarelinColor {
    static let mint = Color(red: 0.49, green: 0.87, blue: 0.76)
    static let coral = Color(red: 1.00, green: 0.60, blue: 0.47)
    static let ink = Color(red: 0.043, green: 0.067, blue: 0.090)
    static let cloud = Color(red: 0.91, green: 0.94, blue: 0.96)
}

struct FarelinPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .foregroundStyle(FarelinColor.ink)
            .background(FarelinColor.mint.opacity(configuration.isPressed ? 0.75 : 1))
            .clipShape(.rect(cornerRadius: 16))
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .animation(.snappy(duration: 0.18), value: configuration.isPressed)
    }
}

