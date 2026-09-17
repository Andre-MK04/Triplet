import SwiftUI

struct DiscoverView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let store: TripSearchStore
    let opportunities: OpportunityStore
    let originAirports: [String]
    let accountEmail: String
    let tripDetailService: any TripDetailServicing
    let watchService: any NativeWatchCreating
    let fareService: any NativeFareSaving
    let onWatchSaved: () -> Void
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?

    @FocusState private var promptFocused: Bool
    @State private var searchMode = DiscoverSearchMode.advanced
    @State private var watchTrip: SearchTrip?
    @State private var showPrecision = false
    @State private var showObservedBoard = false
    @State private var revealStep = 0
    @State private var budgetCheckpoint = 3.0
    @State private var durationNights = 6.0
    @State private var allowNearbyLengths = true
    @State private var showCustomDates = false
    private let budgetPoints = [50, 100, 150, 200, 300, 400, 600, 800, 1000, 1500]

    private let examples = [
        "A warm food-focused week in October under €300",
        "A quiet Nordic weekend next month with direct flights",
        "Surprise me with a nature trip for five to seven days",
    ]

    var body: some View {
        NavigationStack {
            Group {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        introduction
                        if store.response == nil && !store.isSearching && store.errorMessage == nil {
                            opportunityPreview
                            if showObservedBoard { opportunityBoard }
                        }
                        if store.response == nil {
                            Picker("Search mode", selection: $searchMode) {
                                Text("Ask Farelin").tag(DiscoverSearchMode.ai)
                                Text("Explore").tag(DiscoverSearchMode.advanced)
                            }
                            .pickerStyle(.segmented)
                            .disabled(store.isSearching)
                            .accessibilityIdentifier("discover-mode")
                            searchComposer
                        }
                        VStack(alignment: .leading, spacing: 18) {
                            if store.isSearching {
                                searchingState
                            } else if let error = store.errorMessage {
                                errorState(error)
                            } else if let response = store.response {
                                resultActions
                                results(response)
                            } else {
                                startingState
                            }
                        }
                        .id("discover-outcome")
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 36)
                }
                // Compose/results have independent scroll lifetimes. Never
                // animate to a height-dependent anchor while removing a form.
                .id("\(searchMode)-\(store.response != nil)")
                .onChange(of: store.isSearching) { _, searching in
                    if !searching { promptFocused = false }
                }
                .sensoryFeedback(.success, trigger: store.response != nil) { _, hasResults in
                    hasResults && !(store.response?.trips.isEmpty ?? true)
                }
                .scrollDismissesKeyboard(.interactively)
                .background(Color(.systemBackground))
                .navigationTitle("Discover")
                .task { await opportunities.load() }
                .onChange(of: store.query) { _, newValue in
                    if !newValue.isEmpty { searchMode = .ai }
                }
                .task(id: store.placeQuery) {
                    guard searchMode == .advanced else { return }
                    try? await Task.sleep(for: .milliseconds(350))
                    guard !Task.isCancelled else { return }
                    await store.searchPlaces()
                }
                .sheet(item: $watchTrip) { trip in
                    WatchCreationSheet(
                        trip: trip,
                        parsed: store.response?.parsedRequest,
                        fallbackOrigins: originAirports,
                        accountEmail: accountEmail,
                        service: watchService,
                        reauthenticate: reauthenticate,
                        onSaved: onWatchSaved
                    )
                    .presentationDetents([.medium, .large])
                }
            }
        }
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 8) {
            FarelinSectionLabel(
                title: searchMode == .ai ? "ASK FARELIN" : "FROM YOUR AIRPORTS",
                accented: true
            )
            Text(searchMode == .ai ? "Ask for a trip." : "Where to next?")
                .font(FarelinTypography.display(size: 30, weight: .bold))
                .tracking(-0.8)
            Text(
                searchMode == .ai
                    ? "Describe the trip naturally. Farelin uses your profile unless you override it here."
                    : "Your profile fills anything you skip."
            )
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)
                .lineSpacing(3)
        }
        .padding(.top, 8)
    }

    private var opportunityPreview: some View {
        Button {
            withAnimation(reduceMotion ? nil : .snappy(duration: 0.25)) {
                showObservedBoard.toggle()
            }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "sparkle.magnifyingglass")
                    .foregroundStyle(FarelinColor.mint)
                if let feed = opportunities.feed, let first = feed.trips.first {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("FARE SIGHTING · TAP TO EXPLORE")
                            .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                            .foregroundStyle(.secondary)
                        Text("\(first.routeTitle) · \(FarelinSearchFormat.priceHeadline(first))")
                            .font(FarelinTypography.font(.subheadline, weight: .semibold))
                            .lineLimit(2)
                    }
                } else {
                    Text("See observed fares from your airports")
                        .font(FarelinTypography.font(.subheadline))
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Image(systemName: showObservedBoard ? "chevron.up" : "chevron.down")
                    .font(FarelinTypography.font(.caption, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, 7)
        }
        .buttonStyle(.plain)
        .accessibilityValue(showObservedBoard ? "Expanded" : "Collapsed")
        .accessibilityIdentifier("discover-fare-preview")
    }

    private var opportunityBoard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Observed opportunities")
                .font(FarelinTypography.font(.title3, weight: .bold))
            if opportunities.isLoading {
                ProgressView("Checking observed fares from your airports…")
            } else if let error = opportunities.errorMessage {
                Text("Your fare board could not load: \(error). Search trips below instead.")
                    .font(FarelinTypography.font(.subheadline))
                    .foregroundStyle(.secondary)
            } else if let feed = opportunities.feed {
                if feed.isStale {
                    Text("Some fare sightings are older. Check the current price with the provider.")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.orange)
                }
                if feed.trips.isEmpty {
                    Text(feed.originAirports.isEmpty
                         ? "Choose your departure airports in your travel profile to see your own opportunities."
                         : "No usable observed returns are cached for your airports yet. Search below to check more routes.")
                        .font(FarelinTypography.font(.subheadline))
                        .foregroundStyle(.secondary)
                } else {
                    Text("Observed returns from \(feed.originAirports.joined(separator: ", ")). Prices can change.")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                    ForEach(feed.trips.prefix(4)) { trip in
                        NativeTripCard(
                            trip: trip,
                            tripDetailService: tripDetailService,
                            onSaveWatch: { watchTrip = trip },
                            fareService: fareService,
                            reauthenticate: reauthenticate
                        )
                    }
                }
            }
        }
        .accessibilityIdentifier("observed-opportunities")
    }

    private var searchComposer: some View {
        Group {
            if searchMode == .ai {
                aiSearchComposer
            } else {
                advancedSearchComposer
            }
        }
        .id("discover-composer")
    }

    private var resultActions: some View {
        HStack(spacing: 12) {
            Label("Your trip search", systemImage: "checkmark.circle")
                .font(FarelinTypography.font(.subheadline, weight: .semibold))
            Spacer(minLength: 0)
            Button {
                store.clearResults()
            } label: {
                Label("Edit search", systemImage: "slider.horizontal.3")
                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
                    .padding(.vertical, 12)
            }
            .accessibilityHint("Keeps your search choices. Does not run another search.")
            .accessibilityIdentifier("discover-edit-search")
        }
    }

    private var aiSearchComposer: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Flying from")
                    .font(FarelinTypography.font(.caption, weight: .semibold))
                    .foregroundStyle(.secondary)
                if originAirports.isEmpty {
                    Text("No profile airports selected")
                        .font(FarelinTypography.font(.subheadline))
                        .foregroundStyle(FarelinColor.coral)
                } else {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(originAirports, id: \.self) { code in
                                Text(code)
                                    .font(FarelinTypography.font(.caption, weight: .bold, family: .mono))
                                    .padding(.horizontal, 11)
                                    .padding(.vertical, 7)
                                    .background(FarelinColor.mint.opacity(0.16), in: Capsule())
                            }
                        }
                    }
                }
            }

            ZStack(alignment: .topLeading) {
                if store.query.isEmpty {
                    Text("For example: five days somewhere warm in November, under €250…")
                        .foregroundStyle(.tertiary)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 8)
                        .allowsHitTesting(false)
                }
                TextEditor(text: Binding(
                    get: { store.query },
                    set: { store.query = $0 }
                ))
                .focused($promptFocused)
                .frame(minHeight: 112)
                .scrollContentBackground(.hidden)
                .textInputAutocapitalization(.sentences)
                .accessibilityIdentifier("discover-prompt")
            }
            .padding(12)
            .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 18))
            .overlay {
                RoundedRectangle(cornerRadius: 18)
                    .stroke(promptFocused ? FarelinColor.mint : Color(.separator), lineWidth: 1)
            }

            VStack(spacing: 8) {
                    ForEach(Array(examples.enumerated()), id: \.offset) { index, example in
                        Button {
                            store.useExample(example)
                            promptFocused = true
                        } label: {
                            Text(example)
                                .font(FarelinTypography.font(.caption))
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                                .padding(.horizontal, 12)
                                .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
                                .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 13))
                                .overlay { RoundedRectangle(cornerRadius: 13).stroke(Color(.separator).opacity(0.5)) }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("prompt-example-\(index)")
                    }
            }

            Button {
                promptFocused = false
                store.submit(origins: originAirports)
            } label: {
                Label("Find trips", systemImage: "location.magnifyingglass")
            }
            .buttonStyle(FarelinPrimaryButtonStyle())
            .disabled(store.isSearching || store.query.trimmingCharacters(in: .whitespacesAndNewlines).count < 8)
            .accessibilityIdentifier("discover-search")
        }
        .farelinCard()
    }

    private var advancedSearchComposer: some View {
        VStack(alignment: .leading, spacing: 15) {
            quickSearchControls
            if revealStep >= 4 {
            Divider()
            advancedTripShape
            }
            if revealStep >= 5 {
            advancedDestinations
            DisclosureGroup(isExpanded: $showPrecision) {
                VStack(alignment: .leading, spacing: 17) {
                    advancedOrigins
                    connectionControls
                    Button("Reset to profile defaults") {
                        resetComposerDefaults()
                        revealStep = 0
                    }
                    .font(FarelinTypography.font(.caption, weight: .semibold))
                }
                .padding(.top, 12)
            } label: {
                Label("Refine airports, places & comfort", systemImage: "slider.horizontal.3")
                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
            }
            .tint(FarelinColor.action)
            .accessibilityIdentifier("discover-precision")

            Button {
                promptFocused = false
                store.submitAdvanced(profileOrigins: originAirports)
            } label: {
                Label("Find trips", systemImage: "slider.horizontal.3")
            }
            .buttonStyle(FarelinPrimaryButtonStyle())
            .disabled(store.isSearching)
            .accessibilityIdentifier("advanced-search")
            }
        }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.22), value: revealStep)
        .farelinCard()
    }

    private var quickSearchControls: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                FarelinSectionLabel(title: "THE ESSENTIALS", accented: true)
                Spacer()
                Button("Use my defaults") {
                    resetComposerDefaults()
                    revealStep = 5
                }
                .font(FarelinTypography.font(.caption, weight: .semibold))
            }
            Text("WHEN").font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono)).foregroundStyle(.secondary)
            HStack(spacing: 8) {
                quickButton("Soon", selected: dateWindowIs(7, 45)) { setDateWindow(7, 45); advance(to: 1) }
                quickButton("Next 3 months", selected: dateWindowIs(21, 90)) { setDateWindow(21, 90); advance(to: 1) }
                quickButton("Flexible", selected: dateWindowIs(7, 270)) { setDateWindow(7, 270); advance(to: 1) }
            }
            Button("Choose dates") { showCustomDates.toggle() }
                .font(FarelinTypography.font(.caption, weight: .semibold))
            if showCustomDates {
                DatePicker("From", selection: Binding(get: { store.advanced.startDate }, set: {
                    store.advanced.startDate = $0
                    store.advanced.endDate = max(store.advanced.endDate, $0)
                    store.advanced.useProfileDates = false
                }), in: Date.now..., displayedComponents: .date)
                DatePicker("Until", selection: Binding(get: { store.advanced.endDate }, set: {
                    store.advanced.endDate = $0
                    store.advanced.useProfileDates = false
                }), in: store.advanced.startDate..., displayedComponents: .date)
                Button("Use these dates") { store.advanced.useProfileDates = false; advance(to: 1) }
            }
            if revealStep >= 1 {
            Text("FLIGHT BUDGET").font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono)).foregroundStyle(.secondary)
            HStack {
                Text(store.advanced.flexibleBudget ? "Flexible" : store.advanced.budgetText.isEmpty ? "Profile default" : "Up to €\(store.advanced.budgetText)")
                    .font(FarelinTypography.font(.title3, weight: .semibold)).contentTransition(.numericText())
                    .accessibilityIdentifier("explore-budget-value")
                Spacer()
                Button("Flexible") {
                    store.advanced.budgetText = ""
                    store.advanced.flexibleBudget = true
                    advance(to: 2)
                }
                .font(FarelinTypography.font(.subheadline, weight: .semibold))
                .accessibilityIdentifier("explore-flexible-budget")
            }
            Slider(value: Binding(get: { budgetCheckpoint }, set: {
                budgetCheckpoint = $0.rounded()
                store.advanced.budgetText = String(budgetPoints[Int(budgetCheckpoint)])
                store.advanced.flexibleBudget = false
            }), in: 0...Double(budgetPoints.count - 1), step: 1, onEditingChanged: {
                if !$0 { chooseBudget() }
            })
            .tint(FarelinColor.action)
            .accessibilityLabel("Flight budget")
            .accessibilityValue(store.advanced.flexibleBudget ? "Flexible" : "\(budgetPoints[Int(budgetCheckpoint)]) euros")
            .accessibilityIdentifier("explore-budget-slider")
            HStack {
                ForEach(budgetPoints, id: \.self) { point in
                    Circle().fill(FarelinColor.action.opacity(0.45)).frame(width: 4, height: 4)
                    if point != budgetPoints.last { Spacer() }
                }
            }.padding(.horizontal, 7).accessibilityHidden(true)
            HStack { Text("€50"); Spacer(); Text("€1,500") }
                .font(FarelinTypography.font(.caption2)).foregroundStyle(.secondary)
            Button("Use this budget") { chooseBudget() }.font(FarelinTypography.font(.caption, weight: .semibold))
            }
            if revealStep >= 2 {
            Text("HOW LONG").font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono)).foregroundStyle(.secondary)
            Text(store.advanced.useProfileTripLength ? "Profile length" : "\(Int(durationNights)) nights")
                .font(FarelinTypography.font(.title3, weight: .semibold)).contentTransition(.numericText())
                .accessibilityIdentifier("explore-duration-value")
            Slider(value: Binding(get: { durationNights }, set: {
                durationNights = $0.rounded()
                applyLength()
            }), in: 1...30, step: 1, onEditingChanged: { if !$0 { advance(to: 3) } })
                .tint(FarelinColor.action)
                .accessibilityLabel("Trip duration")
                .accessibilityIdentifier("explore-duration-slider")
            Toggle("Allow one night either way", isOn: $allowNearbyLengths)
                .font(FarelinTypography.font(.subheadline)).tint(FarelinColor.action)
                .onChange(of: allowNearbyLengths) { _, _ in applyLength() }
            Button("Use this length") { applyLength(); advance(to: 3) }.font(FarelinTypography.font(.caption, weight: .semibold))
            }
            if revealStep >= 3 {
            Text("TRAVEL MOOD").font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono)).foregroundStyle(.secondary)
            FlowLayout(spacing: 8) {
                    ForEach([("beach", "Beach"), ("food", "Food"), ("nature", "Nature"),
                             ("culture", "Culture"), ("cheap_adventure", "Adventure")], id: \.0) { mood in
                        moodButton(mood.1, selected: store.advanced.travelStyles.contains(mood.0)) {
                            store.toggleTravelStyle(mood.0)
                            advance(to: 4)
                        }
                    }
            }
            Button("Use profile mood") {
                store.advanced.travelStyles = []
                advance(to: 4)
            }.font(FarelinTypography.font(.caption, weight: .semibold))
            }
        }
        .sensoryFeedback(.selection, trigger: revealStep)
        .sensoryFeedback(.selection, trigger: budgetCheckpoint)
    }

    private func advance(to step: Int) { revealStep = max(revealStep, step) }

    private func resetComposerDefaults() {
        store.resetAdvancedOverrides()
        budgetCheckpoint = 3
        durationNights = 6
        allowNearbyLengths = true
        showCustomDates = false
        showPrecision = false
    }

    private func chooseBudget() {
        store.advanced.budgetText = String(budgetPoints[Int(budgetCheckpoint)])
        store.advanced.flexibleBudget = false
        advance(to: 2)
    }

    private func applyLength() {
        let nights = Int(durationNights)
        store.advanced.useProfileTripLength = false
        store.advanced.minTripLengthDays = max(1, nights - (allowNearbyLengths ? 1 : 0))
        store.advanced.maxTripLengthDays = min(30, nights + (allowNearbyLengths ? 1 : 0))
    }

    private func quickButton(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(FarelinTypography.font(.caption, weight: .semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .frame(maxWidth: .infinity, minHeight: 44)
                .background(selected ? FarelinColor.mint.opacity(0.18) : Color(.tertiarySystemBackground), in: .rect(cornerRadius: 12))
                .overlay { RoundedRectangle(cornerRadius: 12).stroke(selected ? FarelinColor.mint : Color(.separator), lineWidth: 1) }
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func moodButton(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(FarelinTypography.font(.caption, weight: .semibold))
                .lineLimit(1)
                .fixedSize(horizontal: true, vertical: false)
                .padding(.horizontal, 16)
                .frame(minHeight: 44)
                .background(selected ? FarelinColor.mint.opacity(0.18) : Color(.tertiarySystemBackground), in: .rect(cornerRadius: 12))
                .overlay { RoundedRectangle(cornerRadius: 12).stroke(selected ? FarelinColor.mint : Color(.separator), lineWidth: 1) }
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func forBudget(_ value: Int) -> some View {
        quickButton("€\(value)", selected: store.advanced.budgetText == String(value)) {
            store.advanced.budgetText = String(value)
        }
    }

    private func quickLength(_ title: String, min: Int, max: Int) -> some View {
        quickButton(title, selected: !store.advanced.useProfileTripLength && store.advanced.minTripLengthDays == min && store.advanced.maxTripLengthDays == max) {
            store.advanced.useProfileTripLength = false
            store.advanced.minTripLengthDays = min
            store.advanced.maxTripLengthDays = max
        }
    }

    private func setDateWindow(_ start: Int, _ end: Int) {
        store.advanced.useProfileDates = false
        store.advanced.startDate = Calendar.current.date(byAdding: .day, value: start, to: Calendar.current.startOfDay(for: .now)) ?? .now
        store.advanced.endDate = Calendar.current.date(byAdding: .day, value: end, to: Calendar.current.startOfDay(for: .now)) ?? .now
    }

    private func dateWindowIs(_ start: Int, _ end: Int) -> Bool {
        let today = Calendar.current.startOfDay(for: .now)
        return !store.advanced.useProfileDates &&
            Calendar.current.dateComponents([.day], from: today, to: store.advanced.startDate).day == start &&
            Calendar.current.dateComponents([.day], from: today, to: store.advanced.endDate).day == end
    }

    private var advancedTripShape: some View {
        VStack(alignment: .leading, spacing: 12) {
            advancedHeading("Trip shape", source: "search")

            HStack(spacing: 8) {
                tripShapeButton(
                    value: "return",
                    title: "Return",
                    systemImage: "arrow.triangle.2.circlepath"
                )
                tripShapeButton(
                    value: "open_jaw",
                    title: "Open-jaw",
                    systemImage: "arrow.triangle.branch"
                )
                tripShapeButton(
                    value: "multi_city",
                    title: "Multi-city",
                    systemImage: "point.3.connected.trianglepath.dotted"
                )
            }

            Text(tripShapeExplanation)
                .font(FarelinTypography.font(.caption))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("trip-shape-explanation")
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-shape-selector")
    }

    private func tripShapeButton(value: String, title: String, systemImage: String) -> some View {
        let selected = store.advanced.tripPlan == value
        return Button {
            withAnimation(reduceMotion ? nil : .snappy(duration: 0.2)) {
                store.advanced.tripPlan = value
                advance(to: 5)
            }
        } label: {
            VStack(spacing: 7) {
                Image(systemName: systemImage)
                    .font(FarelinTypography.font(.body, weight: .semibold))
                Text(title)
                    .font(FarelinTypography.font(.caption, weight: .semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity, minHeight: 62)
            .padding(.horizontal, 4)
            .foregroundStyle(selected ? FarelinColor.ink : Color.primary)
            .background(
                selected ? FarelinColor.mint : Color(.tertiarySystemBackground),
                in: .rect(cornerRadius: 14)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(selected ? FarelinColor.mint : Color(.separator).opacity(0.55))
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityValue(selected ? "Selected" : "Not selected")
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityIdentifier("trip-shape-\(value)")
    }

    private var tripShapeExplanation: String {
        switch store.advanced.tripPlan {
        case "open_jaw":
            return "Add two places in order, or choose one region and Farelin will propose fare-backed routes."
        case "multi_city":
            return "Add places in order, or choose a region, country or continent to explore fare-backed routes."
        default:
            return "Fly to one destination and return to your origin airport."
        }
    }

    private var advancedOrigins: some View {
        VStack(alignment: .leading, spacing: 11) {
            advancedHeading("Flying from", source: store.advanced.useProfileOrigins ? "profile" : "search")
            Toggle("Use all profile airports", isOn: Binding(
                get: { store.advanced.useProfileOrigins },
                set: { store.setUseProfileOrigins($0, profileOrigins: originAirports) }
            ))
            .tint(FarelinColor.mint)

            if !store.advanced.useProfileOrigins {
                FlowLayout(spacing: 8) {
                    ForEach(originAirports, id: \.self) { code in
                        Button {
                            store.toggleOrigin(code)
                        } label: {
                            selectableChip(code, selected: store.advanced.selectedOrigins.contains(code))
                        }
                        .buttonStyle(.plain)
                    }
                }
            } else {
                Text(originAirports.joined(separator: " · "))
                    .font(FarelinTypography.font(.subheadline, weight: .medium, family: .mono))
                    .foregroundStyle(originAirports.isEmpty ? FarelinColor.coral : .secondary)
            }
        }
    }

    private var advancedDestinations: some View {
        VStack(alignment: .leading, spacing: 11) {
            advancedHeading(
                advancedDestinationHeading,
                source: store.advanced.destinations.isEmpty ? "default" : "search"
            )
            if store.advanced.destinations.isEmpty {
                Text(advancedDestinationHelp)
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.secondary)
            } else {
                VStack(spacing: 8) {
                    ForEach(Array(store.advanced.destinations.enumerated()), id: \.element.id) { index, place in
                        HStack(spacing: 10) {
                            destinationOrderMarker(index: index)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(place.name)
                                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
                                Text("\(place.code.uppercased()) · \(place.subtitle)")
                                    .font(FarelinTypography.font(.caption))
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button {
                                store.removeDestination(place)
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Remove \(place.name)")
                        }
                    }
                }
            }

            TextField("Search places", text: Binding(
                get: { store.placeQuery },
                set: { store.placeQuery = $0 }
            ))
            .textInputAutocapitalization(.words)
            .padding(12)
            .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 13))
            .overlay { RoundedRectangle(cornerRadius: 13).stroke(Color(.separator).opacity(0.5)) }
            .accessibilityIdentifier("advanced-destination")

            if store.isSearchingPlaces {
                ProgressView("Looking up places…")
                    .font(FarelinTypography.font(.caption))
            } else if !store.placeResults.isEmpty {
                VStack(spacing: 0) {
                    ForEach(store.placeResults.prefix(7)) { place in
                        Button {
                            store.addDestination(place)
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(place.name)
                                        .font(FarelinTypography.font(.subheadline, weight: .medium))
                                    Text("\(place.code.uppercased()) · \(place.subtitle)")
                                        .font(FarelinTypography.font(.caption))
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: "plus.circle")
                                    .foregroundStyle(FarelinColor.mint)
                            }
                            .padding(.vertical, 10)
                        }
                        .buttonStyle(.plain)
                        if place.id != store.placeResults.prefix(7).last?.id { Divider() }
                    }
                }
            }
        }
    }

    private var advancedDestinationHeading: String {
        switch store.advanced.tripPlan {
        case "open_jaw": "Land in / fly home from, or explore a region"
        case "multi_city": "Destinations or region"
        default: "Where"
        }
    }

    private var advancedDestinationHelp: String {
        switch store.advanced.tripPlan {
        case "open_jaw":
            "Choose two cities in order, or one region, country or continent."
        case "multi_city":
            "Choose two or more cities in order, or one region, country or continent. Farelin checks actual observed fares before proposing a route."
        default:
            "Leave blank for anywhere, or search a city, airport, country, region or continent."
        }
    }

    @ViewBuilder
    private func destinationOrderMarker(index: Int) -> some View {
        if store.advanced.tripPlan == "multi_city" {
            Text("\(index + 1)")
                .font(FarelinTypography.font(.caption, weight: .bold, family: .mono))
                .frame(width: 24, height: 24)
                .background(FarelinColor.mint.opacity(0.18), in: Circle())
        } else if store.advanced.tripPlan == "open_jaw" {
            Image(systemName: index == 0 ? "airplane.arrival" : "airplane.departure")
                .font(FarelinTypography.font(.caption, weight: .semibold))
                .foregroundStyle(FarelinColor.mint)
                .frame(width: 24, height: 24)
                .accessibilityLabel(index == 0 ? "Land in" : "Fly home from")
        }
    }

    private var connectionControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Connections", selection: Binding(
                get: { store.advanced.directPreference },
                set: { store.advanced.directPreference = $0 }
            )) {
                Text("Profile default").tag("profile")
                Text("Direct only").tag("direct")
                Text("Maximum one stop").tag("one_stop")
                Text("Any connections").tag("connections")
            }
            Picker("Cabin bag", selection: Binding(
                get: { store.advanced.baggagePreference },
                set: { store.advanced.baggagePreference = $0 }
            )) {
                Text("Profile default").tag("profile")
                Text("Not required").tag("not_required")
                Text("Included").tag("included")
            }
        }
    }

    private func advancedHeading(_ title: String, source: String) -> some View {
        HStack {
            Text(title)
                .font(FarelinTypography.font(.headline))
            Spacer()
            profileSourceLabel(source == "search" ? "This search" : source == "profile" ? "Profile" : "Default")
        }
    }

    private func profileSourceLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(FarelinTypography.mono(size: 9, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(.secondary)
    }

    private func selectableChip(_ text: String, selected: Bool) -> some View {
        Text(text)
            .font(FarelinTypography.font(.caption, weight: .semibold))
            .padding(.horizontal, 11)
            .padding(.vertical, 8)
            .foregroundStyle(selected ? FarelinColor.ink : Color.primary)
            .background(selected ? FarelinColor.mint : Color(.tertiarySystemBackground), in: Capsule())
            .overlay { Capsule().stroke(selected ? FarelinColor.mint : Color(.separator).opacity(0.5)) }
    }

    private var searchingState: some View {
        HStack(spacing: 14) {
            ProgressView()
                .tint(FarelinColor.mint)
            VStack(alignment: .leading, spacing: 3) {
                Text(store.progressMessage)
                    .font(FarelinTypography.font(.headline))
                Text("Farelin only summarizes fares returned by the backend.")
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .farelinCard()
        .accessibilityIdentifier("discover-loading")
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("That search didn’t finish", systemImage: "exclamationmark.triangle")
                .font(FarelinTypography.font(.headline))
                .foregroundStyle(FarelinColor.coral)
            Text(message)
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)
            Button("Try again") {
                if searchMode == .ai {
                    store.submit(origins: originAirports)
                } else {
                    store.submitAdvanced(profileOrigins: originAirports)
                }
            }
            .buttonStyle(.bordered)
            if searchMode == .ai {
                Button("Use Explore instead — no AI search") {
                    store.clearResults()
                    searchMode = .advanced
                }
                .font(FarelinTypography.font(.subheadline))
                Text("Explore uses the controls you choose there, not the unparsed prompt.")
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .farelinCard()
    }

    private var startingState: some View {
        VStack(alignment: .leading, spacing: 13) {
            Image(systemName: "point.3.connected.trianglepath.dotted")
                .font(FarelinTypography.font(.title2))
                .foregroundStyle(FarelinColor.mint)
            Text(searchMode == .ai ? "One request, complete trip ideas" : "Precise controls, no AI allowance used")
                .font(FarelinTypography.font(.headline))
            Text(
                searchMode == .ai
                    ? "Dates, budgets and places you name here override your profile. Anything you leave vague comes from your saved travel defaults."
                    : "Advanced search calls the fare engine directly. Explicit controls override your profile; untouched fields keep your defaults."
            )
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)
                .lineSpacing(3)
        }
        .farelinCard()
    }

    @ViewBuilder
    private func results(_ response: FarelinAISearchResponse) -> some View {
        if !response.message.isEmpty {
            VStack(alignment: .leading, spacing: 7) {
                Text("Farelin")
                    .font(FarelinTypography.font(.caption, weight: .semibold, family: .mono))
                    .foregroundStyle(FarelinColor.mint)
                Text(plainText(response.message))
                    .font(FarelinTypography.font(.body))
                    .lineSpacing(3)
            }
            .farelinCard()
        }

        if let parsed = response.parsedRequest {
            parsedSummary(parsed, sourceMap: response.sourceMap, hardBudgetApplied: response.hardBudgetApplied)
        }

        if let notice = providerNotice(response.providerMetadata) {
            Label(notice.text, systemImage: notice.warning ? "exclamationmark.triangle" : "clock.arrow.circlepath")
                .font(FarelinTypography.font(.footnote))
                .foregroundStyle(notice.warning ? FarelinColor.coral : .secondary)
                .farelinCard()
        }

        if let relaxation = response.relaxationNote, !relaxation.isEmpty {
            Label(relaxation, systemImage: "arrow.triangle.2.circlepath")
                .font(FarelinTypography.font(.footnote))
                .foregroundStyle(.secondary)
                .farelinCard()
        }

        if response.trips.isEmpty {
            ContentUnavailableView {
                Label("No observed fares found", systemImage: "airplane.arrival")
            } description: {
                Text("There are no usable fare observations for this search right now. Try different dates or a broader destination. Check availability and final prices with the provider.")
            } actions: {
                VStack(spacing: 10) {
                    Button("Edit search") { store.clearResults() }
                        .buttonStyle(.borderedProminent)
                    if store.canReviewWiderDates {
                        Button("Review 30 more days") {
                            if !store.prepareWiderDateWindow() { store.clearResults() }
                        }
                        .buttonStyle(.bordered)
                        Text("Keeps your route, budget and trip length. Review dates before searching again.")
                            .font(FarelinTypography.font(.caption))
                            .foregroundStyle(.secondary)
                    } else if store.lastSearchUsedAI {
                        Text("Editing does not use an AI search. Sending another request may count toward your allowance.")
                            .font(FarelinTypography.font(.caption))
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .farelinCard()
        } else {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Trip ideas")
                        .font(FarelinTypography.font(.title2, weight: .bold))
                    Spacer()
                    Text("\(response.trips.count)")
                        .font(FarelinTypography.font(.caption, weight: .bold, family: .mono))
                        .foregroundStyle(.secondary)
                }
                ForEach(response.trips) { trip in
                    NativeTripCard(
                        trip: trip,
                        tripDetailService: tripDetailService,
                        onSaveWatch: { watchTrip = trip },
                        fareService: fareService,
                        reauthenticate: reauthenticate
                    )
                }
            }
        }
    }

    private func parsedSummary(
        _ parsed: ParsedTripSearch,
        sourceMap: [String: String]?,
        hardBudgetApplied: Bool?
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("WHAT FARELIN UNDERSTOOD")
                .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                .tracking(1.1)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    SearchFact(label: "FROM", value: parsed.originAirports.joined(separator: " + "), source: sourceMap?["originAirports"])
                    SearchFact(label: "WHEN", value: "\(FarelinSearchFormat.shortDate(parsed.startDate))–\(FarelinSearchFormat.shortDate(parsed.endDate))", source: sourceMap?["dateRange"])
                    SearchFact(label: "LENGTH", value: "\(parsed.minTripLengthDays)–\(parsed.maxTripLengthDays) days", source: sourceMap?["minTripLengthDays"])
                    SearchFact(
                        label: "BUDGET",
                        value: hardBudgetApplied == false ? "No hard cap" : "≤ \(FarelinSearchFormat.money(parsed.maxBudget, currency: "EUR"))",
                        source: sourceMap?["maxBudget"]
                    )
                    SearchFact(label: "PLAN", value: parsed.tripPlan.replacingOccurrences(of: "_", with: " ").capitalized, source: sourceMap?["tripPlan"])
                }
            }
            Text(
                searchMode == .ai
                    ? "Your wording overrides profile defaults for this search."
                    : "Search labels show which values came from this search and which came from your profile."
            )
                .font(FarelinTypography.font(.caption))
                .foregroundStyle(.secondary)
        }
    }

    private func providerNotice(_ metadata: SearchProviderMetadata?) -> (text: String, warning: Bool)? {
        guard let metadata else { return nil }
        if metadata.liveProviderAttempted && !metadata.liveProviderSucceeded {
            return (
                metadata.providerWarnings.first
                    ?? "The fare provider could not be reached. These are earlier observations and may be out of date.",
                true
            )
        }
        if metadata.cachedResultsUsed && !metadata.liveProviderSucceeded {
            return ("Showing previously observed fares. Check the current price with the provider.", false)
        }
        if let warning = metadata.providerWarnings.first {
            return (warning, false)
        }
        return nil
    }

    private func plainText(_ value: String) -> String {
        value
            .split(whereSeparator: \.isNewline)
            .map { line in
                line.drop(while: { "#*-• ".contains($0) })
            }
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }
}

private struct SearchFact: View {
    let label: String
    let value: String
    let source: String?

    init(label: String, value: String, source: String? = nil) {
        self.label = label
        self.value = value
        self.source = source
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                .foregroundStyle(.secondary)
            Text(value)
                .font(FarelinTypography.font(.caption, weight: .medium))
                .lineLimit(1)
            if let source {
                Text(source == "search" ? "THIS SEARCH" : source == "profile" ? "PROFILE" : "DEFAULT")
                    .font(FarelinTypography.mono(size: 8, weight: .semibold))
                    .foregroundStyle(source == "search" ? FarelinColor.mint : .secondary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).stroke(Color(.separator).opacity(0.4)) }
    }
}

private enum DiscoverSearchMode: Hashable {
    case ai
    case advanced
}

private let advancedTravelStyles: [(key: String, label: String)] = [
    ("weekend_city_break", "Weekend"),
    ("beach", "Beach"),
    ("food", "Food"),
    ("culture", "Culture"),
    ("nature", "Nature"),
    ("nightlife", "Nightlife"),
    ("cheap_adventure", "Cheap adventure"),
    ("long_haul_dream", "Long-haul"),
]

private struct NativeTripCard: View {
    let trip: SearchTrip
    let tripDetailService: any TripDetailServicing
    let onSaveWatch: () -> Void
    let fareService: any NativeFareSaving
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    @State private var isSaved = false
    @State private var isSaving = false
    @State private var saveError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(trip.routeTitle)
                        .font(FarelinTypography.font(.headline))
                    Text("\(FarelinSearchFormat.shortDate(trip.outboundFlight.departureDateTime))–\(FarelinSearchFormat.shortDate(trip.returnFlight.departureDateTime)) · \(trip.nights) \(trip.nights == 1 ? "night" : "nights")")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 3) {
                    Text(FarelinSearchFormat.priceHeadline(trip))
                        .font(FarelinTypography.font(.title3, weight: .bold))
                        .foregroundStyle(FarelinColor.mint)
                        .multilineTextAlignment(.trailing)
                    Text(trip.fareKind == "round_trip_bundle" ? "round trip" : "flight total")
                        .font(FarelinTypography.font(.caption2))
                        .foregroundStyle(.secondary)
                }
            }

            FlowLayout(spacing: 7) {
                    TripBadge(text: "\(trip.dealScore) deal", color: scoreColor(trip.dealScore))
                    if let fit = trip.fitScore {
                        TripBadge(text: "\(fit) fit", color: scoreColor(fit))
                    }
                    TripBadge(text: trip.tripTypeLabel, color: .secondary)
                    TripBadge(text: FarelinSearchFormat.fareLabel(trip), color: FarelinColor.coral)
                    ForEach(trip.tags.prefix(2), id: \.self) { tag in
                        TripBadge(text: tag, color: .secondary)
                    }
            }

            if trip.durationMatch == "alternative" || trip.tags.contains("Different trip length") {
                Label("Different length: \(trip.nights) nights. This does not match your requested duration.", systemImage: "calendar.badge.exclamationmark")
                    .font(FarelinTypography.font(.caption, weight: .semibold)).foregroundStyle(FarelinColor.coral)
            }
            if ["multi_city", "open_jaw"].contains(trip.tripType), let segments = trip.segments, !segments.isEmpty {
                FarelinSectionLabel(title: "YOUR ROUTE")
                ForEach(Array(segments.enumerated()), id: \.offset) { index, segment in
                    RouteSegmentRow(index: index, segment: segment, showPriceLink: trip.checkPriceURL == nil)
                }
                if let estimate = trip.transportTotalEstimate, (trip.groundEstimate ?? 0) > 0 {
                    Text("Estimated transport total \(FarelinSearchFormat.money(estimate, currency: trip.outboundFlight.currency)) including ground travel. Ground prices and schedules are unverified.")
                        .font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                }
            } else {
            FlightSummaryRow(label: "Outbound", flight: trip.outboundFlight, bundle: trip.fareKind == "round_trip_bundle")
            if let transfer = trip.groundTransfer {
                HStack(alignment: .top, spacing: 9) {
                    Image(systemName: "tram.fill")
                        .foregroundStyle(FarelinColor.coral)
                    Text("\(transfer.fromCity) → \(transfer.toCity) · about \(FarelinSearchFormat.duration(hours: transfer.durationHours)) by \(transfer.mode) · estimated \(FarelinSearchFormat.money(transfer.estimatedCost, currency: "EUR"))")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
            }
            FlightSummaryRow(label: trip.tripType == "multi_city" ? "Homebound" : "Return", flight: trip.returnFlight, bundle: trip.fareKind == "round_trip_bundle")
            }
            if trip.fareKind == "round_trip_bundle" {
                Text("This observed return has dates and a total price, not verified times, stops or baggage. Confirm exact flights with the provider.")
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.orange)
            }

            DisclosureGroup("Why this works") {
                VStack(alignment: .leading, spacing: 10) {
                    Text(trip.explanation)
                        .font(FarelinTypography.font(.subheadline))
                        .foregroundStyle(.secondary)
                    ForEach(trip.warnings, id: \.self) { warning in
                        Label(warning, systemImage: "exclamationmark.triangle")
                            .font(FarelinTypography.font(.caption))
                            .foregroundStyle(FarelinColor.coral)
                    }
                    Text(FarelinSearchFormat.observationDetail(trip))
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 8)
            }
            .tint(FarelinColor.mint)

            Divider()

            if let suggestionId = trip.suggestionId {
                Button {
                    Task { await saveFare(suggestionId) }
                } label: {
                    if isSaving {
                        ProgressView().controlSize(.small)
                    } else {
                        Label(isSaved ? "Saved to Watches" : "Save this fare", systemImage: isSaved ? "bookmark.fill" : "bookmark")
                    }
                }
                .font(FarelinTypography.font(.subheadline, weight: .semibold))
                .tint(FarelinColor.mint)
                .disabled(isSaved || isSaving)
                .accessibilityIdentifier("save-fare")
                if let saveError {
                    Text(saveError).font(FarelinTypography.font(.caption)).foregroundStyle(FarelinColor.coral)
                }
            } else {
                Text("Saving is unavailable for this result because its fare record could not be stored.")
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.secondary)
            }

                Button(action: onSaveWatch) {
                    Label("Watch trips like this", systemImage: "bell.badge")
                        .font(FarelinTypography.font(.subheadline, weight: .semibold))
                }
                .tint(FarelinColor.mint)

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) { detailAction; priceAction }
                VStack(alignment: .leading, spacing: 10) { detailAction; priceAction }
            }
            Text("Price may change. Check with the provider.")
                .font(FarelinTypography.font(.caption2)).foregroundStyle(.secondary)
        }
        .farelinCard()
        .accessibilityElement(children: .contain)
    }

    private var detailAction: some View {
        NavigationLink {
            TripDetailView(trip: trip, service: tripDetailService, reauthenticate: reauthenticate)
        } label: {
            Text("View trip").font(FarelinTypography.font(.subheadline, weight: .semibold))
                .lineLimit(1).fixedSize(horizontal: true, vertical: false)
        }.buttonStyle(.bordered)
    }

    @ViewBuilder private var priceAction: some View {
        if let url = trip.checkPriceURL {
            Link(destination: url) {
                Label("Check price", systemImage: "arrow.up.right")
                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
                    .lineLimit(1).fixedSize(horizontal: true, vertical: false)
            }
            .buttonStyle(.borderedProminent)
            .tint(FarelinColor.mint).foregroundStyle(FarelinColor.ink)
            .accessibilityIdentifier("trip-check-price")
        }
    }

    private func scoreColor(_ score: Int) -> Color {
        score >= 75 ? FarelinColor.mint : score >= 50 ? .orange : .secondary
    }

    private func saveFare(_ suggestionId: String) async {
        guard !isSaving else { return }
        isSaving = true
        saveError = nil
        defer { isSaving = false }
        do {
            _ = try await fareService.saveFare(suggestionId: suggestionId)
            isSaved = true
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else {
                saveError = "Sign in again to save this fare."
                return
            }
            do {
                _ = try await fareService.saveFare(suggestionId: suggestionId)
                isSaved = true
            } catch {
                saveError = (error as? LocalizedError)?.errorDescription ?? "Could not save this fare."
            }
        } catch {
            saveError = (error as? LocalizedError)?.errorDescription ?? "Could not save this fare."
        }
    }
}

private struct WatchCreationSheet: View {
    let trip: SearchTrip
    let parsed: ParsedTripSearch?
    let fallbackOrigins: [String]
    let accountEmail: String
    let service: any NativeWatchCreating
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    let onSaved: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var budgetText: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(
        trip: SearchTrip,
        parsed: ParsedTripSearch?,
        fallbackOrigins: [String],
        accountEmail: String,
        service: any NativeWatchCreating,
        reauthenticate: (@MainActor @Sendable () async -> Bool)?,
        onSaved: @escaping () -> Void
    ) {
        self.trip = trip
        self.parsed = parsed
        self.fallbackOrigins = fallbackOrigins
        self.accountEmail = accountEmail
        self.service = service
        self.reauthenticate = reauthenticate
        self.onSaved = onSaved
        _budgetText = State(initialValue: String(Int((parsed?.maxBudget ?? trip.totalPrice).rounded())))
    }

    private var startDate: String {
        parsed?.startDate ?? String(trip.outboundFlight.departureDateTime.prefix(10))
    }

    private var endDate: String {
        parsed?.endDate ?? String(trip.returnFlight.departureDateTime.prefix(10))
    }

    private var origins: [String] {
        let selected = parsed?.originAirports ?? fallbackOrigins
        return selected.isEmpty ? [trip.outboundFlight.origin] : selected
    }

    private var destinations: [String] {
        var codes = [trip.outboundFlight.destination]
        if trip.tripType == "open_jaw" { codes.append(trip.returnFlight.origin) }
        return Array(Set(codes)).sorted()
    }

    private var destinationLabel: String {
        if let parsed {
            let area = parsed.destinationRegions.map { $0.capitalized } + parsed.destinationCountries + parsed.destinationContinents
            if !area.isEmpty { return area.joined(separator: " + ") }
            if let stops = parsed.routeStops, !stops.isEmpty { return stops.joined(separator: " → ") }
        }
        return trip.routeTitle
    }

    private var budget: Double? {
        guard let amount = Double(budgetText), (20...5000).contains(amount) else { return nil }
        return amount
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("KEEP WATCHING")
                            .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                            .tracking(1.2)
                            .foregroundStyle(FarelinColor.mint)
                        Text("Trips like this, not this exact fare.")
                            .font(FarelinTypography.font(.title2, weight: .bold))
                        Text("Farelin will keep checking \(destinationLabel) from your selected airports, using this search's trip shape and dates. It won't reserve this price or route.")
                            .font(FarelinTypography.font(.subheadline))
                            .foregroundStyle(.secondary)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        watchRow("Origins", origins.joined(separator: " · "))
                        watchRow("Destinations", destinationLabel)
                        watchRow("Dates", "\(startDate) to \(endDate)")
                        watchRow("Length", "\(parsed?.minTripLengthDays ?? trip.tripLengthDays)–\(parsed?.maxTripLengthDays ?? trip.tripLengthDays) days")
                        watchRow("Checks", "Weekly · email to \(accountEmail)")
                    }
                    .farelinCard()

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Alert when flight total is below (€)")
                            .font(FarelinTypography.font(.subheadline, weight: .semibold))
                        TextField("Budget, €20–€5,000", text: $budgetText)
                            .keyboardType(.decimalPad)
                            .padding(12)
                            .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 14))
                        if budget == nil {
                            Text("Enter a flight budget between €20 and €5,000.")
                                .font(FarelinTypography.font(.caption))
                                .foregroundStyle(FarelinColor.coral)
                        }
                    }

                    if let errorMessage {
                        Label(errorMessage, systemImage: "exclamationmark.triangle")
                            .font(FarelinTypography.font(.footnote))
                            .foregroundStyle(FarelinColor.coral)
                    }

                    Button {
                        Task { await save() }
                    } label: {
                        if isSaving { ProgressView().tint(FarelinColor.ink) }
                        else { Label("Save weekly watch", systemImage: "bell.badge") }
                    }
                    .buttonStyle(FarelinPrimaryButtonStyle())
                    .disabled(isSaving || budget == nil || origins.isEmpty || startDate > endDate)

                    Text("An alert can only be sent to a confirmed account email. Fares are observations; check the final price with the provider.")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
                .padding(20)
            }
            .navigationTitle("Save a watch")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Cancel") { dismiss() } }
            }
        }
    }

    private func watchRow(_ title: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(title).foregroundStyle(.secondary).frame(width: 95, alignment: .leading)
            Text(value).fontWeight(.medium)
        }
        .font(FarelinTypography.font(.subheadline))
    }

    private func save() async {
        guard let budget else { return }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        var request = NativeSavedWatchRequest(
            email: accountEmail,
            name: "Trips: \(destinationLabel)",
            originAirports: origins,
            destinationAirports: parsed?.destinationAirports ?? destinations,
            startDate: startDate,
            endDate: endDate,
            minTripLengthDays: parsed?.minTripLengthDays ?? trip.tripLengthDays,
            maxTripLengthDays: parsed?.maxTripLengthDays ?? trip.tripLengthDays,
            maxBudget: budget,
            maxGroundTransferHours: parsed?.maxGroundTransferHours ?? 4,
            tripStyle: trip.tripType == "open_jaw" ? "two nearby cities" : "one city",
            frequency: "weekly",
            triggerMode: "below_budget"
        )
        request.tripPlan = parsed?.tripPlan ?? (trip.tripType == "multi_city" ? "multi_city" : trip.tripType == "open_jaw" ? "open_jaw" : "return")
        request.destinationCountries = parsed?.destinationCountries ?? []
        request.destinationRegions = parsed?.destinationRegions ?? []
        request.destinationContinents = parsed?.destinationContinents ?? []
        request.routeStops = parsed?.routeStops
        request.returnOriginAirports = parsed?.returnOriginAirports
        request.travelStyles = parsed?.travelStyles ?? []
        request.directOnly = parsed?.directOnly
        request.includeBaggage = parsed?.includeBaggage
        request.maxStops = parsed?.maxStops
        if !request.destinationCountries.isEmpty || !request.destinationRegions.isEmpty || !request.destinationContinents.isEmpty {
            request = requestWithArea(request)
        } else if request.tripPlan == "multi_city", request.routeStops == nil {
            request.routeStops = (trip.segments ?? []).dropLast().map(\.destination)
        } else if request.tripPlan == "open_jaw", request.returnOriginAirports == nil {
            request.destinationAirports = [trip.outboundFlight.destination]
            request.returnOriginAirports = [trip.returnFlight.origin]
        }
        do {
            _ = try await service.createWatch(request)
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else {
                errorMessage = APIError.unauthorized.errorDescription
                return
            }
            do {
                _ = try await service.createWatch(request)
            } catch {
                errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not save this watch."
                return
            }
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not save this watch."
            return
        }
        onSaved()
        dismiss()
    }

    private func requestWithArea(_ request: NativeSavedWatchRequest) -> NativeSavedWatchRequest {
        NativeSavedWatchRequest(
            email: request.email, name: request.name, originAirports: request.originAirports,
            destinationAirports: nil, startDate: request.startDate, endDate: request.endDate,
            minTripLengthDays: request.minTripLengthDays, maxTripLengthDays: request.maxTripLengthDays,
            maxBudget: request.maxBudget, maxGroundTransferHours: request.maxGroundTransferHours,
            tripStyle: request.tripStyle, frequency: request.frequency, triggerMode: request.triggerMode,
            destinationCountries: request.destinationCountries, destinationRegions: request.destinationRegions,
            destinationContinents: request.destinationContinents, tripPlan: request.tripPlan,
            routeStops: request.routeStops, returnOriginAirports: request.returnOriginAirports,
            travelStyles: request.travelStyles, directOnly: request.directOnly, includeBaggage: request.includeBaggage,
            maxStops: request.maxStops
        )
    }
}

struct TripDetailView: View {
    @State private var store: TripDetailStore

    init(
        trip: SearchTrip,
        service: any TripDetailServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)?,
        isSavedSnapshot: Bool = false
    ) {
        _store = State(
            initialValue: TripDetailStore(
                trip: trip,
                suggestionID: isSavedSnapshot ? nil : trip.suggestionId,
                service: service,
                reauthenticate: reauthenticate
            )
        )
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 20) {
                tripHeader
                flightPlan
                whyItWorks
                itinerarySection
                providerAction
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 36)
        }
        .background(Color(.systemBackground))
        .navigationTitle(store.title ?? "Trip idea")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load() }
    }

    private var tripHeader: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(store.trip.tripTypeLabel.uppercased())
                .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                .tracking(1.2)
                .foregroundStyle(FarelinColor.mint)
            Text(store.trip.routeTitle)
                .font(FarelinTypography.display(size: 30, weight: .bold))
                .tracking(-0.7)
            Text("\(FarelinSearchFormat.shortDate(store.trip.outboundFlight.departureDateTime))–\(FarelinSearchFormat.shortDate(store.trip.returnFlight.departureDateTime)) · \(store.trip.nights) \(store.trip.nights == 1 ? "night" : "nights")")
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)

            HStack(alignment: .firstTextBaseline) {
                Text(FarelinSearchFormat.priceHeadline(store.trip))
                    .font(FarelinTypography.font(.title2, weight: .bold))
                    .foregroundStyle(FarelinColor.mint)
                Spacer()
                TripBadge(text: "\(store.trip.dealScore) deal", color: detailScoreColor(store.trip.dealScore))
                if let fit = store.trip.fitScore {
                    TripBadge(text: "\(fit) fit", color: detailScoreColor(fit))
                }
            }
            Text(FarelinSearchFormat.observationDetail(store.trip))
                .font(FarelinTypography.font(.caption))
                .foregroundStyle(.secondary)
        }
        .padding(.top, 8)
    }

    private var flightPlan: some View {
        VStack(alignment: .leading, spacing: 12) {
            detailTitle(store.trip.tripType == "multi_city" ? "Every leg" : "Flights")
            if ["multi_city", "open_jaw"].contains(store.trip.tripType), let segments = store.trip.segments, !segments.isEmpty {
                ForEach(Array(segments.enumerated()), id: \.offset) { index, segment in
                    RouteSegmentRow(index: index, segment: segment, showPriceLink: store.trip.checkPriceURL == nil)
                }
                if let groundEstimate = store.trip.groundEstimate, groundEstimate > 0 {
                    Text("Ground travel is not included in the observed flight total. Roughly \(FarelinSearchFormat.money(groundEstimate, currency: "EUR")) extra; confirm actual transport costs.")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(FarelinColor.coral)
                }
            } else {
                FlightSummaryRow(label: "Outbound", flight: store.trip.outboundFlight, bundle: store.trip.fareKind == "round_trip_bundle")
                if let transfer = store.trip.groundTransfer {
                    Label {
                        Text("\(transfer.fromCity) → \(transfer.toCity) · about \(FarelinSearchFormat.duration(hours: transfer.durationHours)) by \(transfer.mode) · estimated \(FarelinSearchFormat.money(transfer.estimatedCost, currency: "EUR"))")
                            .font(FarelinTypography.font(.caption))
                    } icon: {
                        Image(systemName: "tram.fill")
                    }
                    .foregroundStyle(.secondary)
                    .farelinCard()
                }
                FlightSummaryRow(label: "Return", flight: store.trip.returnFlight, bundle: store.trip.fareKind == "round_trip_bundle")
            }
        }
    }

    private var whyItWorks: some View {
        VStack(alignment: .leading, spacing: 12) {
            detailTitle("Why this works")
            Text(store.trip.explanation)
                .font(FarelinTypography.font(.body))
                .lineSpacing(3)
            if !store.trip.tags.isEmpty {
                FlowLayout(spacing: 7) {
                    ForEach(store.trip.tags, id: \.self) { tag in
                        TripBadge(text: tag, color: .secondary)
                    }
                }
            }
            ForEach(store.trip.warnings, id: \.self) { warning in
                Label(warning, systemImage: "exclamationmark.triangle")
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(FarelinColor.coral)
            }
        }
        .farelinCard()
    }

    @ViewBuilder
    private var itinerarySection: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                detailTitle("Your Farelin plan")
                Spacer()
                if store.itineraryWasCached, store.itinerary != nil {
                    Text("SAVED PLAN")
                        .font(FarelinTypography.font(.caption2, weight: .bold, family: .mono))
                        .foregroundStyle(.secondary)
                }
            }

            if let itinerary = store.itinerary {
                Text(itinerary.summary)
                    .font(FarelinTypography.font(.body))
                    .lineSpacing(3)

                ForEach(Array(itinerary.days.enumerated()), id: \.offset) { _, day in
                    VStack(alignment: .leading, spacing: 11) {
                        Text(day.label)
                            .font(FarelinTypography.font(.headline))
                        ForEach(Array(day.items.enumerated()), id: \.offset) { _, item in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: itinerarySymbol(item.category))
                                    .foregroundStyle(FarelinColor.mint)
                                    .frame(width: 22)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.title)
                                        .font(FarelinTypography.font(.subheadline, weight: .semibold))
                                    Text("\(item.partOfDay.capitalized) · \(item.estimatedCost)")
                                        .font(FarelinTypography.font(.caption))
                                        .foregroundStyle(FarelinColor.coral)
                                    Text(item.description)
                                        .font(FarelinTypography.font(.caption))
                                        .foregroundStyle(.secondary)
                                        .lineSpacing(2)
                                }
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }

                if let gettingAround = itinerary.gettingAround, !gettingAround.isEmpty {
                    Label(gettingAround, systemImage: "figure.walk")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
                if let estimate = itinerary.extraCostEstimate, !estimate.isEmpty {
                    Label("Estimated extras: \(estimate)", systemImage: "eurosign.circle")
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(.secondary)
                }
                ForEach(itinerary.disclaimers, id: \.self) { disclaimer in
                    Text(disclaimer)
                        .font(FarelinTypography.font(.caption2))
                        .foregroundStyle(.secondary)
                }
            } else if store.isGenerating {
                HStack(spacing: 12) {
                    ProgressView()
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Planning around your flights…")
                            .font(FarelinTypography.font(.subheadline, weight: .semibold))
                        Text("This may take a few moments. Farelin will cache the finished plan.")
                            .font(FarelinTypography.font(.caption))
                            .foregroundStyle(.secondary)
                    }
                }
            } else if store.suggestionID != nil {
                Text("Build a realistic day-by-day idea around the observed arrival and departure times, your profile, and this trip’s length.")
                    .font(FarelinTypography.font(.subheadline))
                    .foregroundStyle(.secondary)
                Button {
                    store.submitItineraryGeneration()
                } label: {
                    Label("Plan this trip", systemImage: "map")
                }
                .buttonStyle(FarelinPrimaryButtonStyle())
            } else {
                Text("This result does not have a saved suggestion to plan. Run a fresh search and open it again.")
                    .font(FarelinTypography.font(.subheadline))
                    .foregroundStyle(.secondary)
            }

            if let error = store.errorMessage {
                VStack(alignment: .leading, spacing: 8) {
                    Text(error)
                        .font(FarelinTypography.font(.caption))
                        .foregroundStyle(FarelinColor.coral)
                    Button("Dismiss") { store.dismissError() }
                        .font(FarelinTypography.font(.caption, weight: .semibold))
                }
            }
        }
        .farelinCard()
    }

    private var providerAction: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(store.disclaimer)
                .font(FarelinTypography.font(.caption))
                .foregroundStyle(.secondary)
            if let url = store.trip.checkPriceURL {
                Link(destination: url) {
                    Label("Check trip prices", systemImage: "arrow.up.right")
                        .lineLimit(1)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(FarelinPrimaryButtonStyle())
            }
        }
    }

    private func detailTitle(_ value: String) -> some View {
        Text(value.uppercased())
            .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
            .tracking(1.2)
            .foregroundStyle(.secondary)
    }

    private func itinerarySymbol(_ category: String) -> String {
        switch category.lowercased() {
        case "food": "fork.knife"
        case "nature", "hike", "hiking": "mountain.2"
        case "culture", "museum", "architecture": "building.columns"
        case "nightlife": "moon.stars"
        default: "location.fill"
        }
    }

    private func detailScoreColor(_ score: Int) -> Color {
        score >= 75 ? FarelinColor.mint : score >= 50 ? .orange : .secondary
    }
}

private struct FlowLayout: Layout {
    let spacing: CGFloat

    func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) -> CGSize {
        let result = arrangement(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) {
        let result = arrangement(proposal: proposal, subviews: subviews)
        for (index, point) in result.points.enumerated() {
            subviews[index].place(
                at: CGPoint(x: bounds.minX + point.x, y: bounds.minY + point.y),
                proposal: .unspecified
            )
        }
    }

    private func arrangement(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, points: [CGPoint]) {
        let width = proposal.width ?? 320
        var points: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            points.append(CGPoint(x: x, y: y))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return (CGSize(width: width, height: y + rowHeight), points)
    }
}

private struct TripBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(FarelinTypography.font(.caption2, weight: .bold))
            .padding(.horizontal, 9)
            .padding(.vertical, 6)
            .foregroundStyle(color)
            .background(color.opacity(0.13), in: Capsule())
    }
}

private struct RouteSegmentRow: View {
    let index: Int
    let segment: SearchTripSegment
    var showPriceLink = true

    private var statusLabel: String {
        guard segment.kind == "flight" else { return "Ground travel · estimate" }
        switch segment.flight?.confidenceLevel {
        case "mock": return "Flight · demo fare"
        case "live": return "Flight · live observation"
        case "cached": return "Flight · cached fare"
        default: return "Flight · indicative fare"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .top, spacing: 10) {
                Text("\(index + 1)").font(FarelinTypography.font(.caption, weight: .bold, family: .mono))
                    .frame(width: 24, height: 24)
                    .background(FarelinColor.mint.opacity(0.15), in: Circle())
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(segment.origin) → \(segment.destination)").font(FarelinTypography.font(.subheadline, weight: .bold, family: .mono))
                    Text("\(FarelinSearchFormat.shortDate(segment.departureDate)) · \(statusLabel)")
                        .font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                    if let transfer = segment.transfer {
                        Text("About \(FarelinSearchFormat.duration(hours: transfer.durationHours)) · estimated \(FarelinSearchFormat.money(transfer.estimatedCost, currency: "EUR")) · arrange separately")
                            .font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
                    }
                }
                Spacer(minLength: 4)
                if let flight = segment.flight {
                    Text(FarelinSearchFormat.money(flight.price, currency: flight.currency))
                        .font(FarelinTypography.font(.subheadline, weight: .bold))
                }
            }
            if showPriceLink, segment.kind == "flight", let text = segment.bookingUrl,
               let url = URL(string: text), url.scheme == "https", url.host != nil, url.user == nil, url.password == nil {
                Link("Check \(segment.origin) → \(segment.destination)", destination: url)
                    .font(FarelinTypography.font(.caption, weight: .semibold)).tint(FarelinColor.mint)
            } else if showPriceLink, segment.kind == "flight" {
                Text("Provider link unavailable for this flight.").font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 14))
    }
}

private struct FlightSummaryRow: View {
    let label: String
    let flight: SearchFlight
    var bundle = false

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(label.uppercased())
                    .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                    .foregroundStyle(.secondary)
                Text("\(flight.origin) → \(flight.destination)")
                    .font(FarelinTypography.font(.subheadline, weight: .semibold, family: .mono))
                Text(bundle ? "\(FarelinSearchFormat.shortDate(flight.departureDateTime)) · exact flight details unavailable" : FarelinSearchFormat.flightDetail(flight))
                    .font(FarelinTypography.font(.caption))
                    .foregroundStyle(.secondary)
                if !bundle {
                    Text(flight.airline)
                        .font(FarelinTypography.font(.caption2))
                        .foregroundStyle(.tertiary)
                }
            }
            Spacer()
            if !bundle {
                Text(FarelinSearchFormat.money(flight.price, currency: flight.currency))
                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
            }
        }
        .padding(13)
        .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 14))
    }
}

enum FarelinSearchFormat {
    static func money(_ amount: Double, currency: String) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currency
        formatter.maximumFractionDigits = amount.rounded() == amount ? 0 : 2
        formatter.locale = Locale(identifier: "en_IE")
        return formatter.string(from: NSNumber(value: amount)) ?? "\(currency) \(amount)"
    }

    static func shortDate(_ value: String) -> String {
        // Fare dates are local calendar dates, not instants to shift into the
        // device's time zone. Provider observations use a separate timestamp.
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_GB")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        guard let parsed = formatter.date(from: String(value.prefix(10))) else { return "Date unavailable" }
        formatter.dateFormat = "d MMM"
        return formatter.string(from: parsed)
    }

    static func flightDetail(_ flight: SearchFlight) -> String {
        let datePart = shortDate(flight.departureDateTime)
        let times: String
        if flight.durationMinutes == nil {
            times = "Flight times unverified"
        } else if let departure = date(flight.departureDateTime), let arrival = date(flight.arrivalDateTime) {
            times = "\(departure.formatted(date: .omitted, time: .shortened))–\(arrival.formatted(date: .omitted, time: .shortened))"
        } else {
            times = "Time unavailable"
        }
        let stops = flight.stops.map { $0 == 0 ? "direct" : "\($0) \($0 == 1 ? "stop" : "stops")" }
        return [datePart, times, stops].compactMap { $0 }.joined(separator: " · ")
    }

    static func priceHeadline(_ trip: SearchTrip) -> String {
        let price = trip.price
        let amount = money(price?.amount ?? trip.totalPrice, currency: price?.currency ?? "EUR")
        if price?.isEstimate == true { return "Estimated from \(amount)" }
        if price?.freshness == "stale" || price?.freshness == "aging" {
            return "Recently from \(amount)"
        }
        return "Observed from \(amount)"
    }

    static func fareLabel(_ trip: SearchTrip) -> String {
        if trip.price?.isLive == true { return "Quoted just now" }
        if trip.outboundFlight.confidenceLevel == "mock" { return "Demo fare" }
        if trip.outboundFlight.confidenceLevel == "indicative" { return "Indicative fare" }
        return "Observed fare"
    }

    static func observationDetail(_ trip: SearchTrip) -> String {
        guard let price = trip.price else {
            return "Observed fare. Check the final price with the provider."
        }
        if price.isEstimate {
            return "Estimated total from \(price.legCount) separately observed flights. Check every leg with the provider."
        }
        if let hours = price.ageHours {
            if hours < 1 { return "Observed less than an hour ago. The price is not guaranteed." }
            if hours < 24 { return "Observed about \(Int(hours.rounded())) hours ago. The price is not guaranteed." }
            let days = max(1, Int((hours / 24).rounded()))
            return "Observed about \(days) \(days == 1 ? "day" : "days") ago. The price may have changed."
        }
        return "Observed fare. Check the final price with the provider."
    }

    static func duration(hours: Double) -> String {
        hours.rounded() == hours ? "\(Int(hours))h" : String(format: "%.1fh", hours)
    }

    private static func date(_ value: String) -> Date? {
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let parsed = withFraction.date(from: value) { return parsed }

        let standard = ISO8601DateFormatter()
        standard.formatOptions = [.withInternetDateTime]
        if let parsed = standard.date(from: value) { return parsed }

        let dateOnly = DateFormatter()
        dateOnly.locale = Locale(identifier: "en_US_POSIX")
        dateOnly.dateFormat = "yyyy-MM-dd"
        return dateOnly.date(from: value)
    }
}
