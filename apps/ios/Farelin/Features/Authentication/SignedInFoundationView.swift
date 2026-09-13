import SwiftUI

struct SignedInFoundationView: View {
    let configuration: AppConfiguration
    let session: AuthSession
    let user: AuthUser

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image("BrandMark")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 42, height: 42)
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(user.displayName ?? "Welcome to Farelin")
                                .font(.headline)
                            Text(user.email)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                if !user.isVerified {
                    Section("Confirm your email") {
                        Text("Verify your address before using Farelin’s AI and fare-search tools. This keeps usage tied to a reachable account.")
                            .font(.subheadline)
                        Button("Send a new verification email") {
                            Task { await session.resendVerification() }
                        }
                        Button("I’ve confirmed my email") {
                            Task { await session.refreshUser() }
                        }
                    }
                } else {
                    Section {
                        Label("Your account is ready", systemImage: "checkmark.seal.fill")
                            .foregroundStyle(FarelinColor.mint)
                        Text("The native dashboard, search, watches and My World arrive in the next stages. Your account already uses the same Farelin backend as the web app.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                if let message = session.message {
                    Section {
                        Text(message).font(.subheadline)
                    }
                }

                Section {
                    LabeledContent("Environment", value: configuration.environment.rawValue.capitalized)
                    LabeledContent("API", value: configuration.apiBaseURL.host ?? "Configured")
                }

                Section {
                    Button("Sign out", role: .destructive) {
                        Task { await session.signOut() }
                    }
                    .disabled(session.isWorking)
                }
            }
            .navigationTitle("Farelin")
        }
    }
}
