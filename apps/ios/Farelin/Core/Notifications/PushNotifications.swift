import Observation
import SwiftUI
import UserNotifications

struct NativePushStatus: Decodable, Sendable {
    struct Device: Decodable, Identifiable, Sendable { let id: String; let isActive: Bool }
    let enabled: Bool
    let topic: String
    let environment: String
    let devices: [Device]
}
struct NativePushDevice: Decodable, Sendable { let id: String; let isActive: Bool }
struct NativePushRegistration: Encodable, Sendable { let token: String; let topic: String; let environment: String }
protocol NativePushServicing: Sendable {
    func pushStatus() async throws -> NativePushStatus
    func registerPush(_ registration: NativePushRegistration) async throws -> NativePushDevice
    func disconnectPush(id: String) async throws
}

enum NotificationDestination: Equatable, Sendable {
    case watch(String)
    static func parse(watchId: String?) -> NotificationDestination? {
        guard let watchId, let uuid = UUID(uuidString: watchId) else { return nil }
        return .watch(uuid.uuidString.lowercased())
    }
}

@MainActor
@Observable
final class PushNotifications {
    static let shared = PushNotifications()
    private(set) var available = false
    private(set) var enabled = false
    private(set) var working = false
    private(set) var message: String?
    private(set) var devices: [NativePushStatus.Device] = []
    var destination: NotificationDestination?
    private var service: (any NativePushServicing)?
    private var reauthenticate: (@MainActor @Sendable () async -> Bool)?
    private var token: String?
    private var deviceID: String?
    private var accountID: String?
    private var generation = 0
    private var consentKey: String? {
        accountID.map { "farelin.push.consent.\(Bundle.main.bundleIdentifier ?? "app").\($0)" }
    }

    func configure(service: any NativePushServicing, reauthenticate: @escaping @MainActor @Sendable () async -> Bool) {
        self.service = service; self.reauthenticate = reauthenticate
    }

    func restore(accountID: String) async {
        if self.accountID != accountID {
            generation += 1; deviceID = nil; enabled = false; available = false; devices = []
        }
        self.accountID = accountID
        let epoch = generation
        guard let service else { return }
        do {
            let status = try await authenticated { try await service.pushStatus() }
            guard generation == epoch else { return }
            devices = status.devices
            available = status.enabled && status.topic == Bundle.main.bundleIdentifier && status.environment == deliveryEnvironment
            let permission = await UNUserNotificationCenter.current().notificationSettings()
            guard generation == epoch else { return }
            if available && consentKey.map({ UserDefaults.standard.bool(forKey: $0) }) == true
                && (permission.authorizationStatus == .authorized || permission.authorizationStatus == .provisional) {
                // Restore an existing OS permission; never show a prompt on launch.
                UIApplication.shared.registerForRemoteNotifications()
            }
        } catch { if generation == epoch { available = false } }
    }

    func enable() async {
        guard available, !working else { return }
        working = true; message = nil
        let epoch = generation
        defer { working = false }
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound])
            guard generation == epoch else { return }
            if granted {
                if let consentKey { UserDefaults.standard.set(true, forKey: consentKey) }
                UIApplication.shared.registerForRemoteNotifications()
                message = "Connecting this iPhone to your watches…"
            } else { message = "Notifications are off. You can change this in iPhone Settings." }
        } catch { message = "Notification permission could not be requested." }
    }

    func receivedToken(_ data: Data) async {
        token = data.map { String(format: "%02x", $0) }.joined()
        guard available, accountID != nil, consentKey.map({ UserDefaults.standard.bool(forKey: $0) }) == true,
              let service, let token else { return }
        let epoch = generation
        do {
            let registration = NativePushRegistration(token: token, topic: Bundle.main.bundleIdentifier ?? "", environment: deliveryEnvironment)
            let device = try await authenticated { try await service.registerPush(registration) }
            guard generation == epoch else {
                try? await service.disconnectPush(id: device.id)
                return
            }
            deviceID = device.id; enabled = device.isActive
            if !devices.contains(where: { $0.id == device.id }) {
                devices.append(NativePushStatus.Device(id: device.id, isActive: device.isActive))
            }
            message = "Push alerts enabled. Email preferences remain unchanged."
        } catch { message = (error as? LocalizedError)?.errorDescription ?? "This iPhone could not be registered." }
    }

    func disconnect(forSignOut: Bool = false) async {
        generation += 1
        if let consentKey { UserDefaults.standard.set(false, forKey: consentKey) }
        guard let service, let deviceID else {
            enabled = false
            if forSignOut { clearAccountState() }
            UIApplication.shared.unregisterForRemoteNotifications()
            return
        }
        do {
            try await authenticated { try await service.disconnectPush(id: deviceID) }
            self.deviceID = nil; enabled = false
            devices = devices.map { NativePushStatus.Device(id: $0.id, isActive: $0.id == deviceID ? false : $0.isActive) }
            message = "Push alerts disconnected from this iPhone."
        } catch {
            // Keep the id for a retry; don't pretend an offline unregistration worked.
            message = "This iPhone could not be disconnected. Try again online or manage devices on your account."
        }
        if forSignOut {
            clearAccountState()
        }
        UIApplication.shared.unregisterForRemoteNotifications()
    }

    func disconnectDevice(id: String) async {
        guard let service, !working else { return }
        if id == deviceID { await disconnect(); await reloadDevices(); return }
        working = true
        defer { working = false }
        do {
            try await authenticated { try await service.disconnectPush(id: id) }
            await reloadDevices()
            message = "Device disconnected from your watches."
        } catch { message = "Device could not be disconnected. Please try again online." }
    }

    private func reloadDevices() async {
        guard let service, accountID != nil else { return }
        let epoch = generation
        if let status = try? await authenticated({ try await service.pushStatus() }), generation == epoch {
            devices = status.devices
        }
    }

    private func clearAccountState() {
        accountID = nil; deviceID = nil; token = nil; enabled = false
        available = false; destination = nil; devices = []
    }

    func registrationFailed() { message = "Apple could not register this build for push. Check its signing capabilities." }
    private var deliveryEnvironment: String {
        (Bundle.main.object(forInfoDictionaryKey: "APNSDeliveryEnvironment") as? String) == "production" ? "production" : "sandbox"
    }
    private func authenticated<T: Sendable>(_ operation: () async throws -> T) async throws -> T {
        do { return try await operation() }
        catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else { throw APIError.unauthorized }
            return try await operation()
        }
    }
}

@MainActor
final class PushAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        Task { await PushNotifications.shared.receivedToken(deviceToken) }
    }
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: any Error) {
        PushNotifications.shared.registrationFailed()
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let id = response.notification.request.content.userInfo["watchId"] as? String
        let destination = NotificationDestination.parse(watchId: id)
        await MainActor.run { PushNotifications.shared.destination = destination }
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        // Don't surface private account activity over another signed-out account.
        let enabled = await MainActor.run { PushNotifications.shared.enabled }
        return enabled ? [.banner, .sound] : []
    }
}

struct PushPreferencesSection: View {
    private var notifications: PushNotifications { .shared }
    @Environment(\.openURL) private var openURL
    var body: some View {
        Section("Notifications") {
            if notifications.available {
                Button(notifications.enabled ? "Disconnect push alerts" : "Enable push alerts", systemImage: "bell.badge") {
                    Task {
                        if notifications.enabled { await notifications.disconnect() }
                        else { await notifications.enable() }
                    }
                }.disabled(notifications.working)
                Text("Optional alerts from your saved watches. No marketing opt-in and no trip details on your lock screen.")
                    .font(.caption).foregroundStyle(.secondary)
            } else { Text("Push delivery is not configured for this build. Your email watch settings still apply.").font(.footnote).foregroundStyle(.secondary) }
            Button("iPhone notification settings") {
                if let url = URL(string: UIApplication.openNotificationSettingsURLString) { openURL(url) }
            }
            if notifications.devices.contains(where: \.isActive) {
                DisclosureGroup("Connected devices") {
                    ForEach(notifications.devices.filter(\.isActive)) { device in
                        Button("Disconnect device · \(device.id.prefix(8))", role: .destructive) {
                            Task { await notifications.disconnectDevice(id: device.id) }
                        }.disabled(notifications.working)
                    }
                    Text("Device identifiers are private to your account. Disconnect an old device if you no longer use it.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            if let message = notifications.message { Text(message).font(.footnote).foregroundStyle(.secondary) }
        }
        .sensoryFeedback(.selection, trigger: notifications.enabled)
    }
}
