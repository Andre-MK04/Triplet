import SwiftUI

protocol WatchManagementServicing: Sendable {
    func watch(id: String) async throws -> NativeWatchDetail
    func updateWatch(id: String, update: NativeWatchUpdate) async throws -> NativeWatchDetail
    func previewWatch(id: String) async throws -> NativeWatchPreview
    func watchInsights(id: String) async throws -> NativeWatchInsights
    func updateWatchRoute(id: String, update: NativeWatchRouteUpdate) async throws -> NativeWatchDetail
    func watchAirports(query: String) async throws -> [AirportResult]
    func watchPlaces(query: String) async throws -> [FlightPlaceResult]
}

struct NativeWatchDetail: Decodable, Sendable {
    let id: String
    let name: String?
    let originAirports: [String]
    let destinationAirports: [String]?
    let destinationCountries: [String]
    let destinationRegions: [String]
    let destinationContinents: [String]
    let tripPlan: String
    let routeStops: [String]?
    let returnOriginAirports: [String]?
    let startDate: String
    let endDate: String
    let minTripLengthDays: Int
    let maxTripLengthDays: Int
    let maxBudget: Double
    let maxGroundTransferHours: Double
    let frequency: String
    let triggerMode: String?
    let directOnly: Bool?
    let includeBaggage: Bool?
    let isActive: Bool
    var maxStops: Int? = nil

    var destinationDescription: String {
        if let stops = routeStops, !stops.isEmpty { return stops.joined(separator: " → ") }
        let scope = destinationRegions + destinationCountries + destinationContinents + (destinationAirports ?? [])
        return scope.isEmpty ? "Anywhere" : scope.joined(separator: " · ")
    }
}

struct NativeWatchUpdate: Encodable, Sendable {
    var name: String
    var startDate: String
    var endDate: String
    var minTripLengthDays: Int
    var maxTripLengthDays: Int
    var maxBudget: Double
    var maxGroundTransferHours: Double
    var frequency: String
    var triggerMode: String
    var directOnly: Bool
    var includeBaggage: Bool
    // Scope, stops and origins are intentionally untouched by this partial PATCH.
}

struct NativeWatchPreview: Decodable, Sendable {
    let matchingTrips: [SearchTrip]
}

struct NativeWatchInsights: Decodable, Sendable {
    struct Check: Decodable, Identifiable, Sendable {
        var id: String { checkedAt }
        let checkedAt: String
        let bestPrice: Double?
        let resultCount: Int
        let status: String
    }
    struct Delivery: Decodable, Identifiable, Sendable {
        var id: String { sentAt + status }
        let sentAt: String
        let status: String
        let provider: String
        let subject: String
    }
    let totalChecks: Int
    let notificationCount: Int
    let lowestObservedPrice: Double?
    let history: [Check]
    let deliveries: [Delivery]
}

struct WatchDetailView: View {
    let id: String
    let service: any WatchManagementServicing
    let tripService: any TripDetailServicing
    let session: AuthSession
    let dailyChecks: Bool
    var originLimit: Int = 3
    let onUpdated: () -> Void
    @State private var watch: NativeWatchDetail?
    @State private var insights: NativeWatchInsights?
    @State private var preview: NativeWatchPreview?
    @State private var message: String?
    @State private var busy = false
    @State private var editing = false
    @State private var editingRoute = false
    @State private var update: NativeWatchUpdate?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            if let watch {
                List {
                    Section {
                        Text(watch.destinationDescription).font(FarelinTypography.font(.title3, weight: .bold))
                        Text("\(watch.originAirports.joined(separator: " + ")) · \(watch.tripPlan.replacingOccurrences(of: "_", with: " ").capitalized)")
                            .foregroundStyle(.secondary)
                        LabeledContent("Status", value: watch.isActive ? "Active" : "Paused")
                        LabeledContent("Checks", value: watch.frequency.capitalized)
                        if let maxStops = watch.maxStops {
                            LabeledContent("Connections", value: maxStops == 0 ? "Direct only" : "Maximum \(maxStops) stop\(maxStops == 1 ? "" : "s")")
                        }
                        LabeledContent("Budget", value: "€\(Int(watch.maxBudget))")
                        Text("\(watch.minTripLengthDays)–\(watch.maxTripLengthDays) days · \(watch.startDate) to \(watch.endDate)").font(FarelinTypography.font(.footnote))
                        Button("Edit watch", systemImage: "slider.horizontal.3") {
                            update = NativeWatchUpdate(name: watch.name ?? "Trip watch", startDate: watch.startDate,
                                endDate: watch.endDate, minTripLengthDays: watch.minTripLengthDays,
                                maxTripLengthDays: watch.maxTripLengthDays, maxBudget: watch.maxBudget,
                                maxGroundTransferHours: watch.maxGroundTransferHours, frequency: watch.frequency,
                                triggerMode: watch.triggerMode ?? "any", directOnly: watch.directOnly ?? false,
                                includeBaggage: watch.includeBaggage ?? false)
                            editing = true
                        }
                        Button("Preview matching trips", systemImage: "magnifyingglass") {
                            Task { await perform { preview = try await authenticated { try await service.previewWatch(id: id) } } }
                        }
                        Button("Edit airports & destinations", systemImage: "airplane") { editingRoute = true }
                        Text("Preview reads fare observations. It does not send an alert or use an AI search.")
                            .font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                    }
                    if busy { ProgressView("Checking your watch…") }
                    if let message { Text(message).font(FarelinTypography.font(.footnote)).foregroundStyle(FarelinColor.coral) }
                    if let preview {
                        Section("Preview · prices may change") {
                            if preview.matchingTrips.isEmpty {
                                Text("No matching observations right now. Your watch will keep checking on its schedule.")
                            }
                            ForEach(preview.matchingTrips) { trip in
                                NavigationLink {
                                    TripDetailView(trip: trip, service: tripService, reauthenticate: { await session.refreshAccess() })
                                } label: {
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text(trip.routeTitle).font(FarelinTypography.font(.headline))
                                        Text("€\(Int(trip.totalPrice)) observed · check final price with provider").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }
                    if let insights {
                        Section("Observation history") {
                            LabeledContent("Checks recorded", value: String(insights.totalChecks))
                            LabeledContent("Notifications recorded", value: String(insights.notificationCount))
                            if let lowest = insights.lowestObservedPrice { LabeledContent("Lowest observed", value: "€\(Int(lowest))") }
                            if insights.history.isEmpty { Text("History appears after the first scheduled check.").foregroundStyle(.secondary) }
                            ForEach(insights.history) { check in
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(check.checkedAt.prefix(10))
                                        Text("\(check.status) · \(check.resultCount) trips").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if let price = check.bestPrice { Text("€\(Int(price))").monospacedDigit() }
                                }
                            }
                        }
                        Section("Email delivery history") {
                            if insights.deliveries.isEmpty { Text("No delivery recorded yet.").foregroundStyle(.secondary) }
                            ForEach(insights.deliveries) { delivery in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(delivery.subject).font(FarelinTypography.font(.subheadline))
                                    Text("\(delivery.sentAt.prefix(10)) · \(delivery.status) · \(delivery.provider)").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                                }
                            }
                            Text("Provider acceptance is not proof of inbox delivery.").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                        }
                    }
                }
            } else if busy { ProgressView("Loading watch…") }
            else {
                ContentUnavailableView {
                    Label("Watch could not load", systemImage: "wifi.exclamationmark")
                } description: { Text(message ?? "Please try again.") }
                actions: { Button("Try again") { Task { await load() } } }
            }
        }
        .navigationTitle(watch?.name ?? "Trip watch")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .sheet(isPresented: $editing) {
            if let update {
                WatchEditor(update: update, dailyChecks: dailyChecks) { changed in
                    await perform {
                        watch = try await authenticated { try await service.updateWatch(id: id, update: changed) }
                        editing = false
                        onUpdated()
                    }
                    return message
                }
            }
        }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: preview != nil)
        .sheet(isPresented: $editingRoute) {
            if let watch {
                WatchRouteEditor(watch: watch, service: service, originLimit: originLimit) { changed in
                    await perform {
                        self.watch = try await authenticated { try await service.updateWatchRoute(id: id, update: changed) }
                        preview = nil
                        editingRoute = false
                        onUpdated()
                    }
                    return message
                }
            }
        }
        .sensoryFeedback(.success, trigger: preview != nil)
    }

    private func load() async {
        await perform {
            watch = try await authenticated { try await service.watch(id: id) }
            insights = try await authenticated { try await service.watchInsights(id: id) }
        }
    }
    private func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true; message = nil
        defer { busy = false }
        do { try await operation() }
        catch { message = (error as? LocalizedError)?.errorDescription ?? "The watch was not changed." }
    }
    private func authenticated<T: Sendable>(_ operation: () async throws -> T) async throws -> T {
        do { return try await operation() }
        catch APIError.unauthorized {
            guard await session.refreshAccess() else { throw APIError.unauthorized }
            return try await operation()
        }
    }
}

private struct WatchEditor: View {
    @State var update: NativeWatchUpdate
    let dailyChecks: Bool
    let save: (NativeWatchUpdate) async -> String?
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var error: String?
    @State private var saved = false
    var body: some View {
        NavigationStack {
            Form {
                Section("Watch settings") {
                    TextField("Name", text: $update.name)
                    TextField("Start date · YYYY-MM-DD", text: $update.startDate)
                    TextField("End date · YYYY-MM-DD", text: $update.endDate)
                    TextField("Flight budget (€)", value: $update.maxBudget, format: .number).keyboardType(.decimalPad)
                    Stepper("Minimum \(update.minTripLengthDays) days", value: $update.minTripLengthDays, in: 1...60)
                    Stepper("Maximum \(update.maxTripLengthDays) days", value: $update.maxTripLengthDays, in: 1...90)
                    Picker("Check frequency", selection: $update.frequency) {
                        Text("Weekly").tag("weekly")
                        if dailyChecks { Text("Daily").tag("daily") }
                    }
                    if !dailyChecks { Text("Daily checks require a trial or Pro entitlement.").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary) }
                    Picker("Alert when", selection: $update.triggerMode) {
                        Text("Any qualifying deal").tag("any")
                        Text("Below budget").tag("below_budget")
                        Text("Unusually cheap for route").tag("route_deal")
                        Text("Meaningful price drop").tag("price_drop")
                    }
                }
                Section("Comfort") {
                    Toggle("Direct flights only", isOn: $update.directOnly)
                    Toggle("Baggage included required", isOn: $update.includeBaggage)
                    Stepper("Ground transfers up to \(update.maxGroundTransferHours, specifier: "%.1f")h",
                            value: $update.maxGroundTransferHours, in: 0...12, step: 0.5)
                }
                Section {
                    Text("The existing airports, destination scope and route order stay unchanged.")
                        .font(FarelinTypography.font(.footnote)).foregroundStyle(.secondary)
                    if let error { Text(error).foregroundStyle(FarelinColor.coral) }
                }
            }
            .navigationTitle("Edit watch")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() }.disabled(busy) }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        guard update.minTripLengthDays <= update.maxTripLengthDays, update.maxBudget >= 20 else {
                            error = "Check your budget and trip-length range."; return
                        }
                        busy = true
                        Task { error = await save(update); saved = error == nil; busy = false }
                    }.disabled(busy)
                }
            }
            .interactiveDismissDisabled(busy)
            .sensoryFeedback(.success, trigger: saved)
        }
    }
}
