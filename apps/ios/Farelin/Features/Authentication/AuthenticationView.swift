import SwiftUI

struct AuthenticationView: View {
    enum Mode: String, CaseIterable, Identifiable {
        case signIn = "Sign in"
        case createAccount = "Create account"

        var id: String { rawValue }
    }

    let configuration: AppConfiguration
    let session: AuthSession

    @State private var mode: Mode = .signIn
    @State private var email = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var acceptedLegal = false
    @FocusState private var focusedField: Field?

    private enum Field { case name, email, password }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    brand
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your trips, watched quietly.")
                            .font(.system(size: 35, weight: .bold, design: .rounded))
                            .tracking(-1)
                        Text("Sign in to search, save watches and keep every Farelin trip tied to you.")
                            .foregroundStyle(.secondary)
                            .lineSpacing(3)
                    }

                    Picker("Account action", selection: $mode) {
                        ForEach(Mode.allCases) { option in
                            Text(option.rawValue).tag(option)
                        }
                    }
                    .pickerStyle(.segmented)

                    VStack(spacing: 18) {
                        if mode == .createAccount {
                            TextField("Name (optional)", text: $displayName)
                                .textContentType(.name)
                                .focused($focusedField, equals: .name)
                                .textFieldStyle(FarelinTextFieldStyle())
                        }
                        TextField("Email", text: $email)
                            .textContentType(.emailAddress)
                            .keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .focused($focusedField, equals: .email)
                            .textFieldStyle(FarelinTextFieldStyle())
                        SecureField("Password", text: $password)
                            .textContentType(mode == .signIn ? .password : .newPassword)
                            .focused($focusedField, equals: .password)
                            .textFieldStyle(FarelinTextFieldStyle())
                    }

                    if mode == .createAccount {
                        Toggle(isOn: $acceptedLegal) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("I accept Farelin’s Terms and Privacy Policy")
                                    .font(.subheadline.weight(.semibold))
                                HStack(spacing: 14) {
                                    Link("Read terms", destination: URL(string: "https://www.farelin.com/terms")!)
                                    Link("Privacy", destination: URL(string: "https://www.farelin.com/privacy")!)
                                }
                                .font(.caption)
                            }
                        }
                    }

                    if let message = session.message {
                        Text(message)
                            .font(.subheadline)
                            .foregroundStyle(FarelinColor.coral)
                    }

                    Button {
                        focusedField = nil
                        Task {
                            if mode == .signIn {
                                await session.signIn(email: email, password: password)
                            } else {
                                await session.signUp(
                                    email: email,
                                    password: password,
                                    displayName: displayName.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
                                )
                            }
                        }
                    } label: {
                        Group {
                            if session.isWorking {
                                ProgressView().tint(FarelinColor.ink)
                            } else {
                                Text(mode.rawValue)
                            }
                        }
                    }
                    .buttonStyle(FarelinPrimaryButtonStyle())
                    .disabled(!canSubmit || session.isWorking)

                    Text("The iPhone app requires an account before fare or AI search. You can still explore Farelin publicly on the web.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineSpacing(3)
                }
                .padding(24)
            }
            .background(Color(.systemBackground))
        }
        .onChange(of: mode) {
            session.message = nil
            acceptedLegal = false
        }
    }

    private var canSubmit: Bool {
        email.contains("@")
            && password.count >= 12
            && (mode == .signIn || (acceptedLegal && session.legalVersions != nil))
    }

    private var brand: some View {
        HStack(spacing: 11) {
            Image("BrandMark")
                .resizable()
                .scaledToFit()
                .frame(width: 36, height: 36)
                .accessibilityHidden(true)
            Text("FARELIN")
                .font(.system(.headline, design: .monospaced, weight: .bold))
                .tracking(3)
            Spacer()
            if configuration.environment == .staging {
                Text("STAGING")
                    .font(.caption2.monospaced())
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct FarelinTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .padding(.horizontal, 16)
            .frame(minHeight: 54)
            .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Color(.separator).opacity(0.45), lineWidth: 1)
            }
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}
