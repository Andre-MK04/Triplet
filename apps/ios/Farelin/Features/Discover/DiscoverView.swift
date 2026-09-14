import SwiftUI

struct DiscoverView: View {
    let store: TripSearchStore
    let originAirports: [String]

    @FocusState private var promptFocused: Bool

    private let examples = [
        "A warm food-focused week in October under €300",
        "A quiet Nordic weekend next month with direct flights",
        "Surprise me with a nature trip for five to seven days",
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 22) {
                    introduction
                    searchComposer

                    if store.isSearching {
                        searchingState
                    } else if let error = store.errorMessage {
                        errorState(error)
                    } else if let response = store.response {
                        results(response)
                    } else {
                        startingState
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 36)
            }
            .scrollDismissesKeyboard(.interactively)
            .background(Color(.systemBackground))
            .navigationTitle("Discover")
        }
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ASK FARELIN")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.4)
                .foregroundStyle(FarelinColor.mint)
            Text("Where could you go?")
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .tracking(-0.8)
            Text("Describe the trip naturally. Farelin uses your profile unless you override it here.")
                .font(.body)
                .foregroundStyle(.secondary)
                .lineSpacing(3)
        }
        .padding(.top, 8)
    }

    private var searchComposer: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Flying from")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                if originAirports.isEmpty {
                    Text("No profile airports selected")
                        .font(.subheadline)
                        .foregroundStyle(FarelinColor.coral)
                } else {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(originAirports, id: \.self) { code in
                                Text(code)
                                    .font(.caption.monospaced().weight(.bold))
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

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(examples, id: \.self) { example in
                        Button {
                            store.useExample(example)
                            promptFocused = true
                        } label: {
                            Text(example)
                                .font(.caption)
                                .lineLimit(1)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 9)
                                .background(Color(.tertiarySystemBackground), in: Capsule())
                                .overlay { Capsule().stroke(Color(.separator).opacity(0.5)) }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Button {
                promptFocused = false
                Task { await store.search(origins: originAirports) }
            } label: {
                Label("Find trips", systemImage: "location.magnifyingglass")
            }
            .buttonStyle(FarelinPrimaryButtonStyle())
            .disabled(store.isSearching || store.query.trimmingCharacters(in: .whitespacesAndNewlines).count < 8)
            .accessibilityIdentifier("discover-search")
        }
        .farelinCard()
    }

    private var searchingState: some View {
        HStack(spacing: 14) {
            ProgressView()
                .tint(FarelinColor.mint)
            VStack(alignment: .leading, spacing: 3) {
                Text(store.progressMessage)
                    .font(.headline)
                Text("Farelin only summarizes fares returned by the backend.")
                    .font(.caption)
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
                .font(.headline)
                .foregroundStyle(FarelinColor.coral)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Try again") {
                Task { await store.search(origins: originAirports) }
            }
            .buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .farelinCard()
    }

    private var startingState: some View {
        VStack(alignment: .leading, spacing: 13) {
            Image(systemName: "point.3.connected.trianglepath.dotted")
                .font(.title2)
                .foregroundStyle(FarelinColor.mint)
            Text("One request, complete trip ideas")
                .font(.headline)
            Text("Dates, budgets and places you name here override your profile. Anything you leave vague comes from your saved travel defaults.")
                .font(.subheadline)
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
                    .font(.caption.monospaced().weight(.semibold))
                    .foregroundStyle(FarelinColor.mint)
                Text(plainText(response.message))
                    .font(.body)
                    .lineSpacing(3)
            }
            .farelinCard()
        }

        if let parsed = response.parsedRequest {
            parsedSummary(parsed)
        }

        if let notice = providerNotice(response.providerMetadata) {
            Label(notice.text, systemImage: notice.warning ? "exclamationmark.triangle" : "clock.arrow.circlepath")
                .font(.footnote)
                .foregroundStyle(notice.warning ? FarelinColor.coral : .secondary)
                .farelinCard()
        }

        if let relaxation = response.relaxationNote, !relaxation.isEmpty {
            Label(relaxation, systemImage: "arrow.triangle.2.circlepath")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .farelinCard()
        }

        if response.trips.isEmpty {
            ContentUnavailableView {
                Label("No observed fares found", systemImage: "airplane.arrival")
            } description: {
                Text("Try a wider date window, a higher budget, or a less specific destination.")
            }
            .farelinCard()
        } else {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Trip ideas")
                        .font(.title2.bold())
                    Spacer()
                    Text("\(response.trips.count)")
                        .font(.caption.monospaced().weight(.bold))
                        .foregroundStyle(.secondary)
                }
                ForEach(response.trips) { trip in
                    NativeTripCard(trip: trip)
                }
            }
        }
    }

    private func parsedSummary(_ parsed: ParsedTripSearch) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("WHAT FARELIN UNDERSTOOD")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.1)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    SearchFact(label: "FROM", value: parsed.originAirports.joined(separator: " + "))
                    SearchFact(label: "WHEN", value: "\(FarelinSearchFormat.shortDate(parsed.startDate))–\(FarelinSearchFormat.shortDate(parsed.endDate))")
                    SearchFact(label: "LENGTH", value: "\(parsed.minTripLengthDays)–\(parsed.maxTripLengthDays) days")
                    SearchFact(label: "BUDGET", value: "≤ \(FarelinSearchFormat.money(parsed.maxBudget, currency: "EUR"))")
                    SearchFact(label: "PLAN", value: parsed.tripPlan.replacingOccurrences(of: "_", with: " ").capitalized)
                }
            }
            Text("Your wording overrides profile defaults for this search.")
                .font(.caption)
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

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.caption2.monospaced().weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.weight(.medium))
                .lineLimit(1)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).stroke(Color(.separator).opacity(0.4)) }
    }
}

private struct NativeTripCard: View {
    let trip: SearchTrip

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(trip.routeTitle)
                        .font(.headline)
                    Text("\(FarelinSearchFormat.shortDate(trip.outboundFlight.departureDateTime))–\(FarelinSearchFormat.shortDate(trip.returnFlight.departureDateTime)) · \(trip.nights) \(trip.nights == 1 ? "night" : "nights")")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 3) {
                    Text(FarelinSearchFormat.priceHeadline(trip))
                        .font(.title3.bold())
                        .foregroundStyle(FarelinColor.mint)
                        .multilineTextAlignment(.trailing)
                    Text(trip.fareKind == "round_trip_bundle" ? "round trip" : "flight total")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 7) {
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
            }

            FlightSummaryRow(label: "Outbound", flight: trip.outboundFlight)
            if let transfer = trip.groundTransfer {
                HStack(alignment: .top, spacing: 9) {
                    Image(systemName: "tram.fill")
                        .foregroundStyle(FarelinColor.coral)
                    Text("\(transfer.fromCity) → \(transfer.toCity) · about \(FarelinSearchFormat.duration(hours: transfer.durationHours)) by \(transfer.mode) · estimated \(FarelinSearchFormat.money(transfer.estimatedCost, currency: "EUR"))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            FlightSummaryRow(label: "Return", flight: trip.returnFlight)

            DisclosureGroup("Why this works") {
                VStack(alignment: .leading, spacing: 10) {
                    Text(trip.explanation)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    ForEach(trip.warnings, id: \.self) { warning in
                        Label(warning, systemImage: "exclamationmark.triangle")
                            .font(.caption)
                            .foregroundStyle(FarelinColor.coral)
                    }
                    Text(FarelinSearchFormat.observationDetail(trip))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 8)
            }
            .tint(FarelinColor.mint)

            Divider()

            HStack(alignment: .center, spacing: 12) {
                Text("Price may change. Confirm availability with the provider.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Spacer()
                if let url = trip.checkPriceURL {
                    Link(destination: url) {
                        Label("Check price", systemImage: "arrow.up.right")
                            .font(.subheadline.weight(.semibold))
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FarelinColor.mint)
                    .foregroundStyle(FarelinColor.ink)
                }
            }
        }
        .farelinCard()
        .accessibilityElement(children: .contain)
    }

    private func scoreColor(_ score: Int) -> Color {
        score >= 75 ? FarelinColor.mint : score >= 50 ? .orange : .secondary
    }
}

private struct TripBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 9)
            .padding(.vertical, 6)
            .foregroundStyle(color)
            .background(color.opacity(0.13), in: Capsule())
    }
}

private struct FlightSummaryRow: View {
    let label: String
    let flight: SearchFlight

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(label.uppercased())
                    .font(.caption2.monospaced().weight(.semibold))
                    .foregroundStyle(.secondary)
                Text("\(flight.origin) → \(flight.destination)")
                    .font(.subheadline.monospaced().weight(.semibold))
                Text(FarelinSearchFormat.flightDetail(flight))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(flight.airline)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            Spacer()
            Text(FarelinSearchFormat.money(flight.price, currency: flight.currency))
                .font(.subheadline.weight(.semibold))
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
        guard let date = date(value) else { return value }
        return date.formatted(.dateTime.day().month(.abbreviated))
    }

    static func flightDetail(_ flight: SearchFlight) -> String {
        let datePart = shortDate(flight.departureDateTime)
        let times: String
        if let departure = date(flight.departureDateTime), let arrival = date(flight.arrivalDateTime) {
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
