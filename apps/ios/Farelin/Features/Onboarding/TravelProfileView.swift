import SwiftUI

struct TravelProfileView: View {
    let store: TravelProfileStore
    let originLimit: Int

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dismiss) private var dismiss
    @State private var step = 0
    @State private var locationQuery = ""
    @State private var airportQuery = ""
    @State private var absoluteBudget = ""

    private let totalSteps = 10

    var body: some View {
        NavigationStack {
            Group {
                if let draft = store.draft {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            progress
                            header
                            currentStep(draft)

                            if let error = store.errorMessage {
                                Label(error, systemImage: "exclamationmark.triangle")
                                    .font(.footnote)
                                    .foregroundStyle(.red)
                                    .farelinCard()
                                    .accessibilityIdentifier("profile-error")
                            }

                            controls
                        }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 36)
                    }
                    .scrollDismissesKeyboard(.interactively)
                    .background(Color(.systemBackground))
                } else {
                    ProgressView("Loading your travel profile…")
                }
            }
            .navigationTitle("Travel profile")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                guard let draft = store.draft else { return }
                locationQuery = draft.homeLocation
                absoluteBudget = draft.absoluteMaxBudget.map { String(format: "%.0f", $0) } ?? ""
            }
        }
    }

    private var progress: some View {
        VStack(spacing: 8) {
            HStack {
                Text("SET UP YOUR DEFAULTS")
                Spacer()
                Text("\(step + 1) / \(totalSteps)")
                    .monospacedDigit()
            }
            .font(.caption2.monospaced().weight(.semibold))
            .tracking(1.1)
            .foregroundStyle(.secondary)
            ProgressView(value: Double(step + 1), total: Double(totalSteps))
                .tint(FarelinColor.mint)
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Travel profile step \(step + 1) of \(totalSteps)")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(stepTitle)
                .font(.system(size: 30, weight: .bold, design: .rounded))
                .tracking(-0.6)
            Text(stepSubtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineSpacing(3)
        }
        .id(step)
        .transition(reduceMotion ? .identity : .opacity.combined(with: .move(edge: .trailing)))
    }

    @ViewBuilder
    private func currentStep(_ draft: TravelProfileDraft) -> some View {
        switch step {
        case 0: locationStep(draft)
        case 1: distanceStep(draft)
        case 2: airportsStep(draft)
        case 3: stylesStep(draft)
        case 4: lengthStep(draft)
        case 5: budgetStep(draft)
        case 6: spontaneityStep(draft)
        case 7: comfortStep(draft)
        case 8: tripShapeStep(draft)
        default: notificationsStep(draft)
        }
    }

    private func locationStep(_ draft: TravelProfileDraft) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("City or town", text: $locationQuery)
                .textContentType(.addressCity)
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .padding(15)
                .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 16))
                .overlay {
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(draft.baseLocationId == nil ? Color(.separator) : FarelinColor.mint, lineWidth: 1)
                }
                .accessibilityLabel("Search for your base city or town")
                .onChange(of: locationQuery) { _, newValue in
                    if draft.baseLocationId != nil, newValue != draft.homeLocation {
                        store.invalidateSelectedLocation()
                    }
                }
                .task(id: locationQuery) {
                    guard store.draft?.baseLocationId == nil else { return }
                    try? await Task.sleep(for: .milliseconds(300))
                    guard !Task.isCancelled, store.draft?.baseLocationId == nil else { return }
                    await store.searchLocations(locationQuery)
                }

            if store.isSearchingLocations {
                ProgressView("Finding places…")
                    .font(.footnote)
            } else if !store.locationResults.isEmpty {
                VStack(spacing: 0) {
                    ForEach(store.locationResults) { location in
                        Button {
                            locationQuery = "\(location.name), \(location.countryName)"
                            Task { await store.selectLocation(location) }
                        } label: {
                            HStack(alignment: .firstTextBaseline) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(location.name)
                                        .foregroundStyle(.primary)
                                    if let region = location.adminRegion, !region.isEmpty {
                                        Text(region)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                Spacer()
                                Text(location.countryName)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.horizontal, 15)
                            .padding(.vertical, 13)
                        }
                        .buttonStyle(.plain)
                        if location.id != store.locationResults.last?.id { Divider() }
                    }
                }
                .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 16))
            } else if locationQuery.count >= 2, draft.baseLocationId == nil {
                Text("Choose a matching place from the suggestions to continue.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if draft.baseLocationId != nil {
                Label("Base set: \(draft.homeLocation)", systemImage: "checkmark.circle.fill")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(FarelinColor.mint)
            }
        }
    }

    private func distanceStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 10) {
            ForEach(Self.distanceOptions, id: \.kilometers) { option in
                SelectionRow(
                    title: option.title,
                    detail: option.detail,
                    selected: draft.maxAirportDistanceKm == option.kilometers
                ) {
                    store.update {
                        $0.maxAirportDistanceKm = option.kilometers
                        $0.maxAirportTravelTimeMinutes = option.minutes
                    }
                }
            }
            Stepper(
                "Custom range: \(draft.maxAirportDistanceKm) km",
                value: Binding(
                    get: { draft.maxAirportDistanceKm },
                    set: { value in
                        store.update { $0.maxAirportDistanceKm = value }
                    }
                ),
                in: 20 ... 600,
                step: 10
            )
            .padding(.top, 8)
            .onChange(of: draft.maxAirportDistanceKm) { _, _ in
                Task { await store.loadRecommendedAirports(preselectLimit: originLimit) }
            }
        }
    }

    private func airportsStep(_ draft: TravelProfileDraft) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("SELECTED \(draft.originAirports.count) / \(originLimit)")
                    .font(.caption2.monospaced().weight(.semibold))
                    .tracking(1)
                    .foregroundStyle(.secondary)
                Spacer()
                if store.isLoadingRecommendations { ProgressView() }
            }

            if store.recommendedAirports.isEmpty, !store.isLoadingRecommendations {
                Text("No scheduled airports were found inside this range. Increase the distance or search manually below.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .farelinCard()
            } else {
                VStack(spacing: 10) {
                    ForEach(store.recommendedAirports) { airport in
                        AirportRow(
                            airport: airport,
                            selected: draft.originAirports.contains(airport.iataCode),
                            disabled: !draft.originAirports.contains(airport.iataCode)
                                && draft.originAirports.count >= originLimit
                        ) {
                            store.toggleAirport(airport, limit: originLimit)
                        }
                    }
                }
            }

            Divider()

            Text("SEARCH ANOTHER AIRPORT")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1)
                .foregroundStyle(.secondary)
            TextField("City, airport, or IATA code", text: $airportQuery)
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .padding(15)
                .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 16))
                .task(id: airportQuery) {
                    try? await Task.sleep(for: .milliseconds(300))
                    guard !Task.isCancelled else { return }
                    await store.searchAirports(airportQuery)
                }
            if store.isSearchingAirports {
                ProgressView("Searching airports…")
            } else {
                ForEach(store.airportResults) { airport in
                    AirportRow(
                        airport: airport,
                        selected: draft.originAirports.contains(airport.iataCode),
                        disabled: !draft.originAirports.contains(airport.iataCode)
                            && draft.originAirports.count >= originLimit
                    ) {
                        store.toggleAirport(airport, limit: originLimit)
                    }
                }
            }
        }
        .task {
            await store.loadRecommendedAirports(preselectLimit: originLimit)
        }
    }

    private func stylesStep(_ draft: TravelProfileDraft) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ForEach(Self.tripStyles, id: \.value) { option in
                SelectableTile(
                    title: option.title,
                    symbol: option.symbol,
                    selected: draft.preferredTripTypes.contains(option.value)
                ) {
                    store.update {
                        if $0.preferredTripTypes.contains(option.value) {
                            $0.preferredTripTypes.removeAll { $0 == option.value }
                        } else {
                            $0.preferredTripTypes.append(option.value)
                        }
                    }
                }
            }
        }
    }

    private func lengthStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 26) {
            ProfileSlider(
                title: "At least",
                value: Binding(
                    get: { draft.preferredTripLengthMin },
                    set: { value in store.update { $0.preferredTripLengthMin = min(value, $0.preferredTripLengthMax) } }
                ),
                range: 1 ... 21
            )
            ProfileSlider(
                title: "At most",
                value: Binding(
                    get: { draft.preferredTripLengthMax },
                    set: { value in store.update { $0.preferredTripLengthMax = max(value, $0.preferredTripLengthMin) } }
                ),
                range: 1 ... 30
            )
        }
        .farelinCard()
    }

    private func budgetStep(_ draft: TravelProfileDraft) -> some View {
        VStack(alignment: .leading, spacing: 22) {
            OptionSection(title: "Deal sensitivity") {
                ForEach(Self.dealOptions, id: \.value) { option in
                    SelectionRow(title: option.title, detail: option.detail, selected: draft.dealSensitivity == option.value) {
                        store.update { $0.dealSensitivity = option.value }
                    }
                }
            }
            OptionSection(title: "Typical flight budget") {
                ForEach(Self.budgetOptions, id: \.value) { option in
                    SelectionRow(title: option.title, detail: nil, selected: draft.budgetComfortZone == option.value) {
                        store.update { $0.budgetComfortZone = option.value }
                    }
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("ABSOLUTE MAXIMUM · OPTIONAL")
                    .font(.caption2.monospaced().weight(.semibold))
                    .tracking(1)
                    .foregroundStyle(.secondary)
                TextField("No hard cap", text: $absoluteBudget)
                    .keyboardType(.decimalPad)
                    .padding(15)
                    .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 16))
                    .onChange(of: absoluteBudget) { _, value in
                        let normalized = value.replacingOccurrences(of: ",", with: ".")
                        store.update { $0.absoluteMaxBudget = Double(normalized) }
                    }
            }
        }
    }

    private func spontaneityStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 10) {
            ForEach(Self.spontaneityOptions, id: \.value) { option in
                SelectionRow(title: option.title, detail: option.detail, selected: draft.spontaneity == option.value) {
                    store.update { $0.spontaneity = option.value }
                }
            }
        }
    }

    private func comfortStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 12) {
            ForEach(Self.comfortRules, id: \.key) { rule in
                VStack(alignment: .leading, spacing: 10) {
                    Text(rule.title).font(.headline)
                    Text(rule.detail).font(.caption).foregroundStyle(.secondary)
                    Picker(
                        rule.title,
                        selection: Binding(
                            get: { draft.comfortRuleModes[rule.key] ?? "off" },
                            set: { value in
                                store.update {
                                    if value == "off" { $0.comfortRuleModes.removeValue(forKey: rule.key) }
                                    else { $0.comfortRuleModes[rule.key] = value }
                                }
                            }
                        )
                    ) {
                        Text(rule.allowed).tag("off")
                        Text(rule.preferred).tag("prefer")
                        Text(rule.required).tag("require")
                    }
                    .pickerStyle(.menu)
                    .tint(FarelinColor.mint)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .farelinCard()
            }
        }
    }

    private func tripShapeStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 10) {
            ForEach(Self.tripShapeOptions, id: \.value) { option in
                SelectionRow(
                    title: option.title,
                    detail: option.detail,
                    selected: draft.openJawWillingness == option.value
                ) {
                    store.update { $0.openJawWillingness = option.value }
                }
            }
        }
    }

    private func notificationsStep(_ draft: TravelProfileDraft) -> some View {
        VStack(spacing: 10) {
            ForEach(Self.notificationOptions, id: \.value) { option in
                SelectionRow(
                    title: option.title,
                    detail: option.detail,
                    selected: draft.notificationFrequency == option.value
                ) {
                    store.update {
                        $0.notificationFrequency = option.value
                        $0.alertTriggerMode = option.value == "urgent_only" ? "route_deal" : "any"
                    }
                }
            }
            Label(
                "Push notifications will be offered separately when native alerts are ready.",
                systemImage: "bell"
            )
            .font(.footnote)
            .foregroundStyle(.secondary)
            .padding(.top, 8)
        }
    }

    private var controls: some View {
        HStack(spacing: 12) {
            if step > 0 {
                Button("Back") {
                    withAnimation(reduceMotion ? nil : .snappy) { step -= 1 }
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
            }
            Button(step == totalSteps - 1 ? "Start exploring" : "Continue") {
                if step == totalSteps - 1 {
                    Task {
                        if await store.save() { dismiss() }
                    }
                } else {
                    withAnimation(reduceMotion ? nil : .snappy) { step += 1 }
                }
            }
            .buttonStyle(FarelinPrimaryButtonStyle())
            .disabled(!stepIsValid || store.isSaving)
            .accessibilityIdentifier("profile-continue")
        }
        .padding(.top, 4)
    }

    private var stepIsValid: Bool {
        guard let draft = store.draft else { return false }
        return switch step {
        case 0: draft.baseLocationId != nil
        case 2: !draft.originAirports.isEmpty && draft.originAirports.count <= originLimit
        case 4: draft.preferredTripLengthMin <= draft.preferredTripLengthMax
        default: true
        }
    }

    private var stepTitle: String {
        [
            "Where are you based?",
            "How far would you travel?",
            "Choose your origin airports",
            "What kind of trips do you love?",
            "How long is your ideal trip?",
            "How do you feel about price?",
            "How spontaneous are you?",
            "What should Farelin avoid?",
            "How adventurous should routes be?",
            "How should we tell you?",
        ][step]
    }

    private var stepSubtitle: String {
        [
            "Choose a real city or town. Farelin uses it only to recommend practical departure airports.",
            "This is straight-line distance for now; real driving and rail times come later.",
            "Nearby scheduled airports are recommended automatically. You remain in control.",
            "These preferences improve fit scores. Very cheap alternatives can still appear.",
            "This becomes a default, and a specific search can always override it.",
            "Budget shapes ranking and alerts. It does not pretend observed fares are guaranteed.",
            "When you omit dates, this chooses a sensible default window.",
            "Allowed keeps options open. Prefer changes ranking. Never show applies a hard filter.",
            "Farelin can keep trips simple or connect nearby cities when the data supports it.",
            "Choose the email rhythm for new watches. Each watch can be changed later.",
        ][step]
    }
}

private struct SelectionRow: View {
    let title: String
    let detail: String?
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 13) {
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(selected ? FarelinColor.mint : .secondary)
                    .font(.title3)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.headline).foregroundStyle(.primary)
                    if let detail {
                        Text(detail).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
                    }
                }
                Spacer()
            }
            .farelinCard()
        }
        .buttonStyle(.plain)
    }
}

private struct AirportRow: View {
    let airport: AirportResult
    let selected: Bool
    let disabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 13) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(airport.city ?? airport.name).font(.headline)
                        Text(airport.iataCode).font(.subheadline.monospaced().weight(.semibold))
                    }
                    Text(airportDetail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
                Spacer()
                Image(systemName: selected ? "checkmark.circle.fill" : "plus.circle")
                    .font(.title3)
                    .foregroundStyle(selected ? FarelinColor.mint : .secondary)
            }
            .farelinCard()
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .opacity(disabled ? 0.45 : 1)
    }

    private var airportDetail: String {
        var values = [airport.name, airport.countryName]
        if let distance = airport.distanceKm { values.append("\(Int(distance.rounded())) km away") }
        return values.joined(separator: " · ")
    }
}

private struct SelectableTile: View {
    let title: String
    let symbol: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 18) {
                Image(systemName: symbol)
                    .font(.title2)
                    .foregroundStyle(selected ? FarelinColor.ink : FarelinColor.mint)
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(selected ? FarelinColor.ink : .primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(16)
            .frame(minHeight: 112)
            .background(selected ? FarelinColor.mint : Color(.secondarySystemBackground), in: .rect(cornerRadius: 18))
        }
        .buttonStyle(.plain)
    }
}

private struct ProfileSlider: View {
    let title: String
    @Binding var value: Int
    let range: ClosedRange<Int>

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Text(title).foregroundStyle(.secondary)
                Spacer()
                Text("\(value) days").font(.headline.monospacedDigit())
            }
            Slider(
                value: Binding(get: { Double(value) }, set: { value = Int($0.rounded()) }),
                in: Double(range.lowerBound) ... Double(range.upperBound),
                step: 1
            )
            .tint(FarelinColor.mint)
        }
    }
}

private struct OptionSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1)
                .foregroundStyle(.secondary)
            content
        }
    }
}

private extension TravelProfileView {
    static let distanceOptions = [
        (kilometers: 50, minutes: 30, title: "Nearby only", detail: "About 30 minutes · 50 km"),
        (kilometers: 100, minutes: 60, title: "Up to an hour", detail: "About 100 km"),
        (kilometers: 200, minutes: 120, title: "Up to two hours", detail: "About 200 km"),
        (kilometers: 300, minutes: 180, title: "Up to three hours", detail: "About 300 km"),
        (kilometers: 450, minutes: 240, title: "Four hours or more", detail: "About 450 km"),
    ]

    static let tripStyles = [
        (value: "weekend_city_break", title: "Weekend cities", symbol: "building.2"),
        (value: "beach", title: "Beach", symbol: "beach.umbrella"),
        (value: "food", title: "Food", symbol: "fork.knife"),
        (value: "culture", title: "Culture & design", symbol: "building.columns"),
        (value: "nature", title: "Nature & hikes", symbol: "mountain.2"),
        (value: "nightlife", title: "Nightlife", symbol: "moon.stars"),
        (value: "cheap_adventure", title: "Cheap adventures", symbol: "dice"),
        (value: "long_haul_dream", title: "Long-haul dreams", symbol: "airplane.departure"),
    ]

    static let dealOptions = [
        (value: "strict", title: "Only unusually cheap deals", detail: "Prioritize the strongest price anomalies."),
        (value: "balanced", title: "Balance price and comfort", detail: "A practical mix of price, timing, and route quality."),
        (value: "flexible", title: "Pay more for the right trip", detail: "Destination and timing can outweigh the lowest fare."),
    ]

    static let budgetOptions = [
        (value: "under_100", title: "Under €100"),
        (value: "under_200", title: "€100–€200"),
        (value: "under_400", title: "€200–€400"),
        (value: "flexible", title: "Flexible"),
    ]

    static let spontaneityOptions = [
        (value: "very_spontaneous", title: "Within days", detail: "Default window: now through the next three weeks."),
        (value: "soon", title: "Next week", detail: "Default window: roughly one to six weeks ahead."),
        (value: "flexible_monthly", title: "A few weeks", detail: "Default window: roughly three weeks to three months."),
        (value: "planner", title: "At least a month", detail: "Default window: one to six months ahead."),
        (value: "long_term_planner", title: "Two months or more", detail: "Default window: two to nine months ahead."),
    ]

    struct ComfortCopy {
        let key: String
        let title: String
        let detail: String
        let allowed: String
        let preferred: String
        let required: String
    }

    static let comfortRules = [
        ComfortCopy(key: "direct_only", title: "Connecting flights", detail: "How strongly should Farelin favor nonstop routes?", allowed: "Connections allowed", preferred: "Prefer direct", required: "Direct only"),
        ComfortCopy(key: "max_one_stop", title: "Trips with two or more stops", detail: "Long chains can be cheaper, but take more energy.", allowed: "Allowed", preferred: "Prefer max one", required: "Never show"),
        ComfortCopy(key: "avoid_overnight_layovers", title: "Overnight layovers", detail: "Connections that require a night in transit.", allowed: "Allowed", preferred: "Prefer to avoid", required: "Never show"),
        ComfortCopy(key: "no_departures_before_6am", title: "Departures before 6am", detail: "Very early flights may add taxi or hotel costs.", allowed: "Allowed", preferred: "Prefer to avoid", required: "Never show"),
        ComfortCopy(key: "no_returns_after_midnight", title: "Arrivals after midnight", detail: "Late arrivals can make the final journey harder.", allowed: "Allowed", preferred: "Prefer to avoid", required: "Never show"),
        ComfortCopy(key: "cabin_bag_included", title: "Cabin bag", detail: "Some observed fares include only a personal item.", allowed: "Not important", preferred: "Prefer included", required: "Must include"),
    ]

    static let tripShapeOptions = [
        (value: "simple_returns_only", title: "Simple returns only", detail: "Fly out and back from the same city."),
        (value: "nearby_city_open_jaw", title: "Nearby-city open-jaw", detail: "Land in one city and return from another nearby."),
        (value: "adventurous_multi_city", title: "Adventurous multi-city", detail: "Connect several cities when the complete route makes sense."),
    ]

    static let notificationOptions = [
        (value: "instant_email", title: "Deal alerts", detail: "Email when a watched fare qualifies, at the fastest schedule in your plan."),
        (value: "weekly_digest", title: "Weekly digest", detail: "A calmer weekly rhythm for qualifying trip ideas."),
        (value: "urgent_only", title: "Urgent deals only", detail: "Only email unusually strong route deals."),
    ]
}
