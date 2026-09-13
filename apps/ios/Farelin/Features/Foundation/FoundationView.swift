import Observation
import SwiftUI

@MainActor
@Observable
final class FoundationModel {
    enum ConnectionState: Equatable {
        case checking
        case connected
        case unavailable
    }

    var connectionState: ConnectionState = .checking
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func checkConnection() async {
        connectionState = .checking
        do {
            let health = try await client.health()
            connectionState = health.status == "ok" ? .connected : .unavailable
        } catch {
            connectionState = .unavailable
        }
    }
}

struct FoundationView: View {
    let configuration: AppConfiguration
    @State private var model: FoundationModel

    init(configuration: AppConfiguration) {
        self.configuration = configuration
        _model = State(initialValue: FoundationModel(client: APIClient(baseURL: configuration.apiBaseURL)))
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color(.systemBackground).ignoresSafeArea()
                VStack(alignment: .leading, spacing: 28) {
                    Spacer()
                    brandMark
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Find cheap trips,\nnot just cheap flights.")
                            .font(.system(size: 38, weight: .bold, design: .rounded))
                            .tracking(-1.2)
                        Text("Your native Farelin journey starts here. Sign-in and the complete travel experience arrive in the next stage.")
                            .font(.body)
                            .foregroundStyle(.secondary)
                            .lineSpacing(4)
                    }
                    connectionPanel
                    Button("Check connection") {
                        Task { await model.checkConnection() }
                    }
                    .buttonStyle(FarelinPrimaryButtonStyle())
                    Spacer()
                }
                .padding(24)
            }
            .task { await model.checkConnection() }
        }
        .tint(FarelinColor.mint)
    }

    private var brandMark: some View {
        HStack(spacing: 12) {
            Image("BrandMark")
                .resizable()
                .scaledToFit()
                .frame(width: 42, height: 42)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text("FARELIN")
                    .font(.system(.headline, design: .monospaced, weight: .bold))
                    .tracking(3)
                Text(configuration.environment == .staging ? "STAGING" : "TRAVEL INTELLIGENCE")
                    .font(.caption2.monospaced())
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var connectionPanel: some View {
        HStack(spacing: 12) {
            Group {
                switch model.connectionState {
                case .checking:
                    ProgressView()
                case .connected:
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(FarelinColor.mint)
                case .unavailable:
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(FarelinColor.coral)
                }
            }
            .frame(width: 24)
            VStack(alignment: .leading, spacing: 3) {
                Text(connectionTitle).font(.headline)
                Text(configuration.apiBaseURL.host ?? "Configured API")
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
        }
        .padding(18)
        .background(.thinMaterial, in: .rect(cornerRadius: 18))
        .accessibilityElement(children: .combine)
    }

    private var connectionTitle: String {
        switch model.connectionState {
        case .checking: "Checking Farelin…"
        case .connected: "Farelin is connected"
        case .unavailable: "Staging is not connected yet"
        }
    }
}

