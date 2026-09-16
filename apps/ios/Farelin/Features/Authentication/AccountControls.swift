import SwiftUI
import UniformTypeIdentifiers

struct AccountControls: View {
    let service: any NativeAccountServicing
    let session: AuthSession
    let hasPassword: Bool
    @State private var busy = false
    @State private var message: String?
    @State private var deleting = false
    @State private var confirmation = ""
    @State private var changingPassword = false
    @State private var exporting = false
    @State private var document = AccountExportDocument()

    var body: some View {
        Section("Your account & data") {
            if hasPassword {
                Button("Change password", systemImage: "key") { changingPassword = true }
            }
            Button("Export my data", systemImage: "square.and.arrow.up") {
                Task {
                    await perform {
                        let export = try await authenticated { try await service.exportAccount() }
                        let encoder = JSONEncoder()
                        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                        document = AccountExportDocument(data: try encoder.encode(export))
                        exporting = true
                    }
                }
            }
            Button("Delete account", systemImage: "person.crop.circle.badge.minus", role: .destructive) {
                confirmation = ""
                deleting = true
            }
            if busy { ProgressView("Updating your account…") }
            if let message { Text(message).font(.footnote).foregroundStyle(.secondary) }
        }
        .disabled(busy)
        .sheet(isPresented: $changingPassword) {
            PasswordRecoveryView(service: service, session: session, mode: .change)
        }
        .sheet(isPresented: $deleting) {
            NavigationStack {
                Form {
                    Section {
                        Text("Permanently delete your account?").font(.title2.bold())
                        Text("Your profile, travel map, saved fares, watches and sessions will be removed. Any paid subscription must be canceled successfully first. This cannot be undone.")
                        TextField("Type DELETE to confirm", text: $confirmation)
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                            .accessibilityIdentifier("account-delete-confirmation")
                    }
                    Section {
                        Button("Delete my account", role: .destructive) {
                            Task {
                                await perform {
                                    try await authenticated { try await service.deleteAccount() }
                                    deleting = false
                                    await session.accountWasDeleted()
                                }
                            }
                        }
                        .disabled(confirmation != "DELETE" || busy)
                        if busy { ProgressView("Deleting…") }
                        if let message { Text(message).font(.footnote) }
                    }
                }
                .navigationTitle("Delete account")
                .toolbar { Button("Cancel") { deleting = false }.disabled(busy) }
            }
        }
        .fileExporter(isPresented: $exporting, document: document, contentType: .json,
                      defaultFilename: "Farelin-account-export") { result in
            document = AccountExportDocument()
            switch result {
            case .success: message = "Export saved. Keep it private — it contains your personal data."
            case .failure: message = "The export could not be saved. Please try again."
            }
        }
        .sensoryFeedback(.success, trigger: exporting)
    }

    private func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true; message = nil
        defer { busy = false }
        do { try await operation() }
        catch { message = (error as? LocalizedError)?.errorDescription ?? "Your account was not changed. Please try again." }
    }

    private func authenticated<T: Sendable>(_ operation: () async throws -> T) async throws -> T {
        do { return try await operation() }
        catch APIError.unauthorized {
            guard await session.refreshAccess() else { throw APIError.unauthorized }
            return try await operation()
        }
    }
}

struct AccountExportDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.json] }
    var data = Data()
    init(data: Data = Data()) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

struct PasswordRecoveryView: View {
    enum Mode { case forgot, change, reset }
    let service: any NativeAccountServicing
    var session: AuthSession?
    var mode: Mode = .forgot
    @Environment(\.dismiss) private var dismiss
    @State private var email = ""
    @State private var currentPassword = ""
    @State private var password = ""
    @State private var confirmation = ""
    @State private var token = ""
    @State private var busy = false
    @State private var message: String?
    @State private var succeeded = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    if mode == .forgot {
                        Text("Enter your account email. If it has a password login, we’ll send a reset link. You can open the secure link in your browser to choose a new password.")
                        TextField("Email", text: $email).textContentType(.emailAddress)
                            .keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                    } else {
                        if mode == .change { SecureField("Current password", text: $currentPassword).textContentType(.password) }
                        if mode == .reset { TextField("Reset token from your email link", text: $token).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        SecureField("New password · at least 12 characters", text: $password).textContentType(.newPassword)
                        SecureField("Confirm new password", text: $confirmation).textContentType(.newPassword)
                    }
                }
                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if busy { ProgressView() }
                        else { Text(mode == .forgot ? "Send reset link" : "Save new password") }
                    }
                    .disabled(busy || succeeded)
                    if let message { Text(message).font(.footnote).accessibilityIdentifier("password-message") }
                }
            }
            .navigationTitle(mode == .forgot ? "Forgot password" : "Change password")
            .toolbar { Button("Done") { dismiss() }.disabled(busy) }
            .sensoryFeedback(.success, trigger: succeeded)
        }
    }

    private func submit() async {
        guard !busy else { return }
        guard mode == .forgot || (password.count >= 12 && password == confirmation) else {
            message = "Use at least 12 characters and make sure both new passwords match."; return
        }
        guard mode != .forgot || (email.contains("@") && email.contains(".")) else {
            message = "Enter a valid email address."; return
        }
        busy = true; message = nil
        defer { busy = false }
        do {
            if mode == .forgot {
                try await service.forgotPassword(email: email.trimmingCharacters(in: .whitespacesAndNewlines))
                message = "If this address has a password account, a reset link is on its way. Check spam too."
            } else if mode == .reset {
                try await service.resetPassword(token: token, password: password)
                message = "Password updated. You can sign in with your new password."
            } else {
                do { try await service.changePassword(current: currentPassword, new: password) }
                catch APIError.unauthorized {
                    guard let session, await session.refreshAccess() else { throw APIError.unauthorized }
                    try await service.changePassword(current: currentPassword, new: password)
                }
                // Password changes revoke all refresh sessions; do not keep a stale local login.
                await session?.signOut()
                message = "Password updated. Sign in again with your new password."
            }
            currentPassword = ""; password = ""; confirmation = ""; token = ""
            succeeded = true
        } catch { message = (error as? LocalizedError)?.errorDescription ?? "We could not update your password." }
    }
}
